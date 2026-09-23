"""Support for select entities through the SmartThings cloud API."""

from dataclasses import dataclass
from typing import cast, override

from pysmartthings import Attribute, Capability, Command, ComponentStatus, SmartThings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsCycleOptionEntity, SmartThingsEntity
from .util import normalize_cycle_value

LAMP_TO_HA = {
    "extraHigh": "extra_high",
    "high": "high",
    "mid": "mid",
    "low": "low",
    "on": "on",
    "off": "off",
}

SOUND_MODE_TO_HA = {
    "voice": "voice",
    "beep": "tone",
    "mute": "mute",
}

DRIVING_MODE_TO_HA = {
    "areaThenWalls": "area_then_walls",
    "wallFirst": "walls_first",
    "quickCleaningZigzagPattern": "quick_clean_zigzag_pattern",
}

CLEANING_TYPE_TO_HA = {
    "vacuum": "vacuum",
    "mop": "mop",
    "vacuumAndMopTogether": "vacuum_and_mop_together",
    "mopAfterVacuum": "mop_after_vacuum",
}

WASHER_SOIL_LEVEL_TO_HA = {
    "none": "none",
    "heavy": "heavy",
    "normal": "normal",
    "light": "light",
    "extraLight": "extra_light",
    "extraHeavy": "extra_heavy",
    "up": "up",
    "down": "down",
}

WATER_SPRAY_LEVEL_TO_HA = {
    "high": "high",
    "mediumHigh": "moderate_high",
    "medium": "medium",
    "mediumLow": "moderate_low",
    "low": "low",
}

WASHER_SPIN_LEVEL_TO_HA = {
    "none": "none",
    "rinseHold": "rinse_hold",
    "noSpin": "no_spin",
    "low": "low",
    "extraLow": "extra_low",
    "delicate": "delicate",
    "medium": "medium",
    "high": "high",
    "extraHigh": "extra_high",
    "200": "200",
    "400": "400",
    "600": "600",
    "800": "800",
    "1000": "1000",
    "1200": "1200",
    "1400": "1400",
    "1600": "1600",
}

WASHER_WATER_TEMPERATURE_TO_HA = {
    "none": "none",
    "20": "20",
    "30": "30",
    "40": "40",
    "50": "50",
    "60": "60",
    "65": "65",
    "70": "70",
    "75": "75",
    "80": "80",
    "90": "90",
    "95": "95",
    "tapCold": "tap_cold",
    "cold": "cold",
    "cool": "cool",
    "ecoWarm": "eco_warm",
    "warm": "warm",
    "semiHot": "semi_hot",
    "hot": "hot",
    "extraHot": "extra_hot",
    "extraLow": "extra_low",
    "low": "low",
    "mediumLow": "medium_low",
    "medium": "medium",
    "high": "high",
}

DISHWASHER_WASHING_COURSE_TO_HA = {
    "auto": "auto",
    "AI": "ai",
    "normal": "normal",
    "daily": "daily",
    "daily_09": "daily",
    "eco": "eco",
    "eco_08": "eco",
    "eco_10": "eco",
    "intensive": "intensive",
    "heavy": "heavy",
    "chef": "chef",
    "potsAndPans": "pots_and_pans",
    "delicate": "delicate",
    "glasses": "glasses",
    "drinkware": "drinkware",
    "express": "express",
    "express_0C": "express",
    "quick": "quick",
    "quick_14": "quick",
    "upperExpress": "upper_express",
    "preWash": "pre_wash",
    "preBlast": "pre_blast",
    "rinseOnly": "rinse_only",
    "coldRinse": "cold_rinse",
    "babycare": "babycare",
    "babyBottle": "baby_bottle",
    "plastics": "plastics",
    "steamSoak": "steam_soak",
    "night": "night",
    "nightSilence": "night_silence",
    "extraSilence": "extra_silence",
    "dryOnly": "dry_only",
    "rinseDry": "rinse_dry",
    "selfClean": "self_clean",
    "machineCare": "machine_care",
}


