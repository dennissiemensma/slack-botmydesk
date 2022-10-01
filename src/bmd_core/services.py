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
                "to": (start + timezone.timedelta(days=28)).date(),
                "take": 3,
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

    reservations_text = gettext("_No reservations found (or too far away)..._")

    if reservations_result.reservations():
        reservations_text = ""

        for current in reservations_result.reservations():
            reservation_start = current.date_start()
            reservation_start_text = reservation_start.strftime("%A %-d %B")
            natural_time_until_start = humanize.naturaltime(reservation_start)

            current_from = current.checked_in_time() or current.from_time()
            current_to = current.checked_out_time() or current.to_time()

            if current.status() in ("checkedIn", "checkedOut", "cancelled", "expired"):
                if current.status() in ("cancelled", "expired"):
                    emoji = "❌ "
                else:
                    emoji = "✔️"

                reservations_text += gettext(
                    f"\n\n\n{emoji} {reservation_start_text}: {current_from} to {current_to}\n_{current.status()}_"
                )
                continue

            # Skip weird ones.
            if current.status() != "reserved":
                continue

            # Exclude visitors:
            if current.type() == "visitor":
                continue

            emoji = current.emoji_shortcut()
            location = current.location_name_shortcut()

            reservations_text += gettext(
                f"\n\n\n{emoji} {reservation_start_text} from {current_from} to {current_to}\n_In about {natural_time_until_start} at *{location}*_"
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

    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=title,
        blocks=blocks,
    ).validate()


def handle_slash_command_status(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    today_text = timezone.localtime(timezone.now()).strftime("%A %-d %B")
    reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    reservation_count = 0  # Omits ignored ones below
    has_home_reservation = has_office_reservation = has_external_reservation = False
    checked_in = checked_out = False
    reservation_start = reservation_end = None

    # Very shallow assertions.
    for current in reservations_result.reservations():
        if current.type() == "visitor":
            continue

        reservation_count += 1
        reservation_start = current.from_time()
        reservation_end = current.to_time()

        if (
            current.seat() is not None
            and current.seat().map_name()
            == settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME
        ):
            has_external_reservation = True
            checked_in = current.status() == "checkedIn"
            checked_out = current.status() == "checkedOut"
        elif current.seat() is not None and current.type() == "normal":
            has_office_reservation = True
            checked_in = current.status() == "checkedIn"
            checked_out = current.status() == "checkedOut"
        elif current.seat() is None and current.type() == "home":
            has_home_reservation = True

    if has_home_reservation:
        reservation_text = gettext(
            f"🏡 You have a *home reservation* for {today_text} ({reservation_start} - {reservation_end})"
        )
    elif has_office_reservation:
        reservation_text = gettext(
            f"🏢 You have an *office reservation* for {today_text} ({reservation_start} - {reservation_end})"
        )
    elif has_external_reservation:
        reservation_text = gettext(
            f"🚋 You have an *external reservation* outside home/office for {today_text} ({reservation_start} - {reservation_end})"
        )
    else:
        reservation_text = gettext(f"You have *no reservation* yet for {today_text}")

    # Edge-cases, for those wanting to see the world burn.
    if reservation_count > 1:
        reservation_text += gettext(
            f", along with {reservation_count-1} other reservation(s)"
        )

    # This is some assumption, may break in future if statuses change.
    if checked_in:
        reservation_text += gettext(
            " and you are *checked in*.\n\n_Do I even need to do anything at all?_"
        )
    elif checked_out:
        reservation_text += gettext(
            " and you are *checked out*.\n\n_Do I even need to do anything at all?_"
        )
    else:
        reservation_text += gettext(".\n\n_Where are you today?_")

    blocks = [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": gettext("⚙️Preferences"),
                    },
                    "value": "open_settings",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": reservation_text,
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": gettext("🏡 Working home"),
                    },
                    "confirm": {
                        "title": {
                            "type": "plain_text",
                            "text": gettext("Are you sure?"),
                        },
                        "text": {
                            "type": "mrkdwn",
                            "text": gettext(
                                "🏡 You're working from home today.\n\nI will book a home spot for you, if you don't have one yet."
                            ),
                        },
                        "confirm": {
                            "type": "plain_text",
                            "text": gettext("Yes, continue"),
                        },
                        "deny": {
                            "type": "plain_text",
                            "text": gettext("No, wait"),
                        },
                    },
                    "value": "mark_working_from_home_today",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": gettext("🏢 Working in the office"),
                    },
                    "confirm": {
                        "title": {
                            "type": "plain_text",
                            "text": gettext("Are you sure?"),
                        },
                        "text": {
                            "type": "mrkdwn",
                            "text": gettext(
                                "🏢 You're working at the office today.\n\nThis only works if you already have a reservation.\nI will check you in if you are not already, no matter what time your reservation is."
                            ),
                        },
                        "confirm": {
                            "type": "plain_text",
                            "text": gettext("Yes, continue"),
                        },
                        "deny": {
                            "type": "plain_text",
                            "text": gettext("No, wait"),
                        },
                    },
                    "value": "mark_working_at_the_office_today",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": gettext("🚋 Working externally"),
                    },
                    "confirm": {
                        "title": {
                            "type": "plain_text",
                            "text": gettext("Are you sure?"),
                        },
                        "text": {
                            "type": "mrkdwn",
                            "text": gettext(
                                "🚋 You're working externally.\n\nI will book an 'external' spot for you, if you don't have one yet, and check you in as well."
                            ),
                        },
                        "confirm": {
                            "type": "plain_text",
                            "text": gettext("Yes, continue"),
                        },
                        "deny": {
                            "type": "plain_text",
                            "text": gettext("No, wait"),
                        },
                    },
                    "value": "mark_working_externally_today",
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": gettext("❌ Not working"),
                    },
                    "confirm": {
                        "title": {
                            "type": "plain_text",
                            "text": gettext("Are you sure?"),
                        },
                        "text": {
                            "type": "mrkdwn",
                            "text": gettext(
                                "❌ You're not working today or you're already done.\n\nI will delete your pending reservations for today (if any).\nAlso, if you were already checked in, I'll check you out now."
                            ),
                        },
                        "confirm": {
                            "type": "plain_text",
                            "text": gettext("Yes, continue"),
                        },
                        "deny": {
                            "type": "plain_text",
                            "text": gettext("No, wait"),
                        },
                    },
                    "value": "mark_not_working_today",
                },
            ],
        },
    ]

    result = client.web_client.chat_postMessage(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        blocks=blocks,
    )
    result.validate()


