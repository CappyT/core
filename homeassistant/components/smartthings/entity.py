"""Support for SmartThings Cloud."""

from typing import Any, override

from pysmartthings import (
    Attribute,
    Capability,
    Command,
    ComponentStatus,
    DeviceEvent,
    DeviceHealthEvent,
    SmartThings,
)
from pysmartthings.models import HealthStatus

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FullDevice
from .const import DOMAIN, MAIN
from .util import normalize_cycle_value

CYCLE_CAPABILITIES: dict[Capability, Attribute] = {
    Capability.SAMSUNG_CE_WASHER_CYCLE: Attribute.WASHER_CYCLE,
    Capability.SAMSUNG_CE_DRYER_CYCLE: Attribute.DRYER_CYCLE,
}


DRYER_CYCLE_OPTIONS = {"dryingLevel", "dryingTime"}


def get_cycle_capability(
    device: FullDevice, cycle_option_key: str, component: str = MAIN
) -> Capability | None:
    """Return the cycle capability that constrains an option, if there is one.

    A washer-dryer can expose both cycles, so drying options prefer the dryer cycle
    and washing options the washer cycle.
    """
    preferred = (
        [Capability.SAMSUNG_CE_DRYER_CYCLE, Capability.SAMSUNG_CE_WASHER_CYCLE]
        if cycle_option_key in DRYER_CYCLE_OPTIONS
        else [Capability.SAMSUNG_CE_WASHER_CYCLE, Capability.SAMSUNG_CE_DRYER_CYCLE]
    )
    return next(
        (
            capability
            for capability in preferred
            if capability in device.status[component]
        ),
        None,
    )


