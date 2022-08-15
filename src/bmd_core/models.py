from django.db import models

from bmd_core.mixins import ModelUpdateMixin


class BotMyDeskSlackUserManager(models.Manager):
    def by_slack_id(self, slack_user_id: str):
        return self.get(slack_user_id=slack_user_id)


class BotMyDeskUser(ModelUpdateMixin, models.Model):
    objects = BotMyDeskSlackUserManager()

    slack_user_id = models.CharField(
        db_index=True,
        unique=True,
        max_length=255,
    )
    email = models.EmailField(max_length=255)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now=True)
    access_token = models.CharField(null=True, default=None, max_length=255)
    # The actual expiry is unknown, but assume one hour.
    access_token_expires_at = models.DateTimeField(null=True, default=None)
    refresh_token = models.CharField(null=True, default=None, max_length=255)

    def authorized_bot(self) -> bool:
        return self.refresh_token is not None
