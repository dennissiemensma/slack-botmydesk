import datetime
import logging
import re

from django.conf import settings
from django.utils.translation import gettext

from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_core.services


botmydesk_logger = logging.getLogger("botmydesk")


def handle_slash_command(botmydesk_user: BotMyDeskUser, payload: dict):
    """https://api.slack.com/interactivity/slash-commands"""
    text = payload["text"].strip()

    # Check text, e.g. sub commands
    if not text:
        # Default to this when no arguments.
        handle_slash_command_help(botmydesk_user, payload)
        return

    try:
        sub_command_module = {
            settings.SLACK_SLASHCOMMAND_BMD_DEBUG: handle_ephemeral_debug_message,
            settings.SLACK_SLASHCOMMAND_BMD_HELP: handle_slash_command_help,
            settings.SLACK_SLASHCOMMAND_BMD_SETTINGS: handle_preferences_gui,
            settings.SLACK_SLASHCOMMAND_BMD_STATUS: handle_status_notification,
            settings.SLACK_SLASHCOMMAND_BMD_STATUS_ALIAS_2: handle_status_notification,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME: bmd_core.services.handle_user_working_home_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_ALIAS_2: bmd_core.services.handle_user_working_home_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE: bmd_core.services.handle_user_working_in_office_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_ALIAS_2: bmd_core.services.handle_user_working_in_office_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY: bmd_core.services.handle_user_working_externally_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_ALIAS_2: bmd_core.services.handle_user_working_externally_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED: bmd_core.services.handle_user_not_working_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_2: bmd_core.services.handle_user_not_working_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_3: bmd_core.services.handle_user_not_working_today,
            settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_4: bmd_core.services.handle_user_not_working_today,
        }[text]
    except KeyError:
        # Help when unknown sub.
        handle_slash_command_help(botmydesk_user, payload)
    else:
        sub_command_module(botmydesk_user, payload)


def handle_slash_command_help(botmydesk_user: BotMyDeskUser, *_):
    help_text = ""

    if botmydesk_user.has_authorized_bot():
        help_text += (
            "\nYou can *type* the following commands at any moment, at any chat.\n\n"
        )
        help_text += f"*`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_STATUS}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_STATUS_ALIAS_2}`*\n"
        help_text += "_Show your BookMyDesk status today. Allows you to choose what to book for you today. Similar to notifications sent by BotMyDesk._\n\n\n"
        help_text += f"🏡 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME_ALIAS_2}`* \n"
        help_text += "_Mark today as *working from home*. Will book a home spot for you, if you don't have one yet. No check-in required._\n\n\n"
        help_text += f"🏢 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE_ALIAS_2}`* \n"
        help_text += "_Mark today as *working from the office*. Only works if you already have a reservation. I will check you in though._\n\n\n"

        if settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME:
            help_text += f"🚋 *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY_ALIAS_2}`* \n"
            help_text += "_Mark today as *working externally* (but not at home). Books an *'external' spot* for you if you don't have one yet. Checks you in as well._\n\n\n"

        help_text += f"❌ *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED}`* or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_2}`*  or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_3}`*  or *`{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED_ALIAS_4}`* \n"
        help_text += "_*Removes* any pending reservation you have for today or, if you were checked in already, checks you out._\n\n ⚠️ _Care, each will be *applied instantly without confirmation*._\n\n\n"
    else:
        help_text += f"_More commands will be available after you've connected your account by typing *`{settings.SLACK_SLASHCOMMAND_BMD}`*_."

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{settings.BOTMYDESK_NAME} help",
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
                    "value": "open_preferences",
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
        text=f"{settings.BOTMYDESK_NAME} help",
        blocks=blocks,
    ).validate()


