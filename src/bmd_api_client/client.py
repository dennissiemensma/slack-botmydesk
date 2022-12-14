import logging
import zoneinfo
from pprint import pformat
from typing import Optional

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import requests

from bmd_api_client.dto import (
    V3BookMyDeskProfileResult,
    V3CompanyExtendedResult,
    TokenLoginResult,
    V3ReservationsResult,
)
from bmd_api_client.exceptions import BookMyDeskException
from bmd_core.models import BotMyDeskUser


bookmydesk_client_logger = logging.getLogger("bookmydesk_client")


def request_login_code(email: str):
    """Requests and sends a login code to the designated email address."""
    bookmydesk_client_logger.debug(f"Requesting login code for {email}")
    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/request-login",
        json={
            "email": email,
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        email,
        response.status_code,
        response.request.url,
    )

    if response.status_code != 204:
        bookmydesk_client_logger.error(
            f"FAILED to request login code for {email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)


def token_login(username: str, otp: str) -> TokenLoginResult:
    """Login with OTP and fetch access/refresh tokens."""
    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/token",
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
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        username,
        response.status_code,
        response.request.url,
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to token login for {username} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return TokenLoginResult(response.json())


def logout(botmydesk_user: BotMyDeskUser):
    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/logout",
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to terminate session of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)


def refresh_session(botmydesk_user: BotMyDeskUser):
    """Refresh session, updates user as well"""
    botmydesk_user.refresh_from_db()

    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/token",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.BOOKMYDESK_CLIENT_ID,
            "client_secret": settings.BOOKMYDESK_CLIENT_SECRET,
            "refresh_token": botmydesk_user.bookmydesk_refresh_token,
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to refresh session of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )

        botmydesk_user.clear_tokens()
        bookmydesk_client_logger.error(
            f"Cleared session info of {botmydesk_user.slack_email}, reauthorization required..."
        )
        raise BookMyDeskException(response.content)

    json_response = response.json()
    botmydesk_user.update(
        bookmydesk_access_token=json_response["access_token"],
        bookmydesk_access_token_expires_at=timezone.now()
        + timezone.timedelta(minutes=settings.BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES),
        bookmydesk_refresh_token=json_response["refresh_token"],
    )


