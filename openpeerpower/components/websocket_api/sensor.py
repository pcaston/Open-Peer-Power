"""Entity to track connections to websocket API."""

from openpeerpower.core import callback
from openpeerpower.helpers.entity import Entity

from .const import (
    SIGNAL_WEBSOCKET_CONNECTED, SIGNAL_WEBSOCKET_DISCONNECTED,
    DATA_CONNECTIONS)


async def async_setup_platform(
        opp, config, async_add_entities, discovery_info=None):
    """Set up the API streams platform."""
    entity = APICount()

    async_add_entities([entity])


class APICount(Entity):
    """Entity to represent how many people are connected to the stream API."""

    def __init__(self):
        """Initialize the API count."""
        self.count = None

    async def async_added_to_opp(self):
        """Added to opp."""
        self.opp.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_WEBSOCKET_CONNECTED, self._update_count)
        self.opp.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_WEBSOCKET_DISCONNECTED, self._update_count)
        self._update_count()

    @property
    def name(self):
        """Return name of entity."""
        return "Connected clients"

    @property
    def state(self):
        """Return current API count."""
        return self.count

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "clients"

    @callback
    def _update_count(self):
        self.count = self.opp.data.get(DATA_CONNECTIONS, 0)
        self.async_schedule_update_op_state()
