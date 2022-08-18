import logging

from slack_sdk.socket_mode import SocketModeClient
from django.utils import timezone, translation
from django.conf import settings
from decouple import config

from bmd_core.models import BotMyDeskUser


botmydesk_logger = logging.getLogger("botmydesk")


def get_botmydesk_user(client: SocketModeClient, slack_user_id: str) -> BotMyDeskUser:
    """Fetches Slack user info and creates/updates the user info on our side."""
    try:
        # Ensure every user is known internally.
        botmydesk_user = BotMyDeskUser.objects.by_slack_id(slack_user_id=slack_user_id)
    except BotMyDeskUser.DoesNotExist:
        botmydesk_user = None

    # Profile sync on each request is quite expensive, so once in a while suffices. Or when the user is unknown.
    if botmydesk_user is not None and botmydesk_user.profile_data_expired():
        # Apply user locale.
        translation.activate(botmydesk_user.locale)

        return botmydesk_user

    users_info_result = client.web_client.users_info(
        user=slack_user_id, include_locale=True
    )
    users_info_result.validate()

    # Dev only: Override email address when required for development.
    DEV_EMAIL_ADDRESS = config("DEV_EMAIL_ADDRESS", cast=str, default="")

    if settings.DEBUG and DEV_EMAIL_ADDRESS:
        email_address = DEV_EMAIL_ADDRESS
        botmydesk_logger.debug(
            f"DEV_EMAIL_ADDRESS: Overriding email address with: {email_address}"
        )
    else:
        email_address = users_info_result.get("user")["profile"]["email"]

    first_name = users_info_result.get("user")["profile"]["first_name"]
    locale = users_info_result.get("user")["locale"]

    next_profile_update = timezone.now() + timezone.timedelta(days=1)

    # First-time/new user.
    if botmydesk_user is None:
        botmydesk_logger.debug(f"Creating new user: {slack_user_id}")
        botmydesk_user = BotMyDeskUser.objects.create(
            slack_user_id=slack_user_id,
            locale=locale,
            email=email_address,
            name=first_name,
            next_profile_update=next_profile_update,
        )
    else:
        botmydesk_logger.debug(f"Updating existing user: {slack_user_id}")
        # Data sync existing user.
        botmydesk_user.update(
            locale=locale,
            email=email_address,
            name=first_name,
            next_profile_update=next_profile_update,
        )

    translation.activate(botmydesk_user.locale)

    return botmydesk_user