def me_v3(botmydesk_user: BotMyDeskUser) -> V3BookMyDeskProfileResult:
    """Profile call about current user"""

    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    CACHE_KEY = f"me_v3_{botmydesk_user.slack_user_id}"
    cached_result = cache.get(CACHE_KEY)

    if cached_result is not None:
        bookmydesk_client_logger.info("Using cached result for: %s", CACHE_KEY)
        return cached_result

    response = requests.get(
        url=f"{settings.BOOKMYDESK_API_URL}/v3/me",
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )
    bookmydesk_client_logger.debug(
        "(%s) Response content:\n%s",
        botmydesk_user.slack_email,
        pformat(response.json(), indent=2),
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to get me/profile of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    result = V3BookMyDeskProfileResult(response.json()["result"])
    cache.set(CACHE_KEY, result, 60)

    return result


def company_extended_v3(botmydesk_user: BotMyDeskUser) -> V3CompanyExtendedResult:
    """Fetch extended details of the user's company."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    # For now, always use the first company found.
    profile = me_v3(botmydesk_user=botmydesk_user)

    CACHE_KEY = f"me_v3_{botmydesk_user.slack_user_id}"
    cached_result = cache.get(CACHE_KEY)

    if cached_result is not None:
        bookmydesk_client_logger.info("Using cached result for: %s", CACHE_KEY)
        return cached_result

    response = requests.get(
        url=f"{settings.BOOKMYDESK_API_URL}/v3/companyExtended",
        params={
            "companyId": profile.first_company_id(),
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )
    bookmydesk_client_logger.debug(
        "(%s) Response content:\n%s",
        botmydesk_user.slack_email,
        pformat(response.json(), indent=2),
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to get own reservations (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    result = V3CompanyExtendedResult(response.json()["result"]["company"])
    cache.set(CACHE_KEY, result, 3600)

    return result


def list_reservations_v3(
    botmydesk_user: BotMyDeskUser, **override_parameters
) -> V3ReservationsResult:
    """Fetch reservations (for today by default). Any parameters given will overrule any defaults below."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    # For now, always use the first company found.
    profile = me_v3(botmydesk_user=botmydesk_user)

    today = timezone.localtime(
        timezone.now(), timezone=botmydesk_user.user_tz_instance()
    )
    parameters = {
        "companyId": profile.first_company_id(),
        "userId": profile.id(),  # Skips delegates
        "includeAnonymous": "true",
        "from": today.date(),
        "to": (
            today + timezone.timedelta(days=1)
        ).date(),  # Yes, kinda sucks and ambiguous
        "take": 50,  # Limit, default 10
    }
    parameters.update(override_parameters)

    response = requests.get(
        url=f"{settings.BOOKMYDESK_API_URL}/v3/reservations",
        params=parameters,
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )
    bookmydesk_client_logger.debug(
        "(%s) Response content:\n%s",
        botmydesk_user.slack_email,
        pformat(response.json(), indent=2),
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to get reservations of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return V3ReservationsResult(response.json())


def create_reservation_v3(
    botmydesk_user: BotMyDeskUser,
    reservation_type: str,
    start: timezone.datetime,
    end: timezone.datetime,
    seat_id: Optional[str] = None,
) -> str:
    """Creates a new reservation. Returns the ID of it when created successful."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    profile = me_v3(botmydesk_user=botmydesk_user)

    # UTC, just to be sure as we do not know the API input validation used.
    utc = zoneinfo.ZoneInfo("UTC")
    parameters = {
        "dateStart": timezone.localtime(start, timezone=utc).isoformat(),
        "dateEnd": timezone.localtime(end, timezone=utc).isoformat(),
        "type": reservation_type,
        "userId": profile.id(),
    }

    if seat_id:
        parameters.update({"seatId": seat_id})

    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/v3/reservation",
        json=parameters,
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )
    bookmydesk_client_logger.debug(
        "(%s) Response content:\n%s",
        botmydesk_user.slack_email,
        pformat(response.json(), indent=2),
    )

    if response.status_code != 200:
        bookmydesk_client_logger.error(
            f"FAILED to create reservation of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)

    return response.json()["result"]["reservation"]["id"]


def reservation_check_in_out(
    botmydesk_user: BotMyDeskUser, reservation_id: str, check_in: bool
):
    """Check in or out of a reservation."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    check_in_or_out = "checkin" if check_in else "checkout"
    response = requests.post(
        url=f"{settings.BOOKMYDESK_API_URL}/reservation/{reservation_id}/{check_in_or_out}",
        json={
            "type": "manual",
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )

    expected_status_code = 200 if check_in else 204

    if response.status_code != expected_status_code:
        bookmydesk_client_logger.error(
            f"FAILED to {check_in_or_out} from reservation of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)


def delete_reservation_v3(botmydesk_user: BotMyDeskUser, reservation_id: str):
    """Delete a reservation."""
    if botmydesk_user.access_token_expired():
        refresh_session(botmydesk_user)
        botmydesk_user.refresh_from_db()

    response = requests.delete(
        url=f"{settings.BOOKMYDESK_API_URL}/v3/reservation",
        params={
            "reservationId": reservation_id,
        },
        headers={
            "User-Agent": settings.BOTMYDESK_USER_AGENT,
            "Authorization": f"Bearer {botmydesk_user.bookmydesk_access_token}",
        },
    )
    bookmydesk_client_logger.info(
        "(%s) Received HTTP %s on: %s",
        botmydesk_user.slack_email,
        response.status_code,
        response.request.url,
    )

    if response.status_code != 204:
        bookmydesk_client_logger.error(
            f"FAILED to delete reservation of {botmydesk_user.slack_email} (HTTP {response.status_code}): {response.content}"
        )
        raise BookMyDeskException(response.content)
