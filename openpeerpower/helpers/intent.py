"""Module to coordinate user intentions."""
import logging
import re
from typing import Any, Callable, Dict, Iterable, Optional

import voluptuous as vol

from openpeerpower.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from openpeerpower.core import Context, State, T, callback
from openpeerpower.exceptions import OpenPeerPowerError
from openpeerpower.helpers import config_validation as cv
from openpeerpower.helpers.typing import OpenPeerPowerType
from openpeerpower.loader import bind_opp

_LOGGER = logging.getLogger(__name__)
_SlotsType = Dict[str, Any]

INTENT_TURN_OFF = "OppTurnOff"
INTENT_TURN_ON = "OppTurnOn"
INTENT_TOGGLE = "OppToggle"

SLOT_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

DATA_KEY = "intent"

SPEECH_TYPE_PLAIN = "plain"
SPEECH_TYPE_SSML = "ssml"


@callback
@bind_opp
def async_register(opp: OpenPeerPowerType, handler: "IntentHandler") -> None:
    """Register an intent with Open Peer Power."""
    intents = opp.data.get(DATA_KEY)
    if intents is None:
        intents = opp.data[DATA_KEY] = {}

    assert handler.intent_type is not None, "intent_type cannot be None"

    if handler.intent_type in intents:
        _LOGGER.warning(
            "Intent %s is being overwritten by %s.", handler.intent_type, handler
        )

    intents[handler.intent_type] = handler


@bind_opp
async def async_handle(
    opp: OpenPeerPowerType,
    platform: str,
    intent_type: str,
    slots: Optional[_SlotsType] = None,
    text_input: Optional[str] = None,
    context: Optional[Context] = None,
) -> "IntentResponse":
    """Handle an intent."""
    handler: IntentHandler = opp.data.get(DATA_KEY, {}).get(intent_type)

    if handler is None:
        raise UnknownIntent(f"Unknown intent {intent_type}")

    if context is None:
        context = Context()

    intent = Intent(opp, platform, intent_type, slots or {}, text_input, context)

    try:
        _LOGGER.info("Triggering intent handler %s", handler)
        result = await handler.async_handle(intent)
        return result
    except vol.Invalid as err:
        _LOGGER.warning("Received invalid slot info for %s: %s", intent_type, err)
        raise InvalidSlotInfo(f"Received invalid slot info for {intent_type}") from err
    except IntentHandleError:
        raise
    except Exception as err:
        raise IntentUnexpectedError(f"Error handling {intent_type}") from err


class IntentError(OpenPeerPowerError):
    """Base class for intent related errors."""


class UnknownIntent(IntentError):
    """When the intent is not registered."""


class InvalidSlotInfo(IntentError):
    """When the slot data is invalid."""


class IntentHandleError(IntentError):
    """Error while handling intent."""


class IntentUnexpectedError(IntentError):
    """Unexpected error while handling intent."""


@callback
@bind_opp
def async_match_state(
    opp: OpenPeerPowerType, name: str, states: Optional[Iterable[State]] = None
) -> State:
    """Find a state that matches the name."""
    if states is None:
        states = opp.states.async_all()

    state = _fuzzymatch(name, states, lambda state: state.name)

    if state is None:
        raise IntentHandleError(f"Unable to find an entity called {name}")

    return state


@callback
def async_test_feature(state: State, feature: int, feature_name: str) -> None:
    """Test is state supports a feature."""
    if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & feature == 0:
        raise IntentHandleError(f"Entity {state.name} does not support {feature_name}")


class IntentHandler:
    """Intent handler registration."""

    intent_type: Optional[str] = None
    slot_schema: Optional[vol.Schema] = None
    _slot_schema: Optional[vol.Schema] = None
    platforms: Optional[Iterable[str]] = []

    @callback
    def async_can_handle(self, intent_obj: "Intent") -> bool:
        """Test if an intent can be handled."""
        return self.platforms is None or intent_obj.platform in self.platforms

    @callback
    def async_validate_slots(self, slots: _SlotsType) -> _SlotsType:
        """Validate slot information."""
        if self.slot_schema is None:
            return slots

        if self._slot_schema is None:
            self._slot_schema = vol.Schema(
                {
                    key: SLOT_SCHEMA.extend({"value": validator})
                    for key, validator in self.slot_schema.items()
                },
                extra=vol.ALLOW_EXTRA,
            )

        return self._slot_schema(slots)  # type: ignore

    async def async_handle(self, intent_obj: "Intent") -> "IntentResponse":
        """Handle the intent."""
        raise NotImplementedError()

    def __repr__(self) -> str:
        """Represent a string of an intent handler."""
        return "<{} - {}>".format(self.__class__.__name__, self.intent_type)


def _fuzzymatch(name: str, items: Iterable[T], key: Callable[[T], str]) -> Optional[T]:
    """Fuzzy matching function."""
    matches = []
    pattern = ".*?".join(name)
    regex = re.compile(pattern, re.IGNORECASE)
    for idx, item in enumerate(items):
        match = regex.search(key(item))
        if match:
            # Add index so we pick first match in case same group and start
            matches.append((len(match.group()), match.start(), idx, item))

    return sorted(matches)[0][3] if matches else None


class ServiceIntentHandler(IntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {vol.Required("name"): cv.string}

    def __init__(
        self, intent_type: str, domain: str, service: str, speech: str
    ) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.domain = domain
        self.service = service
        self.speech = speech

    async def async_handle(self, intent_obj: "Intent") -> "IntentResponse":
        """Handle the opp intent."""
        opp = intent_obj.opp
        slots = self.async_validate_slots(intent_obj.slots)
        state = async_match_state(opp, slots["name"]["value"])

        await opp.services.async_call(
            self.domain,
            self.service,
            {ATTR_ENTITY_ID: state.entity_id},
            context=intent_obj.context,
        )

        response = intent_obj.create_response()
        response.async_set_speech(self.speech.format(state.name))
        return response


class Intent:
    """Hold the intent."""

    __slots__ = ["opp", "platform", "intent_type", "slots", "text_input", "context"]

    def __init__(
        self,
        opp: OpenPeerPowerType,
        platform: str,
        intent_type: str,
        slots: _SlotsType,
        text_input: Optional[str],
        context: Context,
    ) -> None:
        """Initialize an intent."""
        self.opp = opp
        self.platform = platform
        self.intent_type = intent_type
        self.slots = slots
        self.text_input = text_input
        self.context = context

    @callback
    def create_response(self) -> "IntentResponse":
        """Create a response."""
        return IntentResponse(self)


class IntentResponse:
    """Response to an intent."""

    def __init__(self, intent: Optional[Intent] = None) -> None:
        """Initialize an IntentResponse."""
        self.intent = intent
        self.speech: Dict[str, Dict[str, Any]] = {}
        self.card: Dict[str, Dict[str, str]] = {}

    @callback
    def async_set_speech(
        self, speech: str, speech_type: str = "plain", extra_data: Optional[Any] = None
    ) -> None:
        """Set speech response."""
        self.speech[speech_type] = {"speech": speech, "extra_data": extra_data}

    @callback
    def async_set_card(
        self, title: str, content: str, card_type: str = "simple"
    ) -> None:
        """Set speech response."""
        self.card[card_type] = {"title": title, "content": content}

    @callback
    def as_dict(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Return a dictionary representation of an intent response."""
        return {"speech": self.speech, "card": self.card}