@dataclass(frozen=True, kw_only=True)
class SmartThingsSelectDescription(SelectEntityDescription):
    """Class describing SmartThings select entities."""

    key: Capability
    requires_remote_control_status: bool = False
    requires_dishwasher_machine_state: str | None = None
    options_attribute: Attribute
    status_attribute: Attribute
    command: Command
    options_map: dict[str, str] | None = None
    default_options: list[str] | None = None
    extra_components: list[str] | None = None
    capability_ignore_list: list[Capability] | None = None
    value_is_integer: bool = False
    cycle_option_key: str | None = None


CAPABILITIES_TO_SELECT: dict[Capability | str, SmartThingsSelectDescription] = {
    Capability.DISHWASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DISHWASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
    ),
    Capability.DRYER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DRYER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.WASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.WASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT,
        translation_key="detergent_amount",
        options_attribute=Attribute.SUPPORTED_AMOUNT,
        status_attribute=Attribute.AMOUNT,
        command=Command.SET_AMOUNT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
        translation_key="dishwasher_washing_course",
        requires_remote_control_status=True,
        requires_dishwasher_machine_state="stop",
        options_attribute=Attribute.SUPPORTED_COURSES,
        status_attribute=Attribute.WASHING_COURSE,
        command=Command.SET_WASHING_COURSE,
        options_map=DISHWASHER_WASHING_COURSE_TO_HA,
    ),
    Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT: (
        SmartThingsSelectDescription(
            key=Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT,
            translation_key="flexible_detergent_amount",
            options_attribute=Attribute.SUPPORTED_AMOUNT,
            status_attribute=Attribute.AMOUNT,
            command=Command.SET_AMOUNT,
            entity_category=EntityCategory.CONFIG,
        )
    ),
    Capability.SAMSUNG_CE_LAMP: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_LAMP,
        translation_key="lamp",
        options_attribute=Attribute.SUPPORTED_BRIGHTNESS_LEVEL,
        status_attribute=Attribute.BRIGHTNESS_LEVEL,
        command=Command.SET_BRIGHTNESS_LEVEL,
        options_map=LAMP_TO_HA,
        entity_category=EntityCategory.CONFIG,
        extra_components=["hood"],
        capability_ignore_list=[Capability.SAMSUNG_CE_CONNECTION_STATE],
    ),
    Capability.SAMSUNG_CE_SOUND_DETECTION_SENSITIVITY: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_SOUND_DETECTION_SENSITIVITY,
        translation_key="sound_detection_sensitivity",
        options_attribute=Attribute.SUPPORTED_LEVELS,
        status_attribute=Attribute.LEVEL,
        command=Command.SET_LEVEL,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    Capability.CUSTOM_WASHER_SPIN_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SPIN_LEVEL,
        translation_key="spin_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SPIN_LEVEL,
        status_attribute=Attribute.WASHER_SPIN_LEVEL,
        command=Command.SET_WASHER_SPIN_LEVEL,
        options_map=WASHER_SPIN_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
        cycle_option_key="spinLevel",
    ),
    Capability.CUSTOM_WASHER_SOIL_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SOIL_LEVEL,
        translation_key="soil_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SOIL_LEVEL,
        status_attribute=Attribute.WASHER_SOIL_LEVEL,
        command=Command.SET_WASHER_SOIL_LEVEL,
        options_map=WASHER_SOIL_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
        cycle_option_key="soilLevel",
    ),
    Capability.CUSTOM_WASHER_WATER_TEMPERATURE: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_WATER_TEMPERATURE,
        translation_key="water_temperature",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_WASHER_WATER_TEMPERATURE,
        status_attribute=Attribute.WASHER_WATER_TEMPERATURE,
        command=Command.SET_WASHER_WATER_TEMPERATURE,
        options_map=WASHER_WATER_TEMPERATURE_TO_HA,
        entity_category=EntityCategory.CONFIG,
        cycle_option_key="waterTemperature",
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_WATER_SPRAY_LEVEL: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_WATER_SPRAY_LEVEL,
        translation_key="robot_cleaner_water_spray_level",
        options_attribute=Attribute.SUPPORTED_WATER_SPRAY_LEVELS,
        status_attribute=Attribute.WATER_SPRAY_LEVEL,
        command=Command.SET_WATER_SPRAY_LEVEL,
        options_map=WATER_SPRAY_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_DRIVING_MODE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_DRIVING_MODE,
        translation_key="robot_cleaner_driving_mode",
        options_attribute=Attribute.SUPPORTED_DRIVING_MODES,
        status_attribute=Attribute.DRIVING_MODE,
        command=Command.SET_DRIVING_MODE,
        options_map=DRIVING_MODE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_DUST_FILTER_ALARM: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DUST_FILTER_ALARM,
        translation_key="dust_filter_alarm",
        options_attribute=Attribute.SUPPORTED_ALARM_THRESHOLDS,
        status_attribute=Attribute.ALARM_THRESHOLD,
        command=Command.SET_ALARM_THRESHOLD,
        entity_category=EntityCategory.CONFIG,
        value_is_integer=True,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_SYSTEM_SOUND_MODE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_SYSTEM_SOUND_MODE,
        translation_key="robot_cleaner_sound_mode",
        options_attribute=Attribute.SUPPORTED_SOUND_MODES,
        status_attribute=Attribute.SOUND_MODE,
        command=Command.SET_SOUND_MODE,
        options_map=SOUND_MODE_TO_HA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_CLEANING_TYPE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_CLEANING_TYPE,
        translation_key="robot_cleaner_cleaning_type",
        options_attribute=Attribute.SUPPORTED_CLEANING_TYPES,
        status_attribute=Attribute.CLEANING_TYPE,
        command=Command.SET_CLEANING_TYPE,
        options_map=CLEANING_TYPE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
}
DISHWASHER_WASHING_OPTIONS_TO_SELECT: dict[
    Attribute | str, SmartThingsSelectDescription
] = {
    Attribute.SELECTED_ZONE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
        translation_key="selected_zone",
        options_attribute=Attribute.SELECTED_ZONE,
        status_attribute=Attribute.SELECTED_ZONE,
        command=Command.SET_SELECTED_ZONE,
        entity_category=EntityCategory.CONFIG,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state="stop",
    ),
    Attribute.ZONE_BOOSTER: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
        translation_key="zone_booster",
        options_attribute=Attribute.ZONE_BOOSTER,
        status_attribute=Attribute.ZONE_BOOSTER,
        command=Command.SET_ZONE_BOOSTER,
        entity_category=EntityCategory.CONFIG,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state="stop",
    ),
}

