"""Provides device automations for Alarm control panel."""
from typing import List

import voluptuous as vol

from openpeerpower.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from openpeerpower.components.automation import AutomationActionType, state
from openpeerpower.components.device_automation import TRIGGER_BASE_SCHEMA
from openpeerpower.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from openpeerpower.core import CALLBACK_TYPE, OpenPeerPower
from openpeerpower.helpers import config_validation as cv, entity_registry
from openpeerpower.helpers.typing import ConfigType

from . import DOMAIN

TRIGGER_TYPES = {
    "triggered",
    "disarmed",
    "armed_home",
    "armed_away",
    "armed_night",
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(opp: OpenPeerPower, device_id: str) -> List[dict]:
    """List device triggers for Alarm control panel devices."""
    registry = await entity_registry.async_get_registry(opp)
    triggers = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        entity_state = opp.states.get(entry.entity_id)

        # We need a state or else we can't populate the HVAC and preset modes.
        if entity_state is None:
            continue

        supported_features = entity_state.attributes["supported_features"]

        # Add triggers for each entity that belongs to this integration
        triggers += [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "disarmed",
            },
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "triggered",
            },
        ]
        if supported_features & SUPPORT_ALARM_ARM_HOME:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "armed_home",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_AWAY:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "armed_away",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_NIGHT:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "armed_night",
                }
            )

    return triggers


async def async_attach_trigger(
    opp: OpenPeerPower,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    if config[CONF_TYPE] == "triggered":
        from_state = STATE_ALARM_PENDING
        to_state = STATE_ALARM_TRIGGERED
    elif config[CONF_TYPE] == "disarmed":
        from_state = STATE_ALARM_TRIGGERED
        to_state = STATE_ALARM_DISARMED
    elif config[CONF_TYPE] == "armed_home":
        from_state = STATE_ALARM_PENDING
        to_state = STATE_ALARM_ARMED_HOME
    elif config[CONF_TYPE] == "armed_away":
        from_state = STATE_ALARM_PENDING
        to_state = STATE_ALARM_ARMED_AWAY
    elif config[CONF_TYPE] == "armed_night":
        from_state = STATE_ALARM_PENDING
        to_state = STATE_ALARM_ARMED_NIGHT

    state_config = {
        state.CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }
    state_config = state.TRIGGER_SCHEMA(state_config)
    return await state.async_attach_trigger(
        opp, state_config, action, automation_info, platform_type="device"
    )