class SmartThingsEntity(Entity):
    """Defines a SmartThings entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        capabilities: set[Capability],
        *,
        component: str = MAIN,
    ) -> None:
        """Initialize the instance."""
        self.client = client
        self.capabilities = capabilities
        self.component = component
        self._internal_state: ComponentStatus = {
            capability: device.status[component][capability]
            for capability in capabilities
            if capability in device.status[component]
        }
        self.device = device
        self._attr_unique_id = f"{device.device.device_id}_{component}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device.device_id)},
        )
        self._attr_available = device.online

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        for capability in self._internal_state:
            self.async_on_remove(
                self.client.add_device_capability_event_listener(
                    self.device.device.device_id,
                    self.component,
                    capability,
                    self._update_handler,
                )
            )
        self.async_on_remove(
            self.client.add_device_availability_event_listener(
                self.device.device.device_id, self._availability_handler
            )
        )
        self._update_attr()

    def _availability_handler(self, event: DeviceHealthEvent) -> None:
        self._attr_available = event.status != HealthStatus.OFFLINE
        self.async_write_ha_state()

    def _update_handler(self, event: DeviceEvent) -> None:
        self._internal_state[event.capability][event.attribute].value = event.value
        self._internal_state[event.capability][event.attribute].data = event.data
        self._handle_update()

    def supports_capability(self, capability: Capability) -> bool:
        """Test if device supports a capability."""
        return capability in self.device.status[self.component]

    def get_attribute_value(self, capability: Capability, attribute: Attribute) -> Any:
        """Get the value of a device attribute."""
        return self._internal_state[capability][attribute].value

    def _update_attr(self) -> None:
        """Update the attributes."""

    def _handle_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    async def execute_device_command(
        self,
        capability: Capability,
        command: Command,
        argument: int | str | list[Any] | dict[str, Any] | None = None,
    ) -> None:
        """Execute a command on the device."""
        kwargs = {}
        if argument is not None:
            kwargs["argument"] = argument
        await self.client.execute_device_command(
            self.device.device.device_id, capability, command, self.component, **kwargs
        )


class SmartThingsCycleOptionEntity(SmartThingsEntity):
    """Defines a SmartThings entity for an option of a washer/dryer cycle."""

    _cycle_capability: Capability | None = None
    _cycle_option_key: str | None = None
    _cycle_option_capability: Capability | None = None
    _cycle_option_status_attribute: Attribute | None = None
    _option_value_stale: bool = False
    # Status objects are shared by all entities of a device, so each entity keeps
    # its own copy of the cycle to detect a change
    _last_cycle: str | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._option_value_stale = self._is_initially_stale()
        if self._cycle_capability is not None:
            self._last_cycle = normalize_cycle_value(
                self.get_attribute_value(
                    self._cycle_capability, CYCLE_CAPABILITIES[self._cycle_capability]
                )
            )
        await super().async_added_to_hass()

    def _is_initially_stale(self) -> bool:
        """Return whether the reported option value predates the selected cycle.

        Only the initial status carries timestamps, so an unknown one is treated
        as up to date rather than guessed.
        """
        if (
            self._cycle_capability is None
            or self._cycle_option_capability is None
            or self._cycle_option_status_attribute is None
        ):
            return False
        option_timestamp = self._internal_state[self._cycle_option_capability][
            self._cycle_option_status_attribute
        ].timestamp
        cycle_timestamp = self._internal_state[self._cycle_capability][
            CYCLE_CAPABILITIES[self._cycle_capability]
        ].timestamp
        if option_timestamp is None or cycle_timestamp is None:
            return False
        return option_timestamp < cycle_timestamp

    @override
    def _update_handler(self, event: DeviceEvent) -> None:
        if (
            self._cycle_capability is not None
            and event.capability == self._cycle_capability
            and event.attribute == CYCLE_CAPABILITIES[self._cycle_capability]
        ):
            cycle = normalize_cycle_value(event.value)
            if cycle != self._last_cycle:
                self._option_value_stale = True
                self._last_cycle = cycle
        elif (
            event.capability == self._cycle_option_capability
            and event.attribute == self._cycle_option_status_attribute
        ):
            self._option_value_stale = False
        super()._update_handler(event)

    @property
    def _cycle_option(self) -> dict[str, Any] | None:
        """Return the constraints the selected cycle puts on this option."""
        if self._cycle_capability is None or self._cycle_option_key is None:
            return None
        supported_cycles = self.get_attribute_value(
            self._cycle_capability, Attribute.SUPPORTED_CYCLES
        )
        current_cycle = normalize_cycle_value(
            self.get_attribute_value(
                self._cycle_capability, CYCLE_CAPABILITIES[self._cycle_capability]
            )
        )
        if not supported_cycles or current_cycle is None:
            return None
        supported_options: dict[str, Any] = next(
            (
                cycle["supportedOptions"]
                for cycle in supported_cycles
                if cycle["cycle"].lower() == current_cycle
            ),
            {},
        )
        return supported_options.get(self._cycle_option_key)

    @property
    def cycle_options(self) -> list[str] | None:
        """Return the values the selected cycle allows for this option.

        `None` means the cycle does not restrict the option. A cycle that locks the
        option reports no options, so only its default is allowed.
        """
        if (option := self._cycle_option) is None:
            return None
        if option["options"]:
            return option["options"]
        return [option["default"]] if "default" in option else []

    def resolve_cycle_option_value(self, raw_value: Any) -> Any:
        """Return the value to report for this option.

        Appliances do not republish their options when the cycle is changed
        remotely, so the cloud keeps reporting the values of the previous cycle.
        Report what the selected cycle defaults to until the device sends a fresh
        value, which is also what the SmartThings app shows.
        """
        if (option := self._cycle_option) is None or not (
            options := self.cycle_options
        ):
            return raw_value
        if not self._option_value_stale and raw_value in options:
            return raw_value
        return option.get("default", raw_value)

    def validate_cycle_option(self, value: Any) -> None:
        """Raise if the selected cycle does not allow the value."""
        if (options := self.cycle_options) is not None and value not in options:
            raise ServiceValidationError("Option is not supported by selected cycle")

    def confirm_cycle_option(self, value: Any) -> None:
        """Report the device value again once a command has set it.

        The cloud may not send an event when a command sets the value it already
        holds, which would keep the cycle default reported.
        """
        if (
            self._option_value_stale
            and self._cycle_option_capability is not None
            and self._cycle_option_status_attribute is not None
            and value
            == self.get_attribute_value(
                self._cycle_option_capability, self._cycle_option_status_attribute
            )
        ):
            self._option_value_stale = False
            self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.cycle_options != []