def handle_user_working_home_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    message_to_user = gettext(
        "🏡 _You requested me to book you for working at home._\n\n\nTODO"
    )
    _post_handle_report_update(client, botmydesk_user, message_to_user, **payload)

    # @TODO: Implement
    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("Sorry, not yet implemented 🧑‍💻"),
    ).validate()


def handle_user_working_in_office_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    except BookMyDeskException as error:
        client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Worst-case.
    report_text = gettext(
        "⚠️ No office reservation found for this day. Please book an office seat and check-in anyway."
    )

    if reservations_result.reservations():
        for current in reservations_result.reservations():
            # Ignore everything we're not interested in. E.g. visitors or home reservations.
            if current.seat() is None or current.type() != "normal":
                continue

            location = current.seat().map_name()
            current_reservation_id = current.id()

            # The logic below just assumes a single reservation. We may or may not want to have it compatible
            # with multiple items in the future (which is way more code than it currently already is).

            if current.status() == "checkedIn":
                report_text = gettext(
                    "✔️ _I left it as-is, since you're already *checked in.*_"
                )
                break

            if current.status() == "checkedOut":
                report_text = gettext(
                    "⚠️ _I did nothing, as you seem to be *checked out* already?_"
                )
                break

            if current.status() == "reserved":
                try:
                    bmd_api_client.client.reservation_check_in_out(
                        botmydesk_user, current_reservation_id, check_in=True
                    )
                except BookMyDeskException as error:
                    report_text = gettext(
                        f"⚠️ *Failed to check you in*\n ```{error}```"
                    )
                else:
                    report_text = gettext(f"✅ _I checked you in at {location}_")
                break

            # Fail-safe for future statuses.
            report_text = gettext(
                "⚠️ _Unexpected status, **I ignored your request to make sure not breaking anything**!_"
            )
            break

    message_to_user = gettext(
        f"🏢 _You requested me to check you in for the office._\n\n\n{report_text}"
    )
    _post_handle_report_update(client, botmydesk_user, message_to_user, **payload)


