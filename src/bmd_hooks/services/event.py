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

    # @TODO: Rework later to dynamic view of reservations or status.
    bmd_core.services.slack_web_client().views_publish(
        user_id=payload["event"]["user"],
        view={
            "type": "home",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Sorry, not yet implemented 🧑‍💻",
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
        },
    ).validate()
