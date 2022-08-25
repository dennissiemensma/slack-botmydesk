import logging

from slack_sdk.socket_mode import SocketModeClient
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.contrib.humanize.templatetags import humanize
from django.conf import settings
from decouple import config

from bmd_core.models import BotMyDeskUser
from bmd_api_client.exceptions import BookMyDeskException
import bmd_api_client.client


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
        # Dev only: Override locale or use user's preference.
        locale = config("DEV_LOCALE", cast=str, default=botmydesk_user.locale)

        # Apply user locale.
        translation.activate(locale)

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

    firstName = users_info_result.get("user")["profile"]["firstName"]
    locale = users_info_result.get("user")["locale"]

    next_profile_update = timezone.now() + timezone.timedelta(days=1)

    # First-time/new user.
    if botmydesk_user is None:
        botmydesk_logger.debug(f"Creating new user: {slack_user_id}")
        botmydesk_user = BotMyDeskUser.objects.create(
            slack_user_id=slack_user_id,
            locale=locale,
            email=email_address,
            name=firstName,
            next_profile_update=next_profile_update,
        )
    else:
        botmydesk_logger.debug(f"Updating existing user: {slack_user_id}")
        # Data sync existing user.
        botmydesk_user.update(
            locale=locale,
            email=email_address,
            name=firstName,
            next_profile_update=next_profile_update,
        )

    # Dev only: Override locale or use user's preference.
    locale = config("DEV_LOCALE", cast=str, default=botmydesk_user.locale)
    translation.activate(locale)

    return botmydesk_user


def handle_slash_command_list_reservations(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **_
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    title = gettext("Your upcoming BookMyDesk reservations")
    start = timezone.localtime(timezone.now())

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(
            botmydesk_user,
            **{
                "from": start.date(),
                "to": (start + timezone.timedelta(days=7)).date(),
            },
        )
    except BookMyDeskException as error:
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        )
        result.validate()
        return

    if not reservations_result["result"]["items"]:
        reservations_text = gettext("_No reservations found (or too far away)..._")
    else:
        reservations_text = ""
        for current in reservations_result["result"]["items"]:
            reservation_start = timezone.datetime.fromisoformat(current["dateStart"])
            reservation_start_text = reservation_start.strftime("%A %d %B")
            natural_time_until_start = humanize.naturaltime(reservation_start)

            current_status = current["status"]
            current_from = (
                current["checkedInTime"]
                if "checkedInTime" in current
                else current["from"]
            )
            current_to = (
                current["checkedOutTime"]
                if "checkedOutTime" in current
                else current["to"]
            )
            if current_status in ("checkedIn", "checkedOut", "cancelled", "expired"):
                if current_status in ("cancelled", "expired"):
                    emoji = "❌ "
                else:
                    emoji = "✔️"

                reservations_text += gettext(
                    f"\n\n\n~{emoji} {reservation_start_text}: {current_from} to {current_to}~\n_{current_status}_"
                )
                continue

            # Skip weird ones.
            if current_status != "reserved":
                continue

            # Exclude visitors:
            if current["type"] == "visitor":
                continue

            if (
                current["seat"] is not None
                and current["seat"]["map"]["name"] == "Extern"
            ):
                emoji = "🚋"
                location = current["seat"]["map"]["name"]
            elif current["seat"] is not None and current["type"] == "normal":
                emoji = "🏢"
                location = current["seat"]["map"]["name"]
            elif current["seat"] is None and current["type"] == "home":
                emoji = "🏡"
                location = gettext("Home")
            else:
                emoji = "❓"
                location = "❓"

            reservations_text += gettext(
                f"\n\n\n{emoji} {reservation_start_text} from {current_from} to {current_to}\n_About {natural_time_until_start} at *{location}*_"
            )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": reservations_text,
                }
            ],
        },
    ]

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=title,
        blocks=blocks,
    )
    result.validate()


def handle_user_working_home_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("Sorry, not yet implemented 🧑‍💻"),
    )
    result.validate()


def handle_user_working_in_office_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("Sorry, not yet implemented 🧑‍💻"),
    )
    result.validate()


def handle_user_working_externally_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("Sorry, not yet implemented 🧑‍💻"),
    )
    result.validate()


def handle_user_not_working_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    """Fetches your reservations of the current day and cancels them all, when applicable."""
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    except BookMyDeskException as error:
        result = client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        )
        result.validate()
        return

    # Create a report per reservation.
    if not reservations_result["result"]["items"]:
        report_text = gettext("✔️ No reservations found for today")
    else:
        report_text = ""
        for current in reservations_result["result"]["items"]:
            reservation_start = timezone.datetime.fromisoformat(current["dateStart"])
            reservation_start_text = reservation_start.strftime("%A %d %B")

            if (
                current["seat"] is not None
                and current["seat"]["map"]["name"] == "Extern"
            ):
                location = current["seat"]["map"]["name"]
            elif current["seat"] is not None and current["type"] == "normal":
                location = current["seat"]["map"]["name"]
            elif current["seat"] is None and current["type"] == "home":
                location = gettext("Home")
            else:
                location = "❓"

            current_reservation_id = current["id"]
            current_status = current["status"]
            current_from = (
                current["checkedInTime"]
                if "checkedInTime" in current
                else current["from"]
            )
            current_to = (
                current["checkedOutTime"]
                if "checkedOutTime" in current
                else current["to"]
            )
            current_reservation_text = gettext(
                f"\n\n\n• *{current_from} to {current_to}* (*{location}*) at {reservation_start_text}"
            )

            # Exclude visitors:
            if current["type"] == "visitor":
                continue

            # Do not touch these.
            if current_status in ("checkedOut", "cancelled", "expired"):
                report_text += gettext(
                    f"{current_reservation_text}\n\t\t ✔️ _I left it as-is ({current_status})_"
                )
            # Just check out
            elif current_status in ("checkedIn",):
                try:
                    bmd_api_client.client.reservation_checkout(
                        botmydesk_user, current_reservation_id
                    )
                except BookMyDeskException as error:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ⚠️ *Failed to check you out*\n ```{error}```"
                    )
                else:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ✅ _I checked you out_"
                    )
            # Cancel.
            elif current_status in ("reserved",):
                try:
                    bmd_api_client.client.delete_reservation_v3(
                        botmydesk_user, current_reservation_id
                    )
                except BookMyDeskException as error:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ⚠️ *Failed to delete your reservation*\n ```{error}```"
                    )
                else:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ✅ _I deleted your reservation_"
                    )
            # Fail-safe for future statuses.
            else:
                report_text += gettext(
                    f"{current_reservation_text}\n\t\t ⚠️ _Unexpected status, **left untouched**!_"
                )

    title = gettext("Your BookMyDesk reservations update today")
    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=title,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": gettext(
                            f"_You requested me to clear your reservations today._ {report_text}"
                        ),
                    },
                ],
            },
        ],
    )
    result.validate()


def unauthorized_reply_shortcut(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser
):
    result = client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext(
            f"✋ Sorry, you will need to connect me first. See `{settings.SLACK_SLASHCOMMAND_BMD} {settings.SLACK_SLASHCOMMAND_BMD_HELP}`"
        ),
    )
    result.validate()
