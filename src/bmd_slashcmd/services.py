import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext
from slack_sdk.socket_mode import SocketModeClient

from bmd_api_client.exceptions import BookMyDeskException
from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_core.services


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
                settings.SLACK_SLASHCOMMAND_BMD_SETTINGS: handle_slash_command_settings,
                settings.SLACK_SLASHCOMMAND_BMD_STATUS: bmd_core.services.handle_slash_command_status,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_1: bmd_core.services.handle_user_working_home_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_2: bmd_core.services.handle_user_working_home_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_1: bmd_core.services.handle_user_working_in_office_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_2: bmd_core.services.handle_user_working_in_office_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_1: bmd_core.services.handle_user_working_externally_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_2: bmd_core.services.handle_user_working_externally_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_1: bmd_core.services.handle_user_not_working_today,
                settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_2: bmd_core.services.handle_user_not_working_today,
                settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_1: bmd_core.services.handle_slash_command_list_reservations,
                settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_2: bmd_core.services.handle_slash_command_list_reservations,
            }[text.strip()]
        except KeyError:
            # Help when unknown sub.
            handle_slash_command_help(client, botmydesk_user, **payload)
        else:
            sub_command_module(client, botmydesk_user, **payload)

        return

    # Status or settings when no parameters given.
    if botmydesk_user.authorized_bot():
        bmd_core.services.handle_slash_command_status(client, botmydesk_user, **payload)
    else:
        handle_slash_command_settings(client, botmydesk_user, **payload)


def handle_slash_command_help(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    help_text = ""

    if botmydesk_user.authorized_bot():
        help_text += gettext(
            f"*`{settings.SLACK_SLASHCOMMAND_BMD}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_STATUS}`*\n"
        )
        help_text += gettext(
            "_Show your BookMyDesk status today. Allows you to choose what to book for you today. Similar to notifications sent by BotMyDesk._\n\n\n"
        )
        help_text += gettext(
            f"*`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS_2}`* \n"
        )
        help_text += gettext(
            "_List your upcoming reservations (e.g. coming days)._\n\n\n"
        )
        help_text += gettext(
            "\nYou can use the following commands at any moment, without having to wait for my notification(s) first.*\n\n"
        )
        help_text += gettext(
            f"🏡 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_2}`* \n"
        )
        help_text += gettext(
            "_Mark today as *working from home*. Will book a home spot for you, if you don't have one yet. No check-in required._\n\n\n"
        )
        help_text += gettext(
            f"🏢 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_2}`* \n"
        )
        help_text += gettext(
            "_Mark today as *working from the office*. Only works if you already have a reservation. I will check you in though._\n\n\n"
        )
        help_text += gettext(
            f"🚋 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_2}`* \n"
        )
        help_text += gettext(
            "_Mark today as *working externally* (but not at home). Books an *'external' spot* for you if you don't have one yet. Checks you in as well._\n\n\n"
        )
        help_text += gettext(
            f"❌ *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_1}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_2}`* \n"
        )
        help_text += gettext(
            "_*Removes* any pending reservation you have for today or checks you out (if you were checked in already)._\n ⚠️ _Care, will be applied instantly without confirmation._\n\n\n"
        )
    else:
        help_text += gettext(
            f"_More commands will be available after you've connected your account by typing *`{settings.SLACK_SLASHCOMMAND_BMD}`*_."
        )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": gettext("BotMyDesk help"),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": gettext(
                    "_Click the button to the right for preferences or (dis)connecting BotMyDesk._\n\n\n"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": gettext("BotMyDesk settings"),
                },
                "value": "open_settings",
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
        text=gettext("BotMyDesk help"),
        blocks=blocks,
    )
    result.validate()


