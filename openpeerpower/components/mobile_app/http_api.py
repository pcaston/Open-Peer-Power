"""Provides an HTTP API for mobile_app."""
import secrets
from typing import Dict
import uuid

from aiohttp.web import Request, Response
from nacl.secret import SecretBox

from openpeerpower.components.http import OpenPeerPowerView
from openpeerpower.components.http.data_validator import RequestDataValidator
from openpeerpower.const import CONF_WEBHOOK_ID, HTTP_CREATED

from .const import (
    ATTR_DEVICE_ID,
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_CLOUDHOOK_URL,
    CONF_REMOTE_UI_URL,
    CONF_SECRET,
    CONF_USER_ID,
    DOMAIN,
    REGISTRATION_SCHEMA,
)
from .helpers import supports_encryption


class RegistrationsView(OpenPeerPowerView):
    """A view that accepts registration requests."""

    url = "/api/mobile_app/registrations"
    name = "api:mobile_app:register"

    @RequestDataValidator(REGISTRATION_SCHEMA)
    async def post(self, request: Request, data: Dict) -> Response:
        """Handle the POST request for registration."""
        opp = request.app["opp"]

        webhook_id = secrets.token_hex()

        if opp.components.cloud.async_active_subscription():
            data[
                CONF_CLOUDHOOK_URL
            ] = await opp.components.cloud.async_create_cloudhook(webhook_id)

        data[ATTR_DEVICE_ID] = str(uuid.uuid4()).replace("-", "")

        data[CONF_WEBHOOK_ID] = webhook_id

        if data[ATTR_SUPPORTS_ENCRYPTION] and supports_encryption():
            data[CONF_SECRET] = secrets.token_hex(SecretBox.KEY_SIZE)

        data[CONF_USER_ID] = request["opp_user"].id

        ctx = {"source": "registration"}
        await opp.async_create_task(
            opp.config_entries.flow.async_init(DOMAIN, context=ctx, data=data)
        )

        remote_ui_url = None
        try:
            remote_ui_url = opp.components.cloud.async_remote_ui_url()
        except opp.components.cloud.CloudNotAvailable:
            pass

        return self.json(
            {
                CONF_CLOUDHOOK_URL: data.get(CONF_CLOUDHOOK_URL),
                CONF_REMOTE_UI_URL: remote_ui_url,
                CONF_SECRET: data.get(CONF_SECRET),
                CONF_WEBHOOK_ID: data[CONF_WEBHOOK_ID],
            },
            status_code=HTTP_CREATED,
        )