# Cycle codes only have a meaning within the reference table of the appliance.
# Only codes confirmed on real appliances are listed, others are not exposed.
CYCLE_TO_HA: dict[Capability, dict[str, dict[str, str]]] = {
    Capability.SAMSUNG_CE_WASHER_CYCLE: {
        "Table_02": {
            "1B": "cotton",
            "1C": "eco_40_60",
            "1D": "super_speed",
            "1E": "quick_wash",
            "1F": "intense_cold",
            "20": "hygiene_steam",
            "21": "colors",
            "22": "wool",
            "23": "outdoor",
            "24": "bedding",
            "25": "synthetics",
            "26": "delicates",
            "27": "rinse_spin",
            "28": "drain_spin",
            "29": "drum_clean_plus",
            "2A": "jeans",
            "2D": "silent_wash",
            "2E": "baby_care",
            "2F": "sportswear",
            "30": "cloudy_day",
            "32": "shirts",
            "33": "towels",
            "34": "mixed_load",
            "3A": "drum_clean",
        },
    },
    Capability.SAMSUNG_CE_DRYER_CYCLE: {
        "Table_03": {
            "16": "cotton",
            "17": "super_speed",
            "18": "synthetics",
            "19": "delicates",
            "1A": "wool",
            "1B": "bedding",
            "1C": "shirts",
            "1D": "towels",
            "1E": "outdoor",
            "1F": "mixed_load",
            "20": "iron_dry",
            "21": "hygiene_care",
            "23": "quick_dry",
            "24": "cool_air",
            "25": "warm_air",
            "27": "time_dry",
        },
    },
}


def get_cycle_names(status: ComponentStatus, capability: Capability) -> dict[str, str]:
    """Return the known cycle names of the reference table of an appliance."""
    if (
        table_status := status[capability].get(Attribute.REFERENCE_TABLE)
    ) is None or not isinstance(table := table_status.value, dict):
        return {}
    return CYCLE_TO_HA[capability].get(table["id"], {})


