import locale
import logging
from typing import Optional

from slack_sdk.web import WebClient
from django.utils import timezone, translation
from django.utils.translation import gettext, ngettext
from django.conf import settings

from bmd_core.models import BotMyDeskUser
from bmd_api_client.exceptions import BookMyDeskException
import bmd_api_client.client


botmydesk_logger = logging.getLogger("botmydesk")


def slack_web_client() -> WebClient:
    return WebClient(token=settings.SLACK_BOT_TOKEN)


def get_botmydesk_user(slack_user_id: str) -> BotMyDeskUser:
    """Fetches Slack user info and creates/updates the user info on our side."""
    try:
        # Ensure every user is known internally.
        botmydesk_user = BotMyDeskUser.objects.by_slack_id(slack_user_id=slack_user_id)
    except BotMyDeskUser.DoesNotExist:
        botmydesk_user = None

    # Profile sync on each request is quite expensive, so once in a while suffices.
    if botmydesk_user is not None and botmydesk_user.profile_data_expired():
        return botmydesk_user

    # Fetch Slack info for user.
    users_info_result = slack_web_client().users_info(
        user=slack_user_id, include_locale=True
    )
    users_info_result.validate()
    botmydesk_logger.debug(f"Users info result: {users_info_result}")

    email_address = users_info_result.get("user")["profile"]["email"]
    first_name = users_info_result.get("user")["profile"]["first_name"]
    tz = users_info_result.get("user")["tz"]

    next_profile_update = timezone.now() + timezone.timedelta(hours=1)

    # First-time/new user.
    if botmydesk_user is None:
        botmydesk_logger.debug(f"Creating new user: {slack_user_id}")
        botmydesk_user = BotMyDeskUser.objects.create(
            slack_user_id=slack_user_id,
            slack_email=email_address,
            slack_name=first_name,
            slack_tz=tz,
            next_slack_profile_update=next_profile_update,
        )
    else:
        botmydesk_logger.debug(f"Updating existing user: {slack_user_id}")
        # Data sync existing user.
        botmydesk_user.update(
            slack_email=email_address,
            slack_name=first_name,
            slack_tz=tz,
            next_slack_profile_update=next_profile_update,
        )

    return botmydesk_user


def validate_botmydesk_user(slack_user_id: str):
    """Whitelist check."""
    if not settings.BOTMYDESK_WHITELISTED_SLACK_IDS:
        return

    if slack_user_id in settings.BOTMYDESK_WHITELISTED_SLACK_IDS:
        return

    raise EnvironmentError(
        gettext(
            "Sorry, you are not whitelisted and I was too lazy to create a decent message. This bot will be public eventually, including for you... :]"
        )
    )


def apply_user_locale(botmydesk_user: BotMyDeskUser):
    botmydesk_logger.debug(f"Applying user locale: {botmydesk_user.preferred_locale}")

    # Django gettext strings.
    translation.activate(botmydesk_user.preferred_locale)

    # Python (e.g. date formatters).
    locale.setlocale(locale.LC_TIME, botmydesk_user.preferred_locale)


