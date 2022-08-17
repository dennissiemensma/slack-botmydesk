import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone
from django.contrib.humanize.templatetags import humanize
from slack_sdk.socket_mode import SocketModeClient

from bmd_api_client.exceptions import BookMyDeskException
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
            settings.SLACK_SLASHCOMMAND_BMD: handle_slash_command,
        }[command]
    except KeyError:
        raise NotImplementedError(f"Slash command unknown or misconfigured: {command}")

    service_module(client, botmydesk_user, **payload)


def handle_slash_command(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, text, **payload
):
    """Called on generic slash command."""
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): User triggered slash command with text '{text}'"
    )

    text = text.strip()

    # Check text, e.g. sub commands
    if text:
        try:
            sub_command_module = {
                settings.SLACK_SLASHCOMMAND_BMD_HELP: handle_slash_command_help,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_1: handle_slash_command_mark_home,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_2: handle_slash_command_mark_home,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_1: handle_slash_command_mark_office,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_2: handle_slash_command_mark_office,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_1: handle_slash_command_mark_externally,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_2: handle_slash_command_mark_externally,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_1: handle_slash_command_mark_cancelled,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_2: handle_slash_command_mark_cancelled,
                settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_1: handle_slash_command_list_reservations,
                settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_2: handle_slash_command_list_reservations,
            }[text.strip()]
        except KeyError:
            # Fallback on failed mapping.
            sub_command_module = handle_slash_command_help

        sub_command_module(client, botmydesk_user, **payload)
        return

    # Just the slash command was entered. Unauthorized.
    if not botmydesk_user.authorized_bot():
        botmydesk_logger.info(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Unauthorized, requesting user auth"
        )

        view_data = {
            "type": "modal",
            "callback_id": "bmd-unauthorized-welcome",
            "title": {
                "type": "plain_text",
                "text": f"Hi {botmydesk_user.name}",
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "My name is BotMyDesk, I'm an unofficial Slack bot for BookMyDesk.\n\nI can remind you to check-in at the office or at home. Making life a bit easier for you!",
                    },
                },
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Connecting BotMyDesk",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"First, you will need to authorize me to access your BookMyDesk-account, presuming it's *{botmydesk_user.email}*.",
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
                                "text": "Connect",
                                "emoji": True,
                            },
                            "confirm": {
                                "title": {
                                    "type": "plain_text",
                                    "text": "Are you sure?",
                                },
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"Request BookMyDesk login code for *{botmydesk_user.email}*?\n\n_You can enter it on the next screen._",
                                },
                                "confirm": {
                                    "type": "plain_text",
                                    "text": "Yes, send it",
                                },
                                "deny": {"type": "plain_text", "text": "No, hold on"},
                            },
                            "value": "send_bookmydesk_login_code",
                        }
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_You can disconnect me later at any time by running `{settings.SLACK_SLASHCOMMAND_BMD}` again._",
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

    # Check status.
    profile = bmd_api_client.client.profile(botmydesk_user)

    view_data = {
        "type": "modal",
        "callback_id": "bmd-authorized-welcome",
        "title": {
            "type": "plain_text",
            "text": "BotMyDesk preferences",
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hi *{profile['first_name']} {profile['infix']} {profile['last_name']}*, how can I help you?",
                },
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Settings",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Loading...",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_Connected: *{profile['email']}*_",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "danger",
                        "text": {
                            "type": "plain_text",
                            "text": "Disconnect BotMyDesk",
                            "emoji": True,
                        },
                        "confirm": {
                            "title": {"type": "plain_text", "text": "Are you sure?"},
                            "text": {
                                "type": "mrkdwn",
                                "text": "This will log me out of your BookMyDesk-account and I won't bother you anymore.\n\n*Revoke my access to your account in BookMyDesk?*",
                            },
                            "confirm": {
                                "type": "plain_text",
                                "text": "Yes, disconnect",
                            },
                            "deny": {
                                "type": "plain_text",
                                "text": "Nevermind, keep connected",
                            },
                        },
                        "value": "revoke_botmydesk",
                    }
                ],
            },
        ],
    }
    # @see https://app.slack.com/block-kit-builder/
    initial_view_result = client.web_client.views_open(
        trigger_id=payload["trigger_id"], view=view_data
    )
    initial_view_result.validate()

    # Now perform slow calls. Fetch options now. @TODO implement
    view_data = {
        "type": "modal",
        "callback_id": "bmd-authorized-welcome",
        "title": {
            "type": "plain_text",
            "text": "BotMyDesk preferences",
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hi *{profile['first_name']} {profile['infix']} {profile['last_name']}*, how can I help you?",
                },
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Settings",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "TODO TODO TODO TODO TODO",  # TODO
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_Connected: *{profile['email']}*_",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "danger",
                        "text": {
                            "type": "plain_text",
                            "text": "Disconnect BotMyDesk",
                            "emoji": True,
                        },
                        "confirm": {
                            "title": {"type": "plain_text", "text": "Are you sure?"},
                            "text": {
                                "type": "mrkdwn",
                                "text": "This will log me out of your BookMyDesk-account and I won't bother you anymore.\n\n*Revoke my access to your account in BookMyDesk?*",
                            },
                            "confirm": {
                                "type": "plain_text",
                                "text": "Yes, disconnect",
                            },
                            "deny": {
                                "type": "plain_text",
                                "text": "Nevermind, keep connected",
                            },
                        },
                        "value": "revoke_botmydesk",
                    }
                ],
            },
        ],
    }
    # @see https://api.slack.com/surfaces/modals/using#updating_apis
    update_result = client.web_client.views_update(
        view_id=initial_view_result["view"]["id"],
        hash=initial_view_result["view"]["hash"],
        view=view_data,
    )
    update_result.validate()


