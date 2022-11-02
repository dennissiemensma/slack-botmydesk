import logging

from celery import Celery
from django.utils.translation import gettext

from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_core.services


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
        bmd_core.services.update_user_app_home(botmydesk_user=current)


@app.task
def dispatch_botmydesk_notifications():
    """
    Checks whether any daily notifications should be dispatched, taking user preferences into account.
    Either run this method every minute or once after every notification time available.
    """
    botmydesk_logger.info("Dispatching notifications to users (when applicable)")

    # Since we're dealing with local timezones, ensure to group 'em by timezone.
    for current_timezone in (
        BotMyDeskUser.objects.with_session()
        .values("slack_tz")
        .distinct()
        .values_list("slack_tz", flat=True)
    ):
        botmydesk_logger.debug(f"Processing users in timezone {current_timezone}")

        # The loop below is a nice candidate for further async processing on a per-user basis if ever needed.
        for current_botmydesk_user in BotMyDeskUser.objects.eligible_for_notification(
            current_timezone
        ):
            botmydesk_logger.info(
                f"{current_timezone}: User @{current_botmydesk_user.slack_user_id} ({current_botmydesk_user.slack_email}) eligible for notification"
            )

            current_botmydesk_user.refresh_from_db()

            # @TODO: Take current_botmydesk_user.prefer_only_notifications_when_needed into account as well

            title = gettext("Your BookMyDesk status")
            bmd_core.services.slack_web_client().chat_postEphemeral(
                channel=current_botmydesk_user.slack_user_id,
                user=current_botmydesk_user.slack_user_id,
                text=title,
                blocks=bmd_core.services.gui_status_notification(
                    current_botmydesk_user
                ),
            ).validate()
            bmd_core.services.gui_status_notification(
                botmydesk_user=current_botmydesk_user
            )

            # Only update here, since this is (for now) the only origin for automated notifications
            current_botmydesk_user.touch_last_notification_sent()
            current_botmydesk_user.save()
