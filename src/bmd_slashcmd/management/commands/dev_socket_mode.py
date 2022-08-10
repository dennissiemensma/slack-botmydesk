from pprint import pformat
import traceback

from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import bmd_slashcmd.services
from bmd_slashcmd.dto import UserInfo


class Command(BaseCommand):
    """Based on socket client sample in Slack docs."""

    help = "Dev only: Slack socket client"

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Socket client unsupported in DEBUG mode")

        # Initialize SocketModeClient with an app-level token + WebClient
        client = SocketModeClient(
            # This app-level token will be used only for establishing a connection
            app_token=settings.SLACK_APP_TOKEN,  # xapp-A111-222-xyz
            # You will be using this WebClient for performing Web API calls in listeners
            web_client=WebClient(token=settings.SLACK_BOT_TOKEN),  # xoxb-111-222-xyz
        )

        def process(client: SocketModeClient, req: SocketModeRequest):
            payload_dump = pformat(req.payload, indent=4)
            print(
                f"Incoming request type {req.type} ({req.envelope_id}) with payload:\n{payload_dump}"
            )

            # Ack first (Slack timeout @ 3s).
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            if req.type == "slash_commands":
                self._handle_slash_commands(client, req)
            if req.type == "interactive":
                self._handle_interactivity(client, req)

        # Add a new listener to receive messages from Slack
        # You can add more listeners like this
        client.socket_mode_request_listeners.append(process)
        # Establish a WebSocket connection to the Socket Mode servers
        client.connect()
        # Just not to stop this process
        from threading import Event

        print(
            "Running socket client, now awaiting for someone to interact with us in Slack..."
        )
        Event().wait()

    def _handle_slash_commands(self, client: SocketModeClient, req: SocketModeRequest):
        user_id = req.payload["user_id"]
        result = client.web_client.users_info(user=user_id)
        result.validate()

        user_info = UserInfo(
            slack_user_id=user_id,
            name=result.get("user")["profile"]["first_name"],
            email=result.get("user")["profile"]["email"],
        )

        try:
            command_response = bmd_slashcmd.services.on_slash_command(
                user_info, req.payload
            )
        except Exception as error:
            print(f"Slash command error: {error} ({error.__class__})")

            error_trace = "\n".join(traceback.format_exc().splitlines())
            client.web_client.chat_postEphemeral(
                channel=user_id,
                user=user_id,
                text=f"🤷‍♀️ I'm not sure what to do, sorry! Please tell my creator: 🤨 *{error}*\n\n```{error_trace}```",
            )

        else:
            # @see https://app.slack.com/block-kit-builder/
            result = client.web_client.views_open(
                trigger_id=req.payload["trigger_id"], view=command_response
            )
            result.validate()

    def _handle_interactivity(self, client: SocketModeClient, req: SocketModeRequest):
        user_id = req.payload["user"]["id"]
        result = client.web_client.users_info(user=user_id)
        result.validate()

        user_info = UserInfo(
            slack_user_id=user_id,
            name=result.get("user")["profile"]["first_name"],
            email=result.get("user")["profile"]["email"],
        )

        action_view_id = req.payload["view"]["id"]
        action_view_hash = req.payload["view"]["hash"]

        for current in req.payload["actions"]:
            try:
                interactive_response = bmd_slashcmd.services.on_interactive_action(
                    user_info, current, **req.payload
                )
            except Exception as error:
                print(f"Interactive command error: {error} ({error.__class__})")

                error_trace = "\n".join(traceback.format_exc().splitlines())
                client.web_client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text=f"🤷‍♀️ I'm not sure what to do, sorry! Please tell my creator: 🤨 *{error}*\n\n```{error_trace}```",
                )
            else:
                if interactive_response is not None:
                    # @see https://api.slack.com/surfaces/modals/using#updating_apis
                    result = client.web_client.views_update(
                        view_id=action_view_id,
                        hash=action_view_hash,
                        view=interactive_response,
                    )
                    result.validate()