def handle_slash_command_help(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    help_text = ""

    if botmydesk_user.authorized_bot():
        help_text += f"*`{settings.SLACK_SLASHCOMMAND_BMD}`* \n\n"
        help_text += (
            "_Set your (daily) *reminder preferences*. Disconnect BotMyDesk._\n\n\n"
        )
        help_text += "\n> _You can use the following commands at any moment, without having to wait for my notification(s) first:_\n\n"
        help_text += f"🏡 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_2}`* \n"
        help_text += "_Mark today as *working from home*. Will book a home spot for you, if you don't have one yet. No check-in required._\n\n\n"
        help_text += f"🏢 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_2}`* \n"
        help_text += "_Mark today as *working from the office*. Only checks you in if you already have a reservation._\n\n\n"
        help_text += f"🚋 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_2}`* \n"
        help_text += "_Mark today as *working outside the office* (but not at home). Books an *'external' spot* for you (if you don't have one yet). Checks you in as well._\n\n\n"
        help_text += f"❌ *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_2}`* \n"
        help_text += "_*Removes* any pending reservation you have for today or checks you out, if you were checked in already._\n\n\n"
        help_text += f"*`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_2}`* \n"
        help_text += "_List any reservations you have soon (e.g. upcoming days)._\n\n\n"
    else:
        help_text += (
            f"*`{settings.SLACK_SLASHCOMMAND_BMD}`* \n _Connect BotMyDesk._\n\n\n"
        )
        help_text += f"_More commands are available after you've connected your account with *`{settings.SLACK_SLASHCOMMAND_BMD}`*_."

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Just type any of the following command(s):",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": help_text},
            ],
        },
    ]

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Help summary",
        blocks=blocks,
    )
    result.validate()


def handle_slash_command_mark_home(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`",
        )
        result.validate()
        return

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Sorry, not yet implemented 🧑‍💻",
    )
    result.validate()


def handle_slash_command_mark_office(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`",
        )
        result.validate()
        return

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Sorry, not yet implemented 🧑‍💻",
    )
    result.validate()


def handle_slash_command_mark_externally(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`",
        )
        result.validate()
        return

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Sorry, not yet implemented 🧑‍💻",
    )
    result.validate()


def handle_slash_command_mark_cancelled(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`",
        )
        result.validate()
        return

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Sorry, not yet implemented 🧑‍💻",
    )
    result.validate()


