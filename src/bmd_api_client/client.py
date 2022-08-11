import logging

from django.conf import settings
import requests


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
        bookmydesk_client_logger.error(f"FAILED to request login code for {email}")
        raise PermissionError(response.content)


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
        bookmydesk_client_logger.error(f"FAILED to token login for {username}")
        raise PermissionError(response.content)

    return response.json()
