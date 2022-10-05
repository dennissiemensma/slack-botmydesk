import logging
import re

from django.conf import settings
from django.utils.translation import gettext

from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_core.services


botmydesk_logger = logging.getLogger("botmydesk")


def handle_slash_command(payload):
    """https://api.slack.com/interactivity/slash-commands"""
    botmydesk_user = bmd_core.services.get_botmydesk_user(payload["user_id"])
    text = payload["text"].strip()

    # Check text, e.g. sub commands
    if not text:
        handle_slash_command_settings(botmydesk_user, payload)
        return

    try:
        sub_command_module = {
            settings.SLACK_SLASHCOMMAND_BMD_DEBUGP: handle_ephemeral_debug_message,
            settings.SLACK_SLASHCOMMAND_BMD_HELP: handle_slash_command_help,
            settings.SLACK_SLASHCOMMAND_BMD_SETTINGS: handle_slash_command_settings,
            settings.SLACK_SLASHCOMMAND_BMD_STATUS: bmd_core.services.handle_slash_command_status,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME: bmd_core.services.handle_user_working_home_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE: bmd_core.services.handle_user_working_in_office_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY: bmd_core.services.handle_user_working_externally_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED: bmd_core.services.handle_user_not_working_today,
            settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS: bmd_core.services.handle_slash_command_list_reservations,
        }[text]
    except KeyError:
        # Help when unknown sub.
        handle_slash_command_help(botmydesk_user, payload)
    else:
        sub_command_module(botmydesk_user, payload)


def handle_slash_command_help(botmydesk_user: BotMyDeskUser, *_):
    help_text = ""

    if botmydesk_user.has_authorized_bot():
        help_text += gettext(
            f"*`{settings.SLACK_SLASHCOMMAND_BMD}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_STATUS}`*\n"
        )
        help_text += gettext(
            "_Show your BookMyDesk status today. Allows you to choose what to book for you today. Similar to notifications sent by BotMyDesk._\n\n\n"
        )
        help_text += gettext(
            f"*`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_RESERVATIONS}`* \n"
        )
        help_text += gettext(
            "_List your upcoming reservations (e.g. coming days)._\n\n\n"
        )
        help_text += gettext(
            "\nYou can use the following commands at any moment, without having to wait for my notification(s) first.\n\n"
        )
        help_text += gettext(
            f"🏡 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME}`* \n"
        )
        help_text += gettext(
            "_Mark today as *working from home*. Will book a home spot for you, if you don't have one yet. No check-in required._\n\n\n"
        )
        help_text += gettext(
            f"🏢 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE}`*\n"
        )
        help_text += gettext(
            "_Mark today as *working from the office*. Only works if you already have a reservation. I will check you in though._\n\n\n"
        )
        help_text += gettext(
            f"🚋 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY}`* \n"
        )
        help_text += gettext(
            "_Mark today as *working externally* (but not at home). Books an *'external' spot* for you if you don't have one yet. Checks you in as well._\n\n\n"
        )
        help_text += gettext(
            f"❌ *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED}`* \n"
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
                "text": gettext(f"{settings.BOTMYDESK_NAME} help"),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "⚙️",
                    },
                    "value": "open_settings",
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": help_text},
            ],
        },
    ]

    bmd_core.services.slack_web_client().chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext(f"{settings.BOTMYDESK_NAME} help"),
        blocks=blocks,
    ).validate()


