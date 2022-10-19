import zoneinfo

from django.db import models
from django.utils import timezone

from bmd_core.mixins import ModelUpdateMixin


class BotMyDeskSlackUserManager(models.Manager):
    def by_slack_id(self, slack_user_id: str):
        return self.get(slack_user_id=slack_user_id)


class BotMyDeskUser(ModelUpdateMixin, models.Model):
    ENGLISH_LOCALE = "en"
    DUTCH_LOCALE = "nl"
    LOCALE_CHOICES = (
        (ENGLISH_LOCALE, ENGLISH_LOCALE),
        (DUTCH_LOCALE, DUTCH_LOCALE),
    )

    objects = BotMyDeskSlackUserManager()

    created_at = models.DateTimeField(auto_now=True)
    next_background_run = models.DateTimeField(
        db_index=True, auto_now=True
    )  # Background processing schedule.

    # Slack data.
    slack_user_id = models.CharField(db_index=True, unique=True, max_length=255)
    slack_email = models.EmailField(max_length=255)
    slack_name = models.CharField(max_length=255)
    slack_tz = models.CharField(max_length=64)
    next_slack_profile_update = models.DateTimeField(
        auto_now=True
    )  # Whenever WE update profile info here.

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
