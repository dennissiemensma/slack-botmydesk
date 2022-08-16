import logging

from django.conf import settings
from django.utils import timezone
from slack_sdk.socket_mode import SocketModeClient

from bmd_core.models import BotMyDeskUser
import bmd_api_client.client


botmydesk_logger = logging.getLogger("botmydesk")


def on_slash_command(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, payload: dict
):
    """Pass me your slash command payload to map."""
    command = payload["command"]
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Incoming slash command '{command}'"
    )

    try:
        service_module = {
            settings.SLACK_SLASHCOMMAND_BMD: handle_slash_command_bmd,
        }[command]
    except KeyError:
        raise NotImplementedError(f"Slash command unknown or misconfigured: {command}")

    service_module(client, botmydesk_user, **payload)


def handle_slash_command_bmd(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    """Called on generic bmd."""
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): User triggered slash command"
    )

    # Unauthorized.
    if not botmydesk_user.authorized_bot():
        botmydesk_logger.info(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Unauthorized, requesting user auth"
        )

        view_data = {
            "type": "modal",
            "callback_id": "bmd-unauthorized-welcome",
            "title": {
                "type": "plain_text",
                "text": f"Greetings {botmydesk_user.name}!",
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "I'm an unofficial assistant bot for BookMyDesk. I will remind you to book or check-in by sending a Slack notification. Many more features may be added later!",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"First, you will need to authorize me to access your BMD account (assuming it's {botmydesk_user.email}).",
                    },
                },
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Authorize BotMyDesk",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "style": "primary",
                            "text": {
                                "type": "plain_text",
                                "text": "Start",
                                "emoji": True,
                            },
                            "value": "authorize_pt1",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_You can revoke my access later at any time by running `{settings.SLACK_SLASHCOMMAND_BMD}` again._",
                    },
                },
            ],
        }
        # @see https://app.slack.com/block-kit-builder/
        result = client.web_client.views_open(
            trigger_id=payload["trigger_id"], view=view_data
        )
        result.validate()
        return

    # Show status.
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): User already authorized"
    )
    profile = bmd_api_client.client.profile(botmydesk_user)
    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=f"Already authorized as {profile['email']}",
    )


def on_interactive_block_action(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, action: dict, **payload
):
    """Respond to user (inter)actions."""
    action_value = action["value"]
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Incoming interactive block action '{action_value}'"
    )

    try:
        service_module = {
            "authorize_pt1": handle_interactive_bmd_authorize_pt1_start,
            "authorize_pt2": handle_interactive_bmd_authorize_pt2_start,
        }[action_value]
    except KeyError:
        raise NotImplementedError(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Interactive block action unknown or misconfigured: {action_value}"
        )

    service_module(client, botmydesk_user, **payload)


def handle_interactive_bmd_authorize_pt1_start(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Rendering part 1 of authorization flow for user"
    )

    view_data = {
        "type": "modal",
        "callback_id": "bmd-modal-authorize-pt2",
        "title": {"type": "plain_text", "text": "Authorize BotMyDesk 1/2"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Click below to request a BookMyDesk login code on behalf of your Slack email address.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {
                            "type": "plain_text",
                            "text": "Request login code",
                            "emoji": True,
                        },
                        "confirm": {
                            "title": {"type": "plain_text", "text": "Are you sure?"},
                            "text": {
                                "type": "mrkdwn",
                                "text": f"Request BookMyDesk login code for {botmydesk_user.email}?",
                            },
                            "confirm": {"type": "plain_text", "text": "Yes"},
                            "deny": {"type": "plain_text", "text": "Cancel"},
                        },
                        "value": "authorize_pt2",
                    }
                ],
            },
        ],
    }
    # @see https://api.slack.com/surfaces/modals/using#updating_apis
    result = client.web_client.views_update(
        view_id=payload["view"]["id"],
        hash=payload["view"]["hash"],
        view=view_data,
    )
    result.validate()


def handle_interactive_bmd_authorize_pt2_start(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Rendering part 2 of authorization flow for user"
    )
    view_data = {
        "type": "modal",
        "callback_id": "bmd-modal-authorize-pt2",
        "title": {"type": "plain_text", "text": "Authorize BotMyDesk 2/2"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Enter your login code received for {botmydesk_user.email} below.",
                },
            },
            {
                "type": "input",
                "block_id": "otp_user_input_block",
                "label": {
                    "type": "plain_text",
                    "text": "Login code",
                },
                "element": {
                    "action_id": "otp_user_input",
                    "focus_on_load": True,
                    "type": "plain_text_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "123456",
                    },
                    "min_length": 6,
                    "max_length": 6,
                },
            },
        ],
        "submit": {"type": "plain_text", "text": "Verify login code"},
    }
    # @see https://api.slack.com/surfaces/modals/using#updating_apis
    result = client.web_client.views_update(
        view_id=payload["view"]["id"],
        hash=payload["view"]["hash"],
        view=view_data,
    )
    result.validate()

    # Request code later so the response above is quick.
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Requesting BookMyDesk login code"
    )
    bmd_api_client.client.request_login_code(email=botmydesk_user.email)


def on_interactive_view_submission(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, payload: dict
):
    """Respond to user (inter)actions."""
    view_callback_id = payload["view"]["callback_id"]
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Incoming interactive view submission '{view_callback_id}'"
    )

    try:
        service_module = {
            "bmd-modal-authorize-pt2": handle_interactive_bmd_authorize_pt2_submit,
        }[view_callback_id]
    except KeyError:
        raise NotImplementedError(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Interactive view submission unknown or misconfigured: {view_callback_id}"
        )

    service_module(client, botmydesk_user, **payload)


def handle_interactive_bmd_authorize_pt2_submit(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Authorizing credentials entered for user"
    )

    otp = payload["view"]["state"]["values"]["otp_user_input_block"]["otp_user_input"][
        "value"
    ]
    json_response = bmd_api_client.client.token_login(
        username=botmydesk_user.email, otp=otp
    )

    botmydesk_user.update(
        access_token=json_response["access_token"],
        access_token_expires_at=timezone.now()
        + timezone.timedelta(minutes=5),  # Presume short TTL. Just refresh often.
        refresh_token=json_response["refresh_token"],
    )
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Successful authorization, updated token credentials"
    )

    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=f"Thanks! You've authorize me. You can always revoke my access later at any time by running `{settings.SLACK_SLASHCOMMAND_BMD}` again.",
    )