def handle_slash_command_list_reservations(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`",
        )
        result.validate()
        return

    profile = bmd_api_client.client.profile(botmydesk_user)
    company_id = profile["companies"][0]["id"]
    company_name = profile["companies"][0]["name"]

    reservations_result = bmd_api_client.client.reservations(botmydesk_user, company_id)
    reservations = reservations_result["result"]["items"]

    from pprint import pprint  # @TODO revert

    pprint(reservations_result, indent=4)  # @TODO revert

    reservations_text = ""

    for current in reservations:
        reservation_start = timezone.datetime.fromisoformat(current["dateStart"])
        natural_time_until_start = humanize.naturaltime(reservation_start)

        if current["status"] in ("checkedOut", "cancelled", "expired"):
            reservations_text += f"\n\n~{reservation_start.strftime('%A %d %B')}: {current['from']} to {current['to']}~ ({current['status']})"
            continue

        # Skip weird ones.
        if current["status"] != "reserved":
            continue

        if current["seat"] is not None and current["seat"]["map"]["name"] == "Extern":
            emoji = "🚋"
            location = current["seat"]["map"]["name"]
        elif current["seat"] is not None and current["type"] == "normal":
            emoji = "🏢"
            location = current["seat"]["map"]["name"]
        elif current["seat"] is None and current["type"] == "home":
            emoji = "🏡"
            location = "Home"
        else:
            emoji = "❓"
            location = "❓"

        reservations_text += f"\n\n{emoji} {reservation_start.strftime('%A %d %B')} at *{location}* from {current['from']} to {current['to']}\n_{natural_time_until_start}_"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Upcoming reservation(s) at {company_name}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": reservations_text,
                }
            ],
        },
    ]

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text="Reservation list",
        blocks=blocks,
    )
    result.validate()


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
            "send_bookmydesk_login_code": handle_interactive_send_bookmydesk_login_code,
            "revoke_botmydesk": handle_interactive_bmd_revoke_botmydesk,
        }[action_value]
    except KeyError:
        raise NotImplementedError(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Interactive block action unknown or misconfigured: {action_value}"
        )

    service_module(client, botmydesk_user, **payload)


def handle_interactive_send_bookmydesk_login_code(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Rendering login code form"
    )
    view_data = {
        "type": "modal",
        "callback_id": "bmd-modal-authorize-login-code",
        "title": {"type": "plain_text", "text": "Connecting BotMyDesk"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Check your mailbox for *{botmydesk_user.email}*. Enter the BookMyDesk login code you've received.",
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
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Sending BookMyDesk login code"
    )
    bmd_api_client.client.request_login_code(email=botmydesk_user.email)


def handle_interactive_bmd_revoke_botmydesk(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Revoking bot access, ending BookMyDesk session"
    )

    view_data = {
        "type": "modal",
        "callback_id": "bmd-disconnected",
        "title": {
            "type": "plain_text",
            "text": "BotMyDesk disconnected",
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"I've disconnected from your BookMyDesk-account. You can reconnect me in the future by running `{settings.SLACK_SLASHCOMMAND_BMD}` again.\n\nBye! 👋",
                },
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

    try:
        # Logout in background.
        bmd_api_client.client.logout(botmydesk_user)
    except BookMyDeskException:
        pass  # Whatever

    # Clear session data.
    botmydesk_user.clear_tokens()


def on_interactive_view_submission(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, payload: dict
) -> Optional[dict]:
    """Respond to user (inter)actions."""
    view_callback_id = payload["view"]["callback_id"]
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Incoming interactive view submission '{view_callback_id}'"
    )

    try:
        service_module = {
            "bmd-modal-authorize-login-code": handle_interactive_bmd_authorize_login_code_submit,
        }[view_callback_id]
    except KeyError:
        raise NotImplementedError(
            f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Interactive view submission unknown or misconfigured: {view_callback_id}"
        )

    return service_module(client, botmydesk_user, **payload)


def handle_interactive_bmd_authorize_login_code_submit(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
) -> Optional[dict]:
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Authorizing credentials entered for user"
    )

    otp = payload["view"]["state"]["values"]["otp_user_input_block"]["otp_user_input"][
        "value"
    ]

    try:
        json_response = bmd_api_client.client.token_login(
            username=botmydesk_user.email, otp=otp
        )
    except BookMyDeskException:
        return {
            "response_action": "errors",
            "errors": {
                "otp_user_input_block": "Error validating your login code. You can try it another time or restart this flow to have a new code sent to you."
            },
        }

    botmydesk_user.update(
        access_token=json_response["access_token"],
        access_token_expires_at=timezone.now()
        + timezone.timedelta(minutes=settings.BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES),
        refresh_token=json_response["refresh_token"],
    )
    botmydesk_logger.info(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Successful authorization, updated token credentials"
    )

    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=f"Great! You've connected me to your BookMyDesk-account. 👏\n*To configure your preferences for BotMyDesk, run `{settings.SLACK_SLASHCOMMAND_BMD}` again.*\nYou can type `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}` for a full list of commands available.\n\n_Also, you can revoke my access at any time by running `{settings.SLACK_SLASHCOMMAND_BMD}` again and click the *Disconnect BotMyDesk* button on the bottom of the screen._",
    )

    return {"response_action": "clear"}