CYCLE_CAPABILITIES_TO_SELECT: dict[Capability, SmartThingsSelectDescription] = {
    Capability.SAMSUNG_CE_WASHER_CYCLE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_WASHER_CYCLE,
        translation_key="washer_cycle",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_CYCLES,
        status_attribute=Attribute.WASHER_CYCLE,
        command=Command.SET_WASHER_CYCLE,
    ),
    Capability.SAMSUNG_CE_DRYER_CYCLE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DRYER_CYCLE,
        translation_key="dryer_cycle",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_CYCLES,
        status_attribute=Attribute.DRYER_CYCLE,
        command=Command.SET_DRYER_CYCLE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add select entities for a config entry."""
    entry_data = entry.runtime_data
    entities: list[SmartThingsEntity] = []
    entities.extend(
        SmartThingsSelectEntity(entry_data.client, device, description, component)
        for capability, description in CAPABILITIES_TO_SELECT.items()
        for device in entry_data.devices.values()
        for component in device.status
        if capability in device.status[component]
        and (
            component == MAIN
            or (
                description.extra_components is not None
                and component in description.extra_components
            )
        )
        and (
            description.capability_ignore_list is None
            or any(
                capability not in device.status[component]
                for capability in description.capability_ignore_list
            )
        )
    )
    entities.extend(
        SmartThingsCycleSelectEntity(entry_data.client, device, description, MAIN)
        for capability, description in CYCLE_CAPABILITIES_TO_SELECT.items()
        for device in entry_data.devices.values()
        if capability in device.status[MAIN]
        and get_cycle_names(device.status[MAIN], capability)
    )
    entities.extend(
        SmartThingsDishwasherWashingOptionSelectEntity(
            entry_data.client,
            device,
            DISHWASHER_WASHING_OPTIONS_TO_SELECT[attribute],
        )
        for device in entry_data.devices.values()
        for component in device.status
        if component == MAIN
        and Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS in device.status[component]
        for attribute in cast(
            list[str],
            device.status[component][Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS][
                Attribute.SUPPORTED_LIST
            ].value,
        )
        if attribute in DISHWASHER_WASHING_OPTIONS_TO_SELECT
    )
    async_add_entities(entities)


class SmartThingsSelectEntity(SmartThingsCycleOptionEntity, SelectEntity):
    """Define a SmartThings select."""

    entity_description: SmartThingsSelectDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
        component: str,
        extra_capabilities: set[Capability] | None = None,
    ) -> None:
        """Initialize the instance."""
        capabilities = {entity_description.key}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        if entity_description.requires_dishwasher_machine_state is not None:
            capabilities.add(Capability.DISHWASHER_OPERATING_STATE)
        if extra_capabilities is not None:
            capabilities.update(extra_capabilities)
        super().__init__(
            client,
            device,
            capabilities,
            component=component,
            cycle_option_key=entity_description.cycle_option_key,
            option_capability=entity_description.key,
            option_status_attribute=entity_description.status_attribute,
        )
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{device.device.device_id}_{component}"
            f"_{entity_description.key}"
            f"_{entity_description.status_attribute}"
            f"_{entity_description.status_attribute}"
        )

    def _device_options(self) -> list[str]:
        """Return the list of raw options from device."""
        return (
            self.get_attribute_value(
                self.entity_description.key, self.entity_description.options_attribute
            )
            or self.entity_description.default_options
            or []
        )

    def _to_ha_options(self, options: list[str]) -> list[str]:
        """Convert device values into Home Assistant values."""
        if self.entity_description.options_map:
            options = [
                self.entity_description.options_map.get(option, option)
                for option in options
            ]
        if self.entity_description.value_is_integer:
            options = [str(option) for option in options]
        return options

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of options."""
        options = self._to_ha_options(self._device_options())
        if (cycle_options := self.cycle_options) is not None:
            allowed_options = self._to_ha_options(cycle_options)
            options = [option for option in options if option in allowed_options]
        return options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        option = self.resolve_cycle_option_value(
            self.get_attribute_value(
                self.entity_description.key, self.entity_description.status_attribute
            )
        )
        if self.entity_description.options_map:
            option = self.entity_description.options_map.get(option, option)
        if self.entity_description.value_is_integer and option is not None:
            option = str(option)
        return option

    def _validate_before_select(self) -> None:
        """Validate that the select can be used."""
        if (
            self.entity_description.requires_remote_control_status
            and self.get_attribute_value(
                Capability.REMOTE_CONTROL_STATUS, Attribute.REMOTE_CONTROL_ENABLED
            )
            == "false"
        ):
            raise ServiceValidationError(
                "Can only be updated when remote control is enabled"
            )

        if (
            self.entity_description.requires_dishwasher_machine_state is not None
            and self.get_attribute_value(
                Capability.DISHWASHER_OPERATING_STATE, Attribute.MACHINE_STATE
            )
            != self.entity_description.requires_dishwasher_machine_state
        ):
            raise ServiceValidationError(
                f"Can only be updated when dishwasher machine state is {self.entity_description.requires_dishwasher_machine_state}"
            )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._validate_before_select()
        new_option: str | int = option
        if self.entity_description.options_map:
            options = self._device_options()
            new_option = next(
                (
                    key
                    for key, value in self.entity_description.options_map.items()
                    if value == option and key in options
                ),
                new_option,
            )
        if self.entity_description.value_is_integer:
            new_option = int(option)
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            new_option,
        )
        self.confirm_cycle_option(new_option)