def handle_slash_command_settings(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    """Modal settings."""

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
                "text": gettext(f"Hi {botmydesk_user.name}"),
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "My name is BotMyDesk, I'm an unofficial Slack bot for BookMyDesk.\n\nI can remind you to check-in at the office or at home. Making life a bit easier for you!"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": gettext("Connecting BotMyDesk"),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            f"First, you will need to authorize me to access your BookMyDesk-account, presuming it's *{botmydesk_user.email}*."
                        ),
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
                                "text": gettext("Connect"),
                                "emoji": True,
                            },
                            "confirm": {
                                "title": {
                                    "type": "plain_text",
                                    "text": gettext("Are you sure?"),
                                },
                                "text": {
                                    "type": "mrkdwn",
                                    "text": gettext(
                                        f"Request BookMyDesk login code for *{botmydesk_user.email}*?\n\n_You can enter it on the next screen._"
                                    ),
                                },
                                "confirm": {
                                    "type": "plain_text",
                                    "text": gettext("Yes, send it"),
                                },
                                "deny": {
                                    "type": "plain_text",
                                    "text": gettext("No, hold on"),
                                },
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
                        "text": gettext(
                            f"_You can disconnect me later at any time by running `{settings.SLACK_SLASHCOMMAND_BMD}` again._"
                        ),
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
    profile = bmd_api_client.client.me_v3(botmydesk_user)

    view_data = {
        "type": "modal",
        "callback_id": "bmd-authorized-welcome",
        "title": {
            "type": "plain_text",
            "text": gettext("BotMyDesk settings"),
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Loading..."),
                },
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
            "text": gettext("BotMyDesk settings"),
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"_Connected to: *{profile.first_name} {profile.infix} {profile.last_name}* ({profile.email})_"
                    ),
                },
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": gettext("Preferences"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Select *which working day(s)* to receive daily notifications on:"
                    ),
                },
                "accessory": {
                    "type": "checkboxes",
                    "options": [
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext("Mondays"),
                            },  # TODO - fetch from DB
                            "value": "notify_me_on_mondays",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext("Tuesdays"),
                            },  # TODO - fetch from DB
                            "value": "notify_me_on_tuesdays",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext("Wednesdays"),
                            },  # TODO - fetch from DB
                            "value": "notify_me_on_wednesdays",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext("Thursdays"),
                            },  # TODO - fetch from DB
                            "value": "notify_me_on_thursdays",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext("Fridays"),
                            },  # TODO - fetch from DB
                            "value": "notify_me_on_fridays",
                        },
                    ],
                    "action_id": "daily_notification_days",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Select *what time* to receive daily notification on:"
                    ),
                },
                "accessory": {
                    "type": "timepicker",
                    "initial_time": "09:00",  # TODO - fetch from DB
                    "action_id": "daily_notification_time",
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "danger",
                        "text": {
                            "type": "plain_text",
                            "text": gettext("Disconnect BotMyDesk"),
                            "emoji": True,
                        },
                        "confirm": {
                            "title": {
                                "type": "plain_text",
                                "text": gettext("Are you sure?"),
                            },
                            "text": {
                                "type": "mrkdwn",
                                "text": gettext(
                                    "This will log me out of your BookMyDesk-account and I won't bother you anymore.\n\n*Revoke my access to your account in BookMyDesk?*"
                                ),
                            },
                            "confirm": {
                                "type": "plain_text",
                                "text": gettext("Yes, disconnect"),
                            },
                            "deny": {
                                "type": "plain_text",
                                "text": gettext("Nevermind, keep connected"),
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


def on_interactive_block_action(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, action: dict, **payload
):
    """Respond to user (inter)actions. Some are follow-ups, some are aliases."""
    action_value = action["value"]
    botmydesk_logger.debug(
        f"{botmydesk_user.slack_user_id} ({botmydesk_user.email}): Incoming interactive block action '{action_value}'"
    )

    try:
        service_module = {
            "send_bookmydesk_login_code": handle_interactive_send_bookmydesk_login_code,
            "revoke_botmydesk": handle_interactive_bmd_revoke_botmydesk,
            "open_settings": handle_slash_command_settings,  # Alias
            "mark_working_from_home_today": bmd_core.services.handle_user_working_home_today,
            "mark_working_at_the_office_today": bmd_core.services.handle_user_working_in_office_today,
            "mark_working_externally_today": bmd_core.services.handle_user_working_externally_today,
            "mark_not_working_today": bmd_core.services.handle_user_not_working_today,
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
        "title": {"type": "plain_text", "text": gettext("Connecting BotMyDesk")},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"Check your mailbox for *{botmydesk_user.email}*. Enter the BookMyDesk login code you've received."
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "otp_user_input_block",
                "label": {
                    "type": "plain_text",
                    "text": gettext("Login code"),
                },
                "element": {
                    "action_id": "otp_user_input",
                    "focus_on_load": True,
                    "type": "plain_text_input",
                    "dispatch_action_config": {
                        "trigger_actions_on": ["on_enter_pressed"]
                    },
                    "placeholder": {
                        "type": "plain_text",
                        "text": "123456",
                    },
                    "min_length": 6,
                    "max_length": 6,
                },
            },
        ],
        "submit": {"type": "plain_text", "text": gettext("Verify login code")},
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
            "text": gettext("BotMyDesk disconnected"),
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"I've disconnected from your BookMyDesk-account. You can reconnect me in the future by running `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_SETTINGS}` again.\n\nBye! 👋"
                    ),
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

    # Clear session data. For now, we're not deleting the user to keep their preferences.
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
                "otp_user_input_block": gettext(
                    "Error validating your login code. You can try it another time or restart this flow to have a new code sent to you."
                )
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

    title = gettext("BotMyDesk connected!")
    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
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
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"Great! You've connected me to your BookMyDesk-account 👏\n\nI will now summarize the commands you can use, which is similar to typing *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`*"
                    ),
                },
            },
        ],
    )

    # Just display the default help info.
    handle_slash_command_help(client, botmydesk_user)

    return {"response_action": "clear"}
