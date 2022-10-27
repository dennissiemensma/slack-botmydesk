import logging
from celery import Celery

from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_hooks.services.event


botmydesk_logger = logging.getLogger("botmydesk")
app = Celery()


@app.task
def refresh_all_bookmydesk_sessions():
    """Triggers a profile call for very user, causing a token/user update in the API client and persists it."""
    for current in BotMyDeskUser.objects.with_session():
        botmydesk_logger.info(
            f"Performing scheduled session refresh for @{current.slack_user_id} ({current.slack_email})"
        )
        bmd_api_client.client.me_v3(
            botmydesk_user=current
        )  # Refresh + persists logic in client.


@app.task
def sync_botmydesk_app_homes():
    """Updates the app home screen for every user linked."""
    for current in BotMyDeskUser.objects.with_session():
        botmydesk_logger.info(
            f"Performing periodic app home update for @{current.slack_user_id} ({current.slack_email})"
        )
        # Cheap workaround.
        bmd_hooks.services.event.handle_app_home_opened_event(
            {
                "event": {
                    "user": current.slack_user_id,
                    "tab": "home",
                }
            }
        )
