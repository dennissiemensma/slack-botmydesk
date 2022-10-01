from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from django.conf import settings


def slack_socket_mode_client() -> SocketModeClient:
    return SocketModeClient(
        # This app-level token will be used only for establishing a connection
        app_token=settings.SLACK_APP_TOKEN,  # xapp-A111-222-xyz
        # You will be using this WebClient for performing Web API calls in listeners
        web_client=slack_web_client(),
    )


def slack_web_client() -> WebClient:
    return WebClient(token=settings.SLACK_BOT_TOKEN)  # xoxb-111-222-xyz
