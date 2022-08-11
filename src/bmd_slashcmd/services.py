from typing import Optional

from django.conf import settings

from bmd_slashcmd.dto import UserInfo
import bmd_api_client.client


def on_slash_command(user_info: UserInfo, payload: dict) -> dict:
    """Pass me your slash command payload to map."""
    command = payload["command"]
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Incoming slash command '{command}'"
    )

    try:
        service_module = {
            settings.SLACK_SLASHCOMMAND_BMD: handle_slash_command_bmd,
        }[command]
    except KeyError:
        raise NotImplementedError(f"Slash command unknown or misconfigured: {command}")

    return service_module(user_info, **payload)


def handle_slash_command_bmd(user_info: UserInfo, **payload) -> dict:
    """Called on generic bmd."""
    print(
        f"{user_info.slack_user_id} ({user_info.email}): User triggered slash command"
    )

    # TODO: Check bot auth state for dynamic stuff later

    # Unauthorized.
    return {
        "type": "modal",
        "callback_id": "bmd-unauthorized-welcome",
        "title": {"type": "plain_text", "text": f"Greetings {user_info.name}!"},
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
                    "text": f"First, you will need to authorize me to access your BMD account (assuming it's {user_info.email}).",
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


def on_interactive_block_action(
    user_info: UserInfo, action: dict, **payload
) -> Optional[dict]:
    """Respond to user (inter)actions."""
    action_value = action["value"]
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Incoming interactive block action '{action_value}'"
    )

    try:
        service_module = {
            "authorize_pt1": handle_interactive_bmd_authorize_pt1_start,
            "authorize_pt2": handle_interactive_bmd_authorize_pt2_start,
        }[action_value]
    except KeyError:
        raise NotImplementedError(
            f"{user_info.slack_user_id} ({user_info.email}): Interactive block action unknown or misconfigured: {action_value}"
        )

    return service_module(user_info, **action)


def handle_interactive_bmd_authorize_pt1_start(
    user_info: UserInfo, **payload
) -> Optional[dict]:
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Rendering part 1 of authorization flow for user"
    )

    return {
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
                                "text": f"Request BookMyDesk login code for {user_info.email}?",
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


def handle_interactive_bmd_authorize_pt2_start(
    user_info: UserInfo, **payload
) -> Optional[dict]:
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Requesting BookMyDesk login code"
    )
    bmd_api_client.client.request_login_code(email=user_info.email)  # TODO enable

    print(
        f"{user_info.slack_user_id} ({user_info.email}): Rendering part 2 of authorization flow for user"
    )
    return {
        "type": "modal",
        "callback_id": "bmd-modal-authorize-pt2",
        "title": {"type": "plain_text", "text": "Authorize BotMyDesk 2/2"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Enter your login code received for {user_info.email} below.",
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


def on_interactive_view_submission(
    user_info: UserInfo, payload: dict
) -> Optional[dict]:
    """Respond to user (inter)actions."""
    view_callback_id = payload["view"]["callback_id"]
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Incoming interactive view submission '{view_callback_id}'"
    )

    try:
        service_module = {
            "bmd-modal-authorize-pt2": handle_interactive_bmd_authorize_pt2_submit,
        }[view_callback_id]
    except KeyError:
        raise NotImplementedError(
            f"{user_info.slack_user_id} ({user_info.email}): Interactive view submission unknown or misconfigured: {view_callback_id}"
        )

    return service_module(user_info, **payload)


def handle_interactive_bmd_authorize_pt2_submit(
    user_info: UserInfo, **payload
) -> Optional[dict]:
    print(
        f"{user_info.slack_user_id} ({user_info.email}): Authorizing credentials entered for user"
    )

    # otp = payload["view"]["state"]["values"]["otp_user_input_block"]["otp_user_input"][
    #     "value"
    # ]
    # json_response = bmd_api_client.client.token_login(username=user_info.email, otp=otp)
    # @TODO Store in DB
    return
