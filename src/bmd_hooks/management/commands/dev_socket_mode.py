from pprint import pformat
import traceback
import logging

from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext
from django.utils.autoreload import run_with_reloader
from django.conf import settings

import bmd_core.services
import bmd_hooks.services

console_commands_logger = logging.getLogger("console_commands")
botmydesk_logger = logging.getLogger("botmydesk")


class Command(BaseCommand):
    """Based on socket client sample in Slack docs."""

    help = "Dev only: Slack socket client. Reloads on local file change!"

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Socket client only supported in DEBUG mode")

        # This ensures we have a file watcher locally.
        run_with_reloader(self._run)

    def _run(self):
        socket_mode_client = bmd_hooks.services.slack_socket_mode_client()

        def process(socket_mode_client: SocketModeClient, req: SocketModeRequest):
            try:  # Ugly workaround, since exceptions seem to be silent otherwise.
                payload_dump = pformat(req.payload, indent=4)
                botmydesk_logger.debug(
                    f"Socket Mode: Incoming '{req.type}' ({req.envelope_id}) with payload:\n{payload_dump}"
                )

                if req.type == "slash_commands":
                    self._handle_slash_commands(socket_mode_client, req)
                elif req.type == "interactive":
                    self._handle_interactivity(socket_mode_client, req)
                elif req.type == "events_api":
                    self._handle_events(socket_mode_client, req)
                else:
                    botmydesk_logger.error(f"Unhandled '{req.type}'")

            except Exception as error:
                console_commands_logger.exception(error)
                raise

        # Add a new listener to receive messages from Slack
        # You can add more listeners like this
        socket_mode_client.socket_mode_request_listeners.append(process)
        # Establish a WebSocket connection to the Socket Mode servers
        socket_mode_client.connect()

        # # Set as active.
        # web_client.users_setPresence(presence='auto').validate()

        # Just not to stop this process
        from threading import Event

        console_commands_logger.debug(
            "Running socket client, awaiting interaction in Slack..."
        )
        Event().wait()

    def _handle_events(
        self, socket_mode_client: SocketModeClient, req: SocketModeRequest
    ):
        # Ack first (Slack timeout @ 3s).
        socket_mode_client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        try:
            bmd_hooks.services.on_event(req.payload)
        except Exception as error:
            self._on_error(socket_mode_client, error)
            return

    def _handle_slash_commands(
        self, socket_mode_client: SocketModeClient, req: SocketModeRequest
    ):
        user_id = req.payload["user_id"]
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            socket_mode_client.web_client, slack_user_id=user_id
        )

        # Ack first (Slack timeout @ 3s).
        socket_mode_client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        try:
            bmd_hooks.services.on_slash_command(
                socket_mode_client.web_client, botmydesk_user, req.payload
            )
        except Exception as error:
            self._on_error(socket_mode_client, error)
            return

    def _handle_interactivity(
        self, socket_mode_client: SocketModeClient, req: SocketModeRequest
    ):
        user_id = req.payload["user"]["id"]
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            socket_mode_client.web_client, slack_user_id=user_id
        )

        # Respond to view UX.
        if req.payload["type"] == "block_actions":
            # Ack first (Slack timeout @ 3s).
            socket_mode_client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )

            for current_action in req.payload["actions"]:
                try:
                    (
                        bmd_hooks.services.on_interactive_block_action(
                            socket_mode_client.web_client,
                            botmydesk_user,
                            current_action,
                            **req.payload,
                        )
                    )
                except Exception as error:
                    self._on_error(socket_mode_client, error)
                    return

        # Respond to submits.
        if req.payload["type"] == "view_submission":
            # Do NOT ack yet. As we may or may not need to return a different payload.

            try:
                response_payload = bmd_hooks.services.on_interactive_view_submission(
                    socket_mode_client.web_client, botmydesk_user, req.payload
                )
            except Exception as error:
                self._on_error(socket_mode_client, error)
                return

            # Conditional response. E.g. for closing modal dialogs or form errors.
            if response_payload is not None:
                botmydesk_logger.debug(f"Sending response payload: {response_payload}")
                socket_mode_client.send_socket_mode_response(
                    SocketModeResponse(
                        envelope_id=req.envelope_id, payload=response_payload
                    )
                )
            else:
                # Just ACK
                socket_mode_client.send_socket_mode_response(
                    SocketModeResponse(envelope_id=req.envelope_id)
                )

    def _on_error(self, socket_mode_client: SocketModeClient, error: Exception):
        error_trace = "\n".join(traceback.format_exc().splitlines())
        console_commands_logger.error(
            f"Unexpected error: {error} ({error.__class__})\n{error_trace}"
        )

        # title = gettext("Unexpected error")
        # socket_mode_client.web_client.chat_postEphemeral(
        #     channel=slack_user_id,
        #     user=slack_user_id,
        #     text=title,
        #     blocks=[
        #         {
        #             "type": "header",
        #             "text": {
        #                 "type": "plain_text",
        #                 "text": title,
        #             },
        #         },
        #         {
        #             "type": "context",
        #             "elements": [
        #                 {
        #                     "type": "mrkdwn",
        #                     "text": gettext("I'm not sure what to do, sorry! 🤷‍♀"),
        #                 },
        #                 {
        #                     "type": "mrkdwn",
        #                     "text": gettext(
        #                         f"_Please tell my creator that the following failed_:\n\n```{error_trace}```"
        #                     ),
        #                 },
        #                 {
        #                     "type": "mrkdwn",
        #                     # @see https://api.slack.com/reference/surfaces/formatting#linking-urls
        #                     "text": gettext(
        #                         f"_Report to <{settings.BOTMYDESK_SLACK_ID_ON_ERROR}>_ 🤨"
        #                         if settings.BOTMYDESK_SLACK_ID_ON_ERROR
        #                         else " "
        #                     ),
        #                 },
        #             ],
        #         },
        #     ],
        # ).validate()