def gui_list_upcoming_reservations(botmydesk_user: BotMyDeskUser) -> Optional[list]:
    """
    :return: Slack blocks GUI elements
    """
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    title = gettext("Upcoming reservations")
    start = timezone.localtime(
        timezone.now(), timezone=botmydesk_user.user_tz_instance()
    )

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(
            botmydesk_user,
            **{
                "from": start.date(),
                "to": (start + timezone.timedelta(days=7)).date(),
                "take": 50,
            },
        )
    except BookMyDeskException as error:
        result = slack_web_client().chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext("Sorry, an error occurred while requesting your reservations")
            + f": ```{error}```",
        )
        result.validate()
        return

    reservations_text = gettext("_No reservations found (or too far away)..._")
    profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)

    if reservations_result.reservations():
        reservations_text = ""

        for current in reservations_result.reservations():
            reservation_start = current.date_start()
            reservation_start_text = reservation_start.strftime("%A %-d %B")

            current_from = current.checked_in_time() or current.from_time()
            current_to = current.checked_out_time() or current.to_time()

            if current.owner_id() != profile.id():
                # Ignore delegates
                continue

            if current.type() == "visitor":
                continue

            if current.status() in ("checkedIn", "checkedOut", "cancelled", "expired"):
                if current.status() in ("cancelled", "expired"):
                    emoji = "??? "
                else:
                    emoji = "??????"

                if current.status() == "checkedIn":
                    status_text = gettext("Checked in")
                elif current.status() == "checkedOut":
                    status_text = gettext("Checked out")
                else:
                    status_text = ""

                reservations_text += gettext(
                    f"\n\n\n{emoji} {reservation_start_text}: {current_from} - {current_to}\n_{status_text}_"
                )
                continue

            # Skip weird ones.
            if current.status() != "reserved":
                continue

            emoji = current.emoji_shortcut()
            location = current.location_name_shortcut()

            # Hack for gettext, alternatively concat.
            text_from = gettext("from")
            text_to = gettext("to")
            reservations_text += f"\n\n\n{emoji} *{reservation_start_text}*\n_{location}, {text_from} {current_from} {text_to} {current_to}_"

    return [
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


def gui_status_notification(botmydesk_user: BotMyDeskUser, *_) -> Optional[list]:
    """
    :return: Slack blocks GUI elements
    """
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    today_text = timezone.localtime(
        timezone.now(), timezone=botmydesk_user.user_tz_instance()
    ).strftime("%A %-d %B")
    reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
    reservation_count = 0  # Omits ignored ones below
    has_home_reservation = has_office_reservation = has_external_reservation = False
    checked_in = checked_out = False
    reservation_start = reservation_end = None

    profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)

    # Very shallow assertions.
    for current in reservations_result.reservations():
        if current.owner_id() != profile.id():
            # Ignore delegates
            continue

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
        reservation_text = (
            gettext("???? You seem to have a *home reservation* for")
            + f" {today_text} ({reservation_start} - {reservation_end})"
        )
    elif has_office_reservation:
        reservation_text = (
            gettext("???? You seem to have an *office reservation* for")
            + f" {today_text} ({reservation_start} - {reservation_end})"
        )
    elif has_external_reservation:
        reservation_text = (
            gettext(
                "???? You seem to have an *external reservation* outside home/office for"
            )
            + f" {today_text} ({reservation_start} - {reservation_end})"
        )
    else:
        reservation_text = (
            gettext("You seem to have *no reservation* (yet) for") + f" {today_text}"
        )

    # Edge-cases, for those wanting to see the world burn.
    if reservation_count > 1:
        other_count = reservation_count - 1
        reservation_text += ngettext(
            f", along with {other_count} other reservation",
            f", along with {other_count} other reservations",
            reservation_count,
        )

    # This is some assumption, may break in future if statuses change.
    if checked_in:
        reservation_text += gettext(
            " and you are *checked in*.\n\n_I can only check you out if you'd like..._"
        )
    elif checked_out:
        reservation_text += gettext(
            " and you are *checked out*.\n\n_There is nothing I can do for you (for now)..._"
        )
    else:
        reservation_text += gettext(".\n\n_Are you working today? If so, where?_")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": reservation_text,
            },
        },
    ]

    # Conditionally add actions.
    action_elements = []
    has_any_reservation = any(
        [has_home_reservation, has_office_reservation, has_external_reservation]
    )

    # Home shortcut?
    if not checked_in and not checked_out:
        action_elements.append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": gettext("???? Working home"),
                },
                "confirm": {
                    "title": {
                        "type": "plain_text",
                        "text": gettext("Are you sure?"),
                    },
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "???? You're working from home today.\n\nI will book a home spot for you, if you don't have one yet."
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
            }
        )

    # Office shortcut?
    if has_office_reservation and not checked_in and not checked_out:
        action_elements.append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": gettext("???? Working in the office"),
                },
                "confirm": {
                    "title": {
                        "type": "plain_text",
                        "text": gettext("Are you sure?"),
                    },
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "???? You're working at the office today.\n\nThis only works if you already have a reservation.\nI will check you in if you are not already, no matter what time your reservation is."
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
            }
        )

    # External shortcut? (when enabled)
    if (
        settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME
        and not checked_in
        and not checked_out
    ):
        action_elements.append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": gettext("???? Working externally"),
                },
                "confirm": {
                    "title": {
                        "type": "plain_text",
                        "text": gettext("Are you sure?"),
                    },
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "???? You're working externally.\n\nI will book an 'external' spot for you, if you don't have one yet, and check you in as well."
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
            }
        )

    # Only clear when applicable.
    if has_any_reservation and not checked_out:
        action_elements.append(
            {
                "type": "button",
                "style": "danger",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": gettext("??? Not working"),
                },
                "confirm": {
                    "title": {
                        "type": "plain_text",
                        "text": gettext("Are you sure?"),
                    },
                    "text": {
                        "type": "mrkdwn",
                        "text": gettext(
                            "??? You're not working today or you're already done.\n\nI will delete your pending reservations for today (if any).\nAlso, if you were already checked in, I'll check you out now."
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
            }
        )

    # We may end up with no buttons.
    if action_elements:
        blocks.extend(
            [
                {
                    "type": "actions",
                    "elements": action_elements,
                }
            ]
        )

    return blocks


def handle_user_working_home_today(botmydesk_user: BotMyDeskUser, payload):
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    try:
        home_reservations_result = bmd_api_client.client.list_reservations_v3(
            botmydesk_user, type="home"
        )
        profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)
    except BookMyDeskException as error:
        slack_web_client().chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    found_home_reservation = False

    for current in home_reservations_result.reservations():
        if current.owner_id() != profile.id():
            # Ignore delegates
            continue

        found_home_reservation = True
        break

    if found_home_reservation:
        report_text = gettext(
            "?????? _I left it as-is, since you already *booked a home spot*._"
        )
    else:
        local_start = timezone.localtime(
            timezone.now(), timezone=botmydesk_user.user_tz_instance()
        )
        local_end = local_start.replace(hour=23, minute=59)
        try:
            bmd_api_client.client.create_reservation_v3(
                botmydesk_user=botmydesk_user,
                reservation_type="home",
                start=local_start,
                end=local_end,
            )
        except BookMyDeskException:
            report_text = gettext(
                "?????? Failed to book you for working at home. Please try manually."
            )
        else:
            report_text = gettext("?????? _I booked you a home spot._")

    update_user_app_home(botmydesk_user=botmydesk_user)

    message_to_user = gettext(
        f"???? _You requested me to book you for working at home._\n\n\n{report_text}"
    )
    _post_handle_report_update(botmydesk_user, message_to_user, payload)


def handle_user_working_in_office_today(botmydesk_user: BotMyDeskUser, payload):
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(
            botmydesk_user,
            type="normal",
        )
        profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)
    except BookMyDeskException as error:
        slack_web_client().chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Worst-case.
    report_text = gettext(
        "?????? No office reservation found for this day. Please book an office seat and check-in anyway."
    )

    if reservations_result.reservations():
        for current in reservations_result.reservations():
            if current.owner_id() != profile.id():
                # Ignore delegates
                continue

            # Ignore everything we're not interested in.
            if current.seat() is None:
                continue

            location = current.seat().map_name()
            current_reservation_id = current.id()

            # The logic below just assumes a single reservation. We may or may not want to have it compatible
            # with multiple items in the future (which is way more code than it currently already is).

            if current.status() == "checkedIn":
                report_text = gettext(
                    "?????? _I left it as-is, since you're already *checked in*._"
                )
                break

            if current.status() == "checkedOut":
                report_text = gettext(
                    "?????? _I did nothing, as you seem to be *checked out* already?_"
                )
                break

            if current.status() == "reserved":
                try:
                    bmd_api_client.client.reservation_check_in_out(
                        botmydesk_user, current_reservation_id, check_in=True
                    )
                except BookMyDeskException as error:
                    report_text = gettext(
                        f"?????? *Failed to check you in for your existing reservation*\n ```{error}```"
                    )
                else:
                    report_text = gettext(f"??? _I checked you in at {location}_")
                break

            # Fail-safe for future statuses.
            report_text = gettext(
                "?????? _Unexpected status, **I ignored your request to make sure not breaking anything**!_"
            )
            break

    update_user_app_home(botmydesk_user=botmydesk_user)

    message_to_user = gettext(
        f"???? _You requested me to check you in for the office._\n\n\n{report_text}"
    )
    _post_handle_report_update(botmydesk_user, message_to_user, payload)


