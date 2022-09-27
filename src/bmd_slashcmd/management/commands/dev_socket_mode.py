from pprint import pformat
import traceback
import logging

from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext
from django.utils.autoreload import run_with_reloader
from django.conf import settings

import bmd_slashcmd.services
import bmd_core.services


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
        # Initialize SocketModeClient with an app-level token + WebClient
        client = SocketModeClient(
            # This app-level token will be used only for establishing a connection
            app_token=settings.SLACK_APP_TOKEN,  # xapp-A111-222-xyz
            # You will be using this WebClient for performing Web API calls in listeners
            web_client=WebClient(token=settings.SLACK_BOT_TOKEN),  # xoxb-111-222-xyz
        )

        def process(client: SocketModeClient, req: SocketModeRequest):
            try:  # Ugly workaround, since exceptions seem to be silent otherwise.
                payload_dump = pformat(req.payload, indent=4)
                botmydesk_logger.debug(
                    f"Incoming request type {req.type} ({req.envelope_id}) with payload:\n{payload_dump}"
                )

                if req.type == "slash_commands":
                    self._handle_slash_commands(client, req)
                if req.type == "interactive":
                    self._handle_interactivity(client, req)
            except Exception as error:
                console_commands_logger.exception(error)
                raise

        # Add a new listener to receive messages from Slack
        # You can add more listeners like this
        client.socket_mode_request_listeners.append(process)
        # Establish a WebSocket connection to the Socket Mode servers
        client.connect()

        # # Set as active.
        # client.web_client.users_setPresence(presence='auto').validate()

        # Just not to stop this process
        from threading import Event

        console_commands_logger.debug(
            "Running socket client, awaiting interaction in Slack..."
        )
        Event().wait()

    def _handle_slash_commands(self, client: SocketModeClient, req: SocketModeRequest):
        user_id = req.payload["user_id"]
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            client, slack_user_id=user_id
        )

        # Ack first (Slack timeout @ 3s).
        client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        try:
            bmd_slashcmd.services.on_slash_command(client, botmydesk_user, req.payload)
        except Exception as error:
            self._on_error(client, user_id, error)
            return

    def _handle_interactivity(self, client: SocketModeClient, req: SocketModeRequest):
        user_id = req.payload["user"]["id"]
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            client, slack_user_id=user_id
        )

        # Respond to view UX.
        if req.payload["type"] == "block_actions":
            # Ack first (Slack timeout @ 3s).
            client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )

            for current in req.payload["actions"]:
                try:
                    (
                        bmd_slashcmd.services.on_interactive_block_action(
                            client, botmydesk_user, current, **req.payload
                        )
                    )
                except Exception as error:
                    self._on_error(client, user_id, error)
                    return

        # Respond to submits.
        if req.payload["type"] == "view_submission":
            # Do NOT ack yet. As we may or may not need to return a different payload.

            try:
                response_payload = bmd_slashcmd.services.on_interactive_view_submission(
                    client, botmydesk_user, req.payload
                )
            except Exception as error:
                self._on_error(client, user_id, error)
                return

            # Conditional response. E.g. for closing modal dialogs or form errors.
            if response_payload is not None:
                botmydesk_logger.debug(f"Sending response payload: {response_payload}")
                client.send_socket_mode_response(
                    SocketModeResponse(
                        envelope_id=req.envelope_id, payload=response_payload
                    )
                )
            else:
                # Just ACK
                client.send_socket_mode_response(
                    SocketModeResponse(envelope_id=req.envelope_id)
                )

    def _on_error(self, client: SocketModeClient, slack_user_id: str, error: Exception):
        error_trace = "\n".join(traceback.format_exc().splitlines())
        console_commands_logger.error(
            f"{slack_user_id}: Unexpected error: {error} ({error.__class__})\n{error_trace}"
        )

        title = gettext("Unexpected error")
        client.web_client.chat_postEphemeral(
            channel=slack_user_id,
            user=slack_user_id,
            text=title,
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": gettext("I'm not sure what to do, sorry! 🤷‍♀"),
                        },
                        {
                            "type": "mrkdwn",
                            "text": gettext(
                                f"_Please tell my creator that the following failed_:\n\n```{error_trace}```"
                            ),
                        },
                        {
                            "type": "mrkdwn",
                            # @see https://api.slack.com/reference/surfaces/formatting#linking-urls
                            "text": gettext(
                                f"_Report to <{settings.BOTMYDESK_SLACK_ID_ON_ERROR}>_ 🤨"
                                if settings.BOTMYDESK_SLACK_ID_ON_ERROR
                                else " "
                            ),
                        },
                    ],
                },
            ],
        ).validate()
