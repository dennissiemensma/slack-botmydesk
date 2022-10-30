import logging

from django.conf import settings
from django.utils.translation import gettext

import bmd_core.services


botmydesk_logger = logging.getLogger("botmydesk")


def handle_app_home_opened_event(payload: dict):
    """https://api.slack.com/events/app_home_opened"""
    # Only home tab, for now. Maybe messages tab later.
    if payload["event"]["tab"] != "home":
        return

    slack_user_id = payload["event"]["user"]

    try:
        bmd_core.services.validate_botmydesk_user(slack_user_id=slack_user_id)
    except EnvironmentError:
        # Ignore unknown users.
        return

    botmydesk_user = bmd_core.services.get_botmydesk_user(slack_user_id)

    if botmydesk_user.has_authorized_bot():
        # Do not trigger for known users.
        return

    # New or unauthorized bot users. Give them a welcome.
    bmd_core.services.apply_user_locale(botmydesk_user)

    # Always show preferences button
    blocks = [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": f"⚙️ {settings.BOTMYDESK_NAME} "
                        + gettext("preferences"),
                    },
                    "value": "open_preferences",
                },
            ],
        },
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": gettext(f"Hi {botmydesk_user.slack_name} 👋"),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": gettext("My name is")
                + f" {settings.BOTMYDESK_NAME}, "
                + gettext(
                    "I'm an unofficial Slack bot for BookMyDesk. I can remind you to check-in at the office or at home. Making life a bit easier for you!"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": gettext(
                    "Click the preferences button above to link your BookMyDesk account to me."
                ),
            },
        },
    ]

    bmd_core.services.slack_web_client().views_publish(
        user_id=botmydesk_user.slack_user_id,
        view={
            "type": "home",
            "blocks": blocks,
        },
    ).validate()
