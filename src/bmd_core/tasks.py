import logging
from celery import Celery

import bmd_api_client.client
from bmd_core.models import BotMyDeskUser


botmydesk_logger = logging.getLogger("botmydesk")
app = Celery()


@app.task
def refresh_all_bookmydesk_sessions():
    """Triggers a profile call for very user, causing a token/user update in the API client and persists it."""
    for current in BotMyDeskUser.objects.with_session():
        botmydesk_logger.info(f"Scheduled session refresh of {current.slack_user_id}")
        bmd_api_client.client.me_v3(
            botmydesk_user=current
        )  # Refresh + persists logic in client.