def handle_user_working_externally_today(botmydesk_user: BotMyDeskUser, payload):
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    # Only when required/supported.
    if not settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME:
        return (
            slack_web_client()
            .chat_postEphemeral(
                channel=botmydesk_user.slack_user_id,
                user=botmydesk_user.slack_user_id,
                text=gettext("??? Sorry, not supported at this time"),
            )
            .validate()
        )

    try:
        company_extended_result = bmd_api_client.client.company_extended_v3(
            botmydesk_user
        )
    except BookMyDeskException as error:
        return (
            slack_web_client()
            .chat_postEphemeral(
                channel=botmydesk_user.slack_user_id,
                user=botmydesk_user.slack_user_id,
                text=gettext(
                    f"Sorry, an error occurred while requesting company information: ```{error}```"
                ),
            )
            .validate()
        )

    # Find "external" location.
    matches = [
        x
        for x in company_extended_result.locations()
        if x.name() == settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME
    ]
    report_text = ""

    if not matches or not matches[0].maps():
        return (
            slack_web_client()
            .chat_postEphemeral(
                channel=botmydesk_user.slack_user_id,
                user=botmydesk_user.slack_user_id,
                text=gettext("Sorry, failed to find location or map"),
            )
            .validate()
        )

    external_location = matches[0]
    external_map = external_location.maps()[0]

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(
            botmydesk_user, type="normal", mapId=external_map.id()
        )
        profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)
    except BookMyDeskException as error:
        slack_web_client().chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Check whether we only need to check in.
    if reservations_result.reservations():
        for current in reservations_result.reservations():
            if current.owner_id() != profile.id():
                # Ignore delegates
                continue

            # Ignore everything we're not interested in.
            if current.seat() is None:
                continue

            reservation_location = current.seat().map_name()
            current_reservation_id = current.id()

            # The logic below just assumes a single reservation. We may or may not want to have it compatible
            # with multiple items in the future (which is way more code than it currently already is).

            if current.status() == "checkedIn":
                report_text = gettext(
                    "?????? _I left it as-is, since you're already *checked in*._"
                )
                break

            if current.status() == "checkedOut":
                report_text = gettext(
                    "?????? _I did nothing, as you seem to be *checked out* already?_"
                )
                break

            if current.status() == "reserved":
                try:
                    bmd_api_client.client.reservation_check_in_out(
                        botmydesk_user, current_reservation_id, check_in=True
                    )
                except BookMyDeskException as error:
                    report_text = gettext(
                        f"?????? *Failed to check you in for your existing reservation*\n ```{error}```"
                    )
                else:
                    report_text = gettext(
                        f"??? _I checked you in at {reservation_location}_"
                    )
                break

            # Fail-safe for future statuses.
            report_text = gettext(
                "?????? _Unexpected status, *I ignored your request to make sure not breaking anything*!_"
            )
            break

    # No report, assume we can randomly book a spot.
    if not report_text:
        # Worst-case
        report_text = gettext(
            "?????? Failed to book you for working externally. Please try manually."
        )

        local_start = timezone.localtime(
            timezone.now(), timezone=botmydesk_user.user_tz_instance()
        )
        local_end = local_start.replace(hour=23, minute=59)

        for current in external_map.seats():
            try:
                # Just trial and error.
                reservation_id = bmd_api_client.client.create_reservation_v3(
                    botmydesk_user=botmydesk_user,
                    reservation_type="normal",
                    start=local_start,
                    end=local_end,
                    seat_id=current.id(),
                )
            except BookMyDeskException:
                # Try next seat
                continue

            report_text = gettext(
                "_I booked you a spot externally and checked you in._"
            )

            try:
                # Check in as well.
                bmd_api_client.client.reservation_check_in_out(
                    botmydesk_user, reservation_id, check_in=True
                )
            except BookMyDeskException as error:
                report_text = gettext(
                    f"?????? *I booked you a externally spot, but failed to check you in*\n ```{error}```"
                )
                break

    message_to_user = gettext(
        f"???? _You requested me to book and/or check you in for working externally._\n\n\n{report_text}"
    )
    _post_handle_report_update(botmydesk_user, message_to_user, payload)

    update_user_app_home(botmydesk_user=botmydesk_user)