def handle_slash_command_settings(botmydesk_user: BotMyDeskUser, payload: dict):
    web_client = bmd_core.services.slack_web_client()

    # Unauthorized. Ask to connect.
    if not botmydesk_user.has_authorized_bot():
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
                            f"My name is {settings.BOTMYDESK_NAME}, I'm an unofficial Slack bot for BookMyDesk.\n\nI can remind you to check-in at the office or at home. Making life a bit easier for you!"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": gettext(f"Connecting {settings.BOTMYDESK_NAME}"),
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
                                        f"Request BookMyDesk login code by email for *{botmydesk_user.email}*?\n\n_You can enter it on the next screen._"
                                    ),
                                },
                                "confirm": {
                                    "type": "plain_text",
                                    "text": gettext("Yes, email it"),
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
        web_client.views_open(
            trigger_id=payload["trigger_id"], view=view_data
        ).validate()
        return

    # Check status.
    profile = bmd_api_client.client.me_v3(botmydesk_user)

    title = gettext(f"⚙️ {settings.BOTMYDESK_NAME} preferences")
    view_data = {
        "type": "modal",
        "callback_id": "bmd-authorized-welcome",
        "title": {
            "type": "plain_text",
            "text": title,
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Loading your preferences..."),
                },
            },
        ],
    }
    initial_view_result = web_client.views_open(
        trigger_id=payload["trigger_id"], view=view_data
    )
    initial_view_result.validate()

    full_name = f"{profile.first_name()} {profile.infix()} {profile.last_name()}"
    full_name = re.sub(" +", " ", full_name)

    # Now perform slow calls. Fetch options. @TODO implement
    disabled_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("No"),
        },
        "value": "-",
    }
    notification_options = [
        disabled_option,
        {
            "text": {
                "type": "plain_text",
                "text": gettext("Around 8:00"),
            },
            "value": "8:00",
        },
        {
            "text": {
                "type": "plain_text",
                "text": gettext("Around 9:00"),
            },
            "value": "9:00",
        },
        {
            "text": {
                "type": "plain_text",
                "text": gettext("Around 10:00"),
            },
            "value": "9:00",
        },
    ]
    view_data = {
        "type": "modal",
        "callback_id": "bmd-authorized-welcome",
        "title": {
            "type": "plain_text",
            "text": title,
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Select the days to receive a daily reminder on:"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Notify you on *mondays*?"),
                },
                "accessory": {
                    "action_id": "monday_notification_at",
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select an item"},
                    "options": notification_options,
                    # TODO - fetch from DB
                    "initial_option": disabled_option,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Notify you on *tuesdays*?"),
                },
                "accessory": {
                    "action_id": "tuesday_notification_at",
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select an item"},
                    "options": notification_options,
                    # TODO - fetch from DB
                    "initial_option": disabled_option,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Notify you on *wednesdays*?"),
                },
                "accessory": {
                    "action_id": "wednesday_notification_at",
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select an item"},
                    "options": notification_options,
                    # TODO - fetch from DB
                    "initial_option": disabled_option,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Notify you on *thursdays*?"),
                },
                "accessory": {
                    "action_id": "thursday_notification_at",
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select an item"},
                    "options": notification_options,
                    # TODO - fetch from DB
                    "initial_option": disabled_option,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("Notify you on *fridays*?"),
                },
                "accessory": {
                    "action_id": "friday_notification_at",
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select an item"},
                    "options": notification_options,
                    # TODO - fetch from DB
                    "initial_option": disabled_option,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": "However, should I not *not bother you* when you already seem to have booked and checked in for the day?",
                },
                "accessory": {
                    "type": "checkboxes",
                    "action_id": "dont_bug_me_when_not_needed",
                    # TODO - fetch from DB
                    "options": [
                        {
                            "value": "1",
                            "text": {
                                "type": "plain_text",
                                "text": "Yeah, in that case, don't bug me.",
                            },
                        },
                    ],
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": gettext("Show help info in chat"),
                        },
                        "value": "open_help",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": gettext("Test notification in chat"),
                        },
                        "value": "send_status_notification",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"_Connected to BookMyDesk account of *{full_name}*_"
                    ),
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
                            "text": gettext(f"Disconnect {settings.BOTMYDESK_NAME}"),
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
                                    "This will log me out of your BookMyDesk-account and I won't bother you anymore.\n\n*Disconnect me from your account in BookMyDesk?*"
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
                    },
                ],
            },
        ],
    }
    # @see https://api.slack.com/surfaces/modals/using#updating_apis
    web_client.views_update(
        view_id=initial_view_result["view"]["id"],
        hash=initial_view_result["view"]["hash"],
        view=view_data,
    ).validate()


def handle_ephemeral_debug_message(botmydesk_user: BotMyDeskUser, *_):
    """Debugging only. Post your blocks here."""
    if not settings.DEBUG:
        return

    title = "BotMyDesk debug message"
    bmd_core.services.slack_web_client().chat_postEphemeral(
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
                        "Great! You've connected me to your BookMyDesk-account 👏"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Check out your preferences by clicking the button below, or by going to the 'Home' tab of this bot."
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": gettext(
                                f"⚙️ {settings.BOTMYDESK_NAME} preferences"
                            ),
                        },
                        "value": "open_settings",
                    },
                ],
            },
        ],
    ).validate()