class SmartThingsCycleSelectEntity(SmartThingsSelectEntity):
    """Define a SmartThings select for a washer/dryer cycle."""

    @property
    def _cycle_codes(self) -> dict[str, str]:
        """Return the supported cycle codes, keyed by their name."""
        names = get_cycle_names(self._internal_state, self.entity_description.key)
        cycles = (
            self.get_attribute_value(
                self.entity_description.key, self.entity_description.options_attribute
            )
            or []
        )
        return {
            names[code]: code
            for cycle in cycles
            if (code := cycle["cycle"].upper()) in names
        }

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of options."""
        return list(self._cycle_codes)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        if (
            code := normalize_cycle_value(
                self.get_attribute_value(
                    self.entity_description.key,
                    self.entity_description.status_attribute,
                )
            )
        ) is None:
            return None
        return get_cycle_names(self._internal_state, self.entity_description.key).get(
            code.upper()
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._validate_before_select()
        # The device only accepts the short uppercase cycle code, the full
        # `<table>_Course_<code>` form reported by the status attribute is ignored.
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            self._cycle_codes[option],
        )


class SmartThingsDishwasherWashingOptionSelectEntity(SmartThingsSelectEntity):
    """Define a SmartThings select for a dishwasher washing option."""

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            client,
            device,
            entity_description,
            MAIN,
            {
                Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            },
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of options."""
        device_options = self.get_attribute_value(
            self.entity_description.key, self.entity_description.options_attribute
        )["settable"]
        selected_course = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE, Attribute.WASHING_COURSE
        )
        course_details = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            Attribute.PREDEFINED_COURSES,
        )
        course_options = set(
            next(
                (
                    detail["options"][self.entity_description.options_attribute][
                        "settable"
                    ]
                    for detail in course_details
                    if detail["courseName"] == selected_course
                ),
                [],
            )
        )
        return [option for option in device_options if option in course_options]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )["value"]

    @override
    def _validate_before_select(self) -> None:
        """Validate that the select can be used."""
        super()._validate_before_select()
        if (
            self.get_attribute_value(
                Capability.DISHWASHER_OPERATING_STATE, Attribute.MACHINE_STATE
            )
            != "stop"
        ):
            raise ServiceValidationError(
                "Can only be updated when dishwasher machine state is stop"
            )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._validate_before_select()
        selected_course = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE, Attribute.WASHING_COURSE
        )
        options = {
            option: self.get_attribute_value(self.entity_description.key, option)[
                "value"
            ]
            for option in self.get_attribute_value(
                self.entity_description.key, Attribute.SUPPORTED_LIST
            )
        }
        options[self.entity_description.options_attribute] = option
        await self.execute_device_command(
            Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
            Command.CANCEL,
            False,
        )
        await self.execute_device_command(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
            Command.SET_WASHING_COURSE,
            selected_course,
        )
        await self.execute_device_command(
            self.entity_description.key,
            Command.SET_OPTIONS,
            options,
        )