def handle_user_not_working_today(botmydesk_user: BotMyDeskUser, payload):
    """Fetches your reservations of the current day and cancels them all, when applicable."""
    if not botmydesk_user.has_authorized_bot():
        return _unauthorized_reply_shortcut(botmydesk_user)

    try:
        reservations_result = bmd_api_client.client.list_reservations_v3(botmydesk_user)
        profile = bmd_api_client.client.me_v3(botmydesk_user=botmydesk_user)
    except BookMyDeskException as error:
        slack_web_client().chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(
                f"Sorry, an error occurred while requesting your reservations: ```{error}```"
            ),
        ).validate()
        return

    # Create a report per reservation.
    report_text = gettext("?????? No reservations found anyway")

    if reservations_result.reservations():
        report_text = ""

        for current in reservations_result.reservations():
            if current.owner_id() != profile.id():
                # Ignore delegates
                continue

            location = current.location_name_shortcut()

            current_reservation_id = current.id()
            current_status = current.status()
            current_from = current.checked_in_time() or current.from_time()
            current_to = current.checked_out_time() or current.to_time()
            current_reservation_text = gettext(
                f"\n\n\n??? *{current_from} to {current_to}* (*{location}*)"
            )

            # Exclude visitors:
            if current.type() == "visitor":
                continue

            # Do not touch these.
            if current_status in ("checkedOut", "cancelled", "expired"):
                report_text += gettext(
                    f"{current_reservation_text}\n\t\t ?????? _I left it as-is ({current_status})_"
                )
            # Just check out.
            elif current_status in ("checkedIn",):
                try:
                    bmd_api_client.client.reservation_check_in_out(
                        botmydesk_user, current_reservation_id, check_in=False
                    )
                except BookMyDeskException as error:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ?????? *Failed to check you out*\n ```{error}```"
                    )
                else:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ??? _I checked you out_"
                    )
            # Delete.
            elif current_status in ("reserved",):
                try:
                    bmd_api_client.client.delete_reservation_v3(
                        botmydesk_user, current_reservation_id
                    )
                except BookMyDeskException as error:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ?????? *Failed to delete your reservation*\n ```{error}```"
                    )
                else:
                    report_text += gettext(
                        f"{current_reservation_text}\n\t\t ??? _I deleted your reservation_"
                    )
            # Fail-safe for future statuses.
            else:
                report_text += gettext(
                    f"{current_reservation_text}\n\t\t ?????? _Unexpected status, **left untouched**!_"
                )

    update_user_app_home(botmydesk_user=botmydesk_user)

    message_to_user = gettext(
        f"??? _You requested me to clear your reservations._\n\n\n{report_text}"
    )
    _post_handle_report_update(botmydesk_user, message_to_user, payload)


