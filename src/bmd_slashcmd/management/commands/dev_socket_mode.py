from decouple import config
from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import bmd_slashcmd.services


class Command(BaseCommand):
    """Based on socket client sample in Slack docs."""

    help = "Dev only: Slack socket client"

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Socket client unsupported in DEBUG mode")

        # Initialize SocketModeClient with an app-level token + WebClient
        client = SocketModeClient(
            # This app-level token will be used only for establishing a connection
            app_token=config("SLACK_APP_TOKEN", cast=str),  # xapp-A111-222-xyz
            # You will be using this WebClient for performing Web API calls in listeners
            web_client=WebClient(
                token=config("SLACK_BOT_TOKEN", cast=str)
            ),  # xoxb-111-222-xyz
        )

        from slack_sdk.socket_mode.response import SocketModeResponse
        from slack_sdk.socket_mode.request import SocketModeRequest

        def process(client: SocketModeClient, req: SocketModeRequest):
            print("Incoming sevent", req.type)

            if req.type == "slash_commands":
                print("Incoming slash command...")
                try:
                    bmd_slashcmd.services.on_slash_command(req.payload)
                except Exception as error:
                    print("Slash command error", error.__class__, error)
                    return

            if req.type == "events_api":
                # Acknowledge the request anyway
                response = SocketModeResponse(envelope_id=req.envelope_id)
                client.send_socket_mode_response(response)

                # Add a reaction to the message if it's a new message
                if (
                    req.payload["event"]["type"] == "message"
                    and req.payload["event"].get("subtype") is None
                ):
                    client.web_client.reactions_add(
                        name="eyes",
                        channel=req.payload["event"]["channel"],
                        timestamp=req.payload["event"]["ts"],
                    )
            if req.type == "interactive" and req.payload.get("type") == "shortcut":
                if req.payload["callback_id"] == "hello-shortcut":
                    # Acknowledge the request
                    response = SocketModeResponse(envelope_id=req.envelope_id)
                    client.send_socket_mode_response(response)
                    # Open a welcome modal
                    client.web_client.views_open(
                        trigger_id=req.payload["trigger_id"],
                        view={
                            "type": "modal",
                            "callback_id": "hello-modal",
                            "title": {"type": "plain_text", "text": "Greetings!"},
                            "submit": {"type": "plain_text", "text": "Good Bye"},
                            "blocks": [
                                {
                                    "type": "section",
                                    "text": {"type": "mrkdwn", "text": "Hello!"},
                                }
                            ],
                        },
                    )

            if (
                req.type == "interactive"
                and req.payload.get("type") == "view_submission"
            ):
                if req.payload["view"]["callback_id"] == "hello-modal":
                    # Acknowledge the request and close the modal
                    response = SocketModeResponse(envelope_id=req.envelope_id)
                    client.send_socket_mode_response(response)

        # Add a new listener to receive messages from Slack
        # You can add more listeners like this
        client.socket_mode_request_listeners.append(process)
        # Establish a WebSocket connection to the Socket Mode servers
        client.connect()
        # Just not to stop this process
        from threading import Event

        print(
            "Running socket client, now awaiting for something to interact with us in Slack..."
        )
        Event().wait()