def handle_user_working_externally_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    # Only when required/supported.
    if not settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME:
        return client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext("✋ Sorry, not supported at this time"),
        ).validate()

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    except BookMyDeskException as error:
        client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Check whether we only need to check in.
    # @TODO
    reservations_result

    # try:
    #     company_extended_result = bmd_api_client.client.company_extended_v3(botmydesk_user)
    # except BookMyDeskException as error:
    #     return client.web_client.chat_postEphemeral(
    #         channel=botmydesk_user.slack_user_id,
    #         user=botmydesk_user.slack_user_id,
    #         text=gettext(
    #             f"Sorry, an error occurred while requesting company information: ```{error}```"
    #         ),
    #     ).validate()
    #
    # # Find "external" location.
    # matches = [x for x in company_extended_result.locations() if x.name() == settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME]
    #
    # if not matches:
    #     raise AssertionError('Failed to find location for working externally')
    #
    # # First and only floor. Just find any seat available.
    # seats = matches[0].maps()[0].seats()

    # message_to_user = gettext(
    #     f"🚋 _You requested me to check you in for working externally._\n\n\nTODO"
    # )
    # _post_handle_report_update(client, botmydesk_user, message_to_user, **payload)

    # @TODO: Implement
    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("Sorry, not yet implemented 🧑‍💻"),
    ).validate()


def handle_user_not_working_today(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser, **payload
):
    """Fetches your reservations of the current day and cancels them all, when applicable."""
    if not botmydesk_user.authorized_bot():
        return unauthorized_reply_shortcut(client, botmydesk_user)

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    except BookMyDeskException as error:
        client.web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Create a report per reservation.
    report_text = gettext("✔️ No reservations found anyway")

    if reservations_result.reservations():
        report_text = ""

        for current in reservations_result.reservations():
            location = current.location_name_shortcut()

            current_reservation_id = current.id()
            current_status = current.status()
            current_from = current.checked_in_time() or current.from_time()
            current_to = current.checked_out_time() or current.to_time()
            current_reservation_text = gettext(
                f"\n\n\n• *{current_from} to {current_to}* (*{location}*)"
            )

            # Exclude visitors:
            if current.type() == "visitor":
                continue

            # Do not touch these.
            if current_status in ("checkedOut", "cancelled", "expired"):
                report_text += gettext(
                    f"{current_reservation_text}\n\t\t ✔️ _I left it as-is ({current_status})_"
                )
            # Just check out.
            elif current_status in ("checkedIn",):
                try:
                    bmd_api_client.client.reservation_check_in_out(
                        botmydesk_user, current_reservation_id, check_in=False
                    )
                except BookMyDeskException as error:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ⚠️ *Failed to check you out*\n ```{error}```"
                    )
                else:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ✅ _I checked you out_"
                    )
            # Delete.
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

    message_to_user = gettext(
        f"❌ _You requested me to clear your reservations._\n\n\n{report_text}"
    )
    _post_handle_report_update(client, botmydesk_user, message_to_user, **payload)


def _post_handle_report_update(
    client: SocketModeClient,
    botmydesk_user: BotMyDeskUser,
    message_to_user: str,
    **payload,
):
    today_text = timezone.localtime(timezone.now()).strftime("%A %-d %B")
    title = gettext(f"{today_text} update")
    client.web_client.chat_postMessage(
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
                        "text": message_to_user,
                    },
                ],
            },
        ],
    ).validate()

    try:
        # Delete trigger, if any was given.
        client.web_client.chat_delete(
            channel=payload["container"]["channel_id"],
            ts=payload["container"]["message_ts"],
        ).validate()
    except KeyError:
        pass


def unauthorized_reply_shortcut(
    client: SocketModeClient, botmydesk_user: BotMyDeskUser
):
    client.web_client.chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("✋ Sorry, you will need to connect me first."),
    ).validate()
