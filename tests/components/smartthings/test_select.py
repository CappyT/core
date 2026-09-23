"""Test for the SmartThings select platform."""

from unittest.mock import AsyncMock, call

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.theater_dryer").state == "stop"

    await trigger_update(
        hass,
        devices,
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )

    assert hass.states.get("select.theater_dryer").state == "run"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.theater_dryer", ATTR_OPTION: "run"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Command.SET_MACHINE_STATE,
        MAIN,
        argument="run",
    )


@pytest.mark.parametrize("device_fixture", ["da_ks_range_0101x"])
async def test_select_option_map(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.vulcan_lamp")
    assert state
    assert state.state == "extra_high"
    assert state.attributes[ATTR_OPTIONS] == [
        "off",
        "extra_high",
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.vulcan_lamp", ATTR_OPTION: "extra_high"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2c3cbaa0-1899-5ddc-7b58-9d657bd48f18",
        Capability.SAMSUNG_CE_LAMP,
        Command.SET_BRIGHTNESS_LEVEL,
        MAIN,
        argument="extraHigh",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option_without_remote_control(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "false",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be updated when remote control is enabled",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.theater_dryer", ATTR_OPTION: "run"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.theater_dryer").state == "stop"

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.OFFLINE
    )

    assert hass.states.get("select.theater_dryer").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.ONLINE
    )

    assert hass.states.get("select.theater_dryer").state == "stop"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("select.theater_dryer").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000003"])
async def test_select_option_as_integer(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option represented as an integer."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.clim_salon_dust_filter_alarm_threshold")
    assert state.state == "500"
    assert all(isinstance(option, str) for option in state.attributes[ATTR_OPTIONS])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.clim_salon_dust_filter_alarm_threshold",
            ATTR_OPTION: "300",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "1e3f7ca2-e005-e1a4-f6d7-bc231e3f7977",
        Capability.SAMSUNG_CE_DUST_FILTER_ALARM,
        Command.SET_ALARM_THRESHOLD,
        MAIN,
        argument=300,
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_select_dishwasher_washing_course_with_wrong_machine_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.DISHWASHER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be updated when dishwasher machine state is stop",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.dishwasher_1_cycle", ATTR_OPTION: "eco"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_select_dishwasher_washing_course(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.dishwasher_1_cycle", ATTR_OPTION: "eco"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7ff318f3-3772-524d-3c9f-72fcd26413ed",
        Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
        Command.SET_WASHING_COURSE,
        MAIN,
        argument="eco",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_select_dishwasher_washing_option_with_wrong_machine_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.DISHWASHER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be updated when dishwasher machine state is stop",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.dishwasher_1_selected_zone", ATTR_OPTION: "lower"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_select_dishwasher_washing_option(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.dishwasher_1_selected_zone", ATTR_OPTION: "lower"},
        blocking=True,
    )
    device_id = "7ff318f3-3772-524d-3c9f-72fcd26413ed"
    devices.execute_device_command.assert_has_calls(
        [
            call(
                device_id,
                Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
                Command.CANCEL,
                MAIN,
                argument=False,
            ),
            call(
                device_id,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
                Command.SET_WASHING_COURSE,
                MAIN,
                argument="eco",
            ),
            call(
                device_id,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
                Command.SET_OPTIONS,
                MAIN,
                argument={
                    "selectedZone": "lower",
                    "speedBooster": False,
                    "sanitize": False,
                },
            ),
        ]
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
async def test_select_options_follow_cycle(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options and value follow the selected cycle."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        WASHER_ID,
        Capability.SAMSUNG_CE_WASHER_CYCLE,
        Attribute.WASHER_CYCLE,
        "Table_02_Course_1E",
    )

    # The device keeps reporting the previous values until it republishes them
    state = hass.states.get("select.machine_a_laver_water_temperature")
    assert state.state == "40"
    assert state.attributes[ATTR_OPTIONS] == ["cold", "20", "30", "40"]
    state = hass.states.get("select.machine_a_laver_spin_level")
    assert state.state == "1200"
    assert state.attributes[ATTR_OPTIONS] == [
        "rinse_hold",
        "no_spin",
        "400",
        "800",
        "1000",
        "1200",
    ]


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
async def test_select_option_locked_by_cycle(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an option the selected cycle locks to its default."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.machine_a_laver_water_temperature")
    assert state.state == "none"
    assert state.attributes[ATTR_OPTIONS] == ["none"]

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.machine_a_laver_water_temperature",
                ATTR_OPTION: "40",
            },
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
async def test_select_option_kept_when_cycle_is_republished(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a republished cycle does not replace the value with its default."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        WASHER_ID,
        Capability.CUSTOM_WASHER_SPIN_LEVEL,
        Attribute.WASHER_SPIN_LEVEL,
        "800",
    )
    await trigger_update(
        hass,
        devices,
        WASHER_ID,
        Capability.SAMSUNG_CE_WASHER_CYCLE,
        Attribute.WASHER_CYCLE,
        "Table_02_Course_1C",
    )

    assert hass.states.get("select.machine_a_laver_spin_level").state == "800"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
async def test_select_cycle(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cycle select sends the cycle code of the named cycle."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.machine_a_laver_cycle").state == "eco_40_60"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.machine_a_laver_cycle", ATTR_OPTION: "cotton"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        WASHER_ID,
        Capability.SAMSUNG_CE_WASHER_CYCLE,
        Command.SET_WASHER_CYCLE,
        MAIN,
        argument="1B",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
@pytest.mark.parametrize(
    "reference_table",
    [
        pytest.param({"id": "Table_00"}, id="unknown_table"),
        pytest.param(None, id="no_table"),
    ],
)
async def test_no_cycle_select_without_known_table(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reference_table: dict[str, str] | None,
) -> None:
    """Test cycle codes are not exposed when their table is not known."""
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_WASHER_CYCLE,
        Attribute.REFERENCE_TABLE,
        reference_table,
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.machine_a_laver_cycle") is None
    assert hass.states.get("select.machine_a_laver_spin_level") is not None


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_01011"])
@pytest.mark.parametrize(
    ("option", "expected_state"),
    [
        pytest.param("1000", "1000", id="value_held_by_cloud"),
        pytest.param("800", "1200", id="value_awaiting_event"),
    ],
)
async def test_select_option_after_cycle_change(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    option: str,
    expected_state: str,
) -> None:
    """Test selecting the value the cloud already holds reports it again."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        WASHER_ID,
        Capability.SAMSUNG_CE_WASHER_CYCLE,
        Attribute.WASHER_CYCLE,
        "Table_02_Course_1E",
    )
    assert hass.states.get("select.machine_a_laver_spin_level").state == "1200"

    # No event follows, as when the cloud already holds the value
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.machine_a_laver_spin_level", ATTR_OPTION: option},
        blocking=True,
    )

    assert hass.states.get("select.machine_a_laver_spin_level").state == expected_state