def handle_preferences_gui(botmydesk_user: BotMyDeskUser, payload: dict):
    web_client = bmd_core.services.slack_web_client()

    # Unauthorized. Ask to connect first.
    if not botmydesk_user.has_authorized_bot():
        view_data = {
            "type": "modal",
            "callback_id": "bmd-unauthorized-welcome",
            "title": {
                "type": "plain_text",
                "text": gettext("Hi") + f"{botmydesk_user.slack_name} 👋",
            },
            "blocks": [
                {"type": "divider"},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": gettext("Connecting BookMyDesk to")
                        + f" {settings.BOTMYDESK_NAME}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "First, you will need to authorize me to access your BookMyDesk-account, presuming it's your Slack email address."
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
                                        "Request BookMyDesk login code by email for"
                                    )
                                    + f" *{botmydesk_user.slack_email}*?\n\n"
                                    + gettext(
                                        "_You can enter the code on the next screen._"
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
                            "_You can disconnect me later at any time by accessing these preferences again._"
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

    title = "⚙️ " + gettext("Preferences")
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
                    "text": gettext("_Loading your preferences..._"),
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

    # Now perform slow calls. Fetch options.
    botmydesk_user.refresh_from_db()

    disabled_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("No"),
        },
        "value": "-",
    }
    at_7am_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("Around 7:00"),
        },
        "value": "07:00",
    }
    at_8am_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("Around 8:00"),
        },
        "value": "08:00",
    }
    at_830am_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("Around 8:30"),
        },
        "value": "08:30",
    }
    at_9am_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("Around 9:00"),
        },
        "value": "09:00",
    }
    notification_options = [
        disabled_option,
        at_7am_option,
        at_8am_option,
        at_830am_option,
        at_9am_option,
    ]
    notification_preference_mapping = {
        None: disabled_option,
        datetime.time(hour=7): at_7am_option,
        datetime.time(hour=8): at_8am_option,
        datetime.time(hour=8, minute=30): at_830am_option,
        datetime.time(hour=9): at_9am_option,
    }
    initial_monday_preference = (
        notification_preference_mapping[
            botmydesk_user.preferred_notification_time_on_mondays
        ]
        or disabled_option
    )
    initial_tuesday_preference = (
        notification_preference_mapping[
            botmydesk_user.preferred_notification_time_on_tuesdays
        ]
        or disabled_option
    )
    initial_wednesday_preference = (
        notification_preference_mapping[
            botmydesk_user.preferred_notification_time_on_wednesdays
        ]
        or disabled_option
    )
    initial_thursday_preference = (
        notification_preference_mapping[
            botmydesk_user.preferred_notification_time_on_thursdays
        ]
        or disabled_option
    )
    initial_friday_preference = (
        notification_preference_mapping[
            botmydesk_user.preferred_notification_time_on_fridays
        ]
        or disabled_option
    )

    # smart_notifications_enabled_option = {
    #     "text": {
    #         "type": "plain_text",
    #         "text": gettext("Yes, skip"),
    #     },
    #     "value": "1",
    # }
    # smart_notifications_disabled_option = {
    #     "text": {
    #         "type": "plain_text",
    #         "text": gettext("No, notify me"),
    #     },
    #     "value": "0",
    # }

    dutch_locale_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("Dutch (locales broken)"),
        },
        "value": BotMyDeskUser.DUTCH_LOCALE,
    }
    english_locale_option = {
        "text": {
            "type": "plain_text",
            "text": gettext("English"),
        },
        "value": BotMyDeskUser.ENGLISH_LOCALE,
    }

    initial_locale = (
        dutch_locale_option
        if botmydesk_user.preferred_locale == BotMyDeskUser.DUTCH_LOCALE
        else english_locale_option
    )

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
                    "text": gettext("Preferred language:"),
                },
                "accessory": {
                    "action_id": "preferred_locale",
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": (
                        dutch_locale_option,
                        english_locale_option,
                    ),
                    "initial_option": initial_locale,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Select the days to receive a Slack reminder on for your BookMyDesk status:"
                    ),
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": notification_options,
                    "initial_option": initial_monday_preference,
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": notification_options,
                    "initial_option": initial_tuesday_preference,
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": notification_options,
                    "initial_option": initial_wednesday_preference,
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": notification_options,
                    "initial_option": initial_thursday_preference,
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": gettext("Select an item"),
                    },
                    "options": notification_options,
                    "initial_option": initial_friday_preference,
                },
            },
            # @TODO Implement dont_bug_me_when_not_needed some day
            # {"type": "divider"},
            # {
            #     "type": "section",
            #     "text": {
            #         "type": "mrkdwn",
            #         "text": gettext(
            #             "However, should I not *not bother you* when you already seem to have booked and checked in for the day(s) above?"
            #         ),
            #     },
            # },
            # {
            #     "type": "section",
            #     "text": {
            #         "type": "mrkdwn",
            #         "text": gettext("Skip notification when booked/checked in?"),
            #     },
            #     "accessory": {
            #         "action_id": "dont_bug_me_when_not_needed",
            #         "type": "static_select",
            #         "placeholder": {"type": "plain_text", "text": "Select an item"},
            #         "options": [
            #             smart_notifications_enabled_option,
            #             smart_notifications_disabled_option,
            #         ],
            #         "initial_option": smart_notifications_enabled_option
            #         if botmydesk_user.prefer_only_notifications_when_needed
            #         else smart_notifications_disabled_option,
            #     },
            # },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("_Connected to BookMyDesk account of")
                    + f" *{full_name}*_",
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
                            "text": gettext("Disconnect")
                            + f" {settings.BOTMYDESK_NAME}",
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


def handle_status_notification(botmydesk_user: BotMyDeskUser, *_):
    """Send status notification."""
    title = gettext("Your BookMyDesk status")
    bmd_core.services.slack_web_client().chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=title,
        blocks=bmd_core.services.gui_status_notification(botmydesk_user),
    ).validate()


def handle_ephemeral_debug_message(botmydesk_user: BotMyDeskUser, *_):
    """Debugging only. Post your blocks here."""
    if not settings.DEBUG:
        return

    # Translators: This is a debug message
    title = gettext("BotMyDesk debug message")
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
        ],
    ).validate()
