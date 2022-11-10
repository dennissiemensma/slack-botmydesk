import zoneinfo
import logging

from django.db import models
from django.db.models import QuerySet, Q
from django.utils import timezone

from bmd_core.mixins import ModelUpdateMixin


botmydesk_logger = logging.getLogger("botmydesk")


class BotMyDeskSlackUserManager(models.Manager):
    def with_session(self) -> QuerySet:
        """Returns users with any session."""
        return self.filter(bookmydesk_refresh_token__isnull=False)

    def eligible_for_notification(self, user_timezone: str) -> QuerySet:
        """Specifically checks for users eligible in the given timezone."""
        local_now = timezone.localtime(timezone.now(), zoneinfo.ZoneInfo(user_timezone))

        preferred_notification_time_field = {
            0: "preferred_notification_time_on_mondays",
            1: "preferred_notification_time_on_tuesdays",
            2: "preferred_notification_time_on_wednesdays",
            3: "preferred_notification_time_on_thursdays",
            4: "preferred_notification_time_on_fridays",
            5: None,  # Maybe if we ever have users working in the weekends.
            6: None,  # Maybe if we ever have users working in the weekends.
        }[local_now.weekday()]

        # Non-working days affect none.
        if preferred_notification_time_field is None:
            return self.none()

        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        results = (
            self.with_session()
            .filter(
                # Notification not yet sent today (or at all)? Prevent duplicate notifications.
                Q(last_notification_sent__isnull=True)
                | Q(last_notification_sent__lte=local_midnight)
            )
            .filter(
                # Only select users in given timezone.
                slack_tz=user_timezone,
                **{
                    # Has notification pref set at all for current day?
                    f"{preferred_notification_time_field}__isnull": False,
                    # And notification pref passed? Only process when applicable.
                    f"{preferred_notification_time_field}__lte": local_now.time(),
                },
            )
        )

        botmydesk_logger.info(
            "Query eligible_for_notification: %s", results.query
        )  # Temp debug.

        return results

    def by_slack_id(self, slack_user_id: str) -> "BotMyDeskUser":
        return self.get(slack_user_id=slack_user_id)


class BotMyDeskUser(ModelUpdateMixin, models.Model):
    ENGLISH_LOCALE = "en"
    DUTCH_LOCALE = "nl"
    LOCALE_CHOICES = (
        (ENGLISH_LOCALE, ENGLISH_LOCALE),
        (DUTCH_LOCALE, DUTCH_LOCALE),
    )

    objects = BotMyDeskSlackUserManager()

    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # @TDO later
    created_at = models.DateTimeField(auto_now=True)

    # Slack data.
    slack_user_id = models.CharField(db_index=True, unique=True, max_length=255)
    slack_email = models.EmailField(max_length=255)
    slack_name = models.CharField(max_length=255)
    slack_tz = models.CharField(max_length=64, db_index=True)
    next_slack_profile_update = models.DateTimeField(
        auto_now=True
    )  # Whenever we update profile info here.

    # BMD data
    bookmydesk_access_token = models.CharField(null=True, default=None, max_length=255)
    bookmydesk_access_token_expires_at = models.DateTimeField(null=True, default=None)
    bookmydesk_refresh_token = models.CharField(null=True, default=None, max_length=255)

    # User preferences
    preferred_locale = models.CharField(
        max_length=16, choices=LOCALE_CHOICES, default=ENGLISH_LOCALE
    )
    preferred_notification_time_on_mondays = models.TimeField(null=True, default=None)
    preferred_notification_time_on_tuesdays = models.TimeField(null=True, default=None)
    preferred_notification_time_on_wednesdays = models.TimeField(
        null=True, default=None
    )
    preferred_notification_time_on_thursdays = models.TimeField(null=True, default=None)
    preferred_notification_time_on_fridays = models.TimeField(null=True, default=None)
    prefer_only_notifications_when_needed = models.BooleanField(default=True)

    last_notification_sent = models.DateTimeField(  # Deprecated for now
        null=True, default=None, db_index=True
    )

    def has_authorized_bot(self) -> bool:
        """Whether the bot is authorized for this user (has session)."""
        return self.bookmydesk_refresh_token is not None

    def access_token_expired(self) -> bool:
        """Whether the access token needs to be refreshed."""
        return (
            self.bookmydesk_access_token_expires_at is None
            or self.bookmydesk_access_token_expires_at <= timezone.now()
        )

    def profile_data_expired(self) -> bool:
        """Whether the profile data needs to be refreshed."""
        return self.next_slack_profile_update <= timezone.now()

    def user_tz_instance(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(str(self.slack_tz))

    def clear_tokens(self):
        self.update(
            bookmydesk_access_token=None,
            bookmydesk_access_token_expires_at=None,
            bookmydesk_refresh_token=None,
        )

    def touch_last_notification_sent(self):
        self.last_notification_sent = timezone.now()
