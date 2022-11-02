from pprint import pformat
import logging

from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from django.core.management.base import BaseCommand, CommandError
from django.utils.autoreload import run_with_reloader
from django.conf import settings

import bmd_core.services
import bmd_hooks.services.callbacks


botmydesk_logger = logging.getLogger("botmydesk")


class Command(BaseCommand):
    """Based on socket client sample in Slack docs."""

    help = "DEV ONLY: Run when configured using Socket Mode! Process reloads on any local file change."

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Only supported in DEBUG mode")

        # This ensures we have a file watcher locally.
        run_with_reloader(self._run)

    def _run(self):
        socket_mode_client = SocketModeClient(
            # This app-level token will be used only for establishing a connection
            app_token=settings.SLACK_APP_TOKEN,
            web_client=bmd_core.services.slack_web_client(),
        )

        # Add a new listener to receive messages from Slack
        # You can add more listeners like this
        socket_mode_client.socket_mode_request_listeners.append(
            self._on_incoming_request
        )
        # Establish a WebSocket connection to the Socket Mode servers
        socket_mode_client.connect()

        # Just not to stop this process
        from threading import Event

        botmydesk_logger.debug("Listening to Slack in Socket Mode...")
        Event().wait()

    def _on_incoming_request(self, client: SocketModeClient, req: SocketModeRequest):
        payload_dump = pformat(req.payload, indent=2)
        botmydesk_logger.debug(
            f"Socket Mode: Incoming '{req.type}' ({req.envelope_id}) with payload:\n{payload_dump}"
        )

        try:
            callback_module = {
                # Similar mapping as views for incoming webhooks, but without validation.
                "events_api": bmd_hooks.services.callbacks.on_event,
                "slash_commands": bmd_hooks.services.callbacks.on_slash_command,
                "interactive": bmd_hooks.services.callbacks.on_interactivity,
            }[req.type]
        except KeyError:
            botmydesk_logger.error(f"Unsupported request type: {req.type}")
            return

        # Ack first.
        client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        try:
            callback_module(req.payload)
        except Exception as error:
            # Ugly workaround, since exceptions seem to be silent otherwise.
            bmd_hooks.services.callbacks.on_error(error)
            raise
