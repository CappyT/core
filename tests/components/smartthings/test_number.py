"""Test for the SmartThings number platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry

WASHER_ID = "b854ca5f-dc54-140d-6349-758b4d973c41"
DRYER_ID = "3d39866c-7716-5259-44f0-fd7025efd85f"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_set_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.theater_washer_rinse_cycles", ATTR_VALUE: 3},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Command.SET_WASHER_RINSE_CYCLES,
        MAIN,
        argument="3",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Attribute.WASHER_RINSE_CYCLES,
        "3",
    )

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "3"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("number.theater_washer_rinse_cycles").state == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.ONLINE
    )

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("number.theater_washer_rinse_cycles").state == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
async def test_delay_end_without_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the delay end number when the washer reports no remaining time."""
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_WASHER_DELAY_END,
        Attribute.REMAINING_TIME,
        None,
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.machine_a_laver_delay_end").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "device_id", "capability", "value"),
    [
        *(
            pytest.param(
                "da_wm_wm_01011",
                "number.machine_a_laver_delay_end",
                WASHER_ID,
                Capability.SAMSUNG_CE_WASHER_DELAY_END,
                value,
                id=f"washer_{value}",
            )
            for value in (0, 165, 300)
        ),
        # Dryers report no minimum reservable time
        pytest.param(
            "da_wm_wd_01011",
            "number.trockner_delay_end",
            DRYER_ID,
            Capability.SAMSUNG_CE_DRYER_DELAY_END,
            60,
            id="dryer_60",
        ),
    ],
)
async def test_set_delay_end(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    device_id: str,
    capability: Capability,
    value: int,
) -> None:
    """Test setting a delay of 0 or at least the minimum reservable time."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        device_id,
        capability,
        Command.SET_DELAY_TIME,
        MAIN,
        argument=value,
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
@pytest.mark.parametrize(
    ("remote_control", "value", "message"),
    [
        pytest.param(
            "true", 60, "The delay must be 0 or at least 165 minutes", id="too_short"
        ),
        pytest.param(
            "false",
            300,
            "Can only be changed when remote control is enabled",
            id="no_remote_control",
        ),
    ],
)
async def test_set_delay_end_rejected(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    remote_control: str,
    value: int,
    message: str,
) -> None:
    """Test a delay the washer cannot accept is rejected."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        remote_control,
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.machine_a_laver_delay_end", ATTR_VALUE: value},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()
