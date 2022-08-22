import logging

from django.conf import settings
from django.utils import timezone
import requests

from bmd_api_client.exceptions import BookMyDeskException
from bmd_core.models import BotMyDeskUser


bookmydesk_client_logger = logging.getLogger("bookmydesk_client")


def request_login_code(email: str):
    """Requests and sends a login code to the designated email address."""
    bookmydesk_client_logger.debug(f"Requesting login code for {email}")
    response = requests.post(
        url="{}/request-login".format(settings.BOOKMYDESK_API_URL),
        json={
            "email": email,
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
        },
    )

    if response.status_code != 204:
        bookmydesk_client_logger.error(
            f"FAILED to request login code for {email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)


def token_login(username: str, otp: str) -> dict:
    """Login with OTP and fetch access/refresh tokens."""
    bookmydesk_client_logger.debug(f"Token login for {username} with {otp}")
    response = requests.post(
        url="{}/token".format(settings.BOOKMYDESK_API_URL),
        data={
            "grant_type": "password",
            "client_id": settings.BOOKMYDESK_CLIENT_ID,
            "client_secret": settings.BOOKMYDESK_CLIENT_SECRET,
            "username": username,
            "password": otp,
            "scopes": "",
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to token login for {username} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return response.json()


def logout(botmydesk_user: BotMyDeskUser):
    bookmydesk_client_logger.debug(f"Terminate session for {botmydesk_user.email}")

    response = requests.post(
        url="{}/logout".format(settings.BOOKMYDESK_API_URL),
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.access_token}",
        },
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to terminate session for {botmydesk_user.email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)


def refresh_session(botmydesk_user: BotMyDeskUser):
    """Refresh session, updates user as well"""
    botmydesk_user.refresh_from_db()

    bookmydesk_client_logger.debug(f"Refresh session for {botmydesk_user.email}")
    response = requests.post(
        url="{}/token".format(settings.BOOKMYDESK_API_URL),
        data={
            "grant_type": "refresh_token",
            "client_id": settings.BOOKMYDESK_CLIENT_ID,
            "client_secret": settings.BOOKMYDESK_CLIENT_SECRET,
            "refresh_token": botmydesk_user.refresh_token,
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to refresh session for {botmydesk_user.email} (HTTP {response.status_code}): {response.content}"
        )
        botmydesk_user.clear_tokens()
        bookmydesk_client_logger.error(
            f"Cleared session info for {botmydesk_user.email}, reauthorization required..."
        )
        raise BookMyDeskException(response.content)

    json_response = response.json()
    botmydesk_user.update(
        access_token=json_response["access_token"],
        access_token_expires_at=timezone.now()
        + timezone.timedelta(minutes=settings.BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES),
        refresh_token=json_response["refresh_token"],
    )


def profile(botmydesk_user: BotMyDeskUser) -> dict:
    """Profile call about current user"""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    bookmydesk_client_logger.debug(f"Me/profile for {botmydesk_user.email}")
    response = requests.get(
        url="{}/me".format(settings.BOOKMYDESK_API_URL),
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.access_token}",
        },
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to get me/profile for {botmydesk_user.email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return response.json()


def reservations(botmydesk_user: BotMyDeskUser, **override_parameters) -> dict:
    """Fetch reservations. Any parameters given will overrule any defaults below."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    # For now, always use the first company found.
    profile_result = profile(botmydesk_user=botmydesk_user)
    company_id = profile_result["companies"][0]["id"]

    today = timezone.localtime(timezone.now())
    bookmydesk_client_logger.debug(f"Reservations for {botmydesk_user.email}")
    parameters = {
        "companyId": company_id,
        "includeAnonymous": "true",
        "from": today.date(),
        "to": (today + timezone.timedelta(days=7)).date(),
    }
    parameters.update(override_parameters)

    response = requests.get(
        url="{}/v3/reservations".format(settings.BOOKMYDESK_API_URL),
        params=parameters,
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.access_token}",
        },
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to get reservations for {botmydesk_user.email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return response.json()
