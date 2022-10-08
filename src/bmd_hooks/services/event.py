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
                        "text": gettext(f"⚙️ {settings.BOTMYDESK_NAME} preferences"),
                    },
                    "value": "open_settings",
                },
            ],
        }
    ]

    botmydesk_user = bmd_core.services.get_botmydesk_user(payload["event"]["user"])

    if botmydesk_user.has_authorized_bot():
        # Clear on update.
        bmd_core.services.slack_web_client().views_publish(
            user_id=payload["event"]["user"],
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": gettext("_Refreshing your reservations..._"),
                        },
                    },
                ],
            },
        ).validate()

        blocks.extend(bmd_core.services.gui_list_upcoming_reservations(botmydesk_user))
    else:
        blocks.extend(
            [
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
                        "text": gettext(
                            f"My name is {settings.BOTMYDESK_NAME}, I'm an unofficial Slack bot for BookMyDesk. I can remind you to check-in at the office or at home. Making life a bit easier for you!"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "Click the Preferences button above to link your BookMyDesk account to me."
                        ),
                    },
                },
            ]
        )

    bmd_core.services.slack_web_client().views_publish(
        user_id=payload["event"]["user"],
        view={
            "type": "home",
            "blocks": blocks,
        },
    ).validate()