def update_user_app_home(botmydesk_user: BotMyDeskUser):
    apply_user_locale(botmydesk_user)

    if botmydesk_user.has_authorized_bot():
        blocks = [
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "?????? " + gettext("Preferences"),
                        },
                        "value": "open_preferences",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": gettext("Help / Commands"),
                        },
                        "value": "trigger_help",
                    },
                ],
            }
        ]
        blocks.extend(gui_list_upcoming_reservations(botmydesk_user))
    else:
        blocks = [
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "??????? " + gettext("Link BookMyDesk"),
                        },
                        "value": "open_preferences",
                    },
                ],
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": gettext(f"Hi {botmydesk_user.slack_name} ????"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext("My name is")
                    + f" {settings.BOTMYDESK_NAME}, "
                    + gettext(
                        "I'm an unofficial Slack bot for BookMyDesk. I can remind you to check-in at the office or at home. Making life a bit easier for you!"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Click the button above to link your BookMyDesk account."
                    ),
                },
            },
        ]

    slack_web_client().views_publish(
        user_id=botmydesk_user.slack_user_id,
        view={
            "type": "home",
            "blocks": blocks,
        },
    ).validate()


def _post_handle_report_update(
    botmydesk_user: BotMyDeskUser,
    message_to_user: str,
    payload: dict,
):
    today_text = timezone.localtime(
        timezone.now(), timezone=botmydesk_user.user_tz_instance()
    ).strftime("%A %-d %B")
    title = gettext(f"{today_text} update")

    slack_web_client().chat_postMessage(
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
        # Delete trigger, if any was given. Also, do not validate as it MAY fail.
        slack_web_client().chat_delete(
            channel=payload["container"]["channel_id"],
            ts=payload["container"]["message_ts"],
        )
    except KeyError:
        pass


def _unauthorized_reply_shortcut(botmydesk_user: BotMyDeskUser):
    slack_web_client().chat_postEphemeral(
        channel=botmydesk_user.slack_user_id,
        user=botmydesk_user.slack_user_id,
        text=gettext("??? Sorry, you will need to connect me first."),
    ).validate()
