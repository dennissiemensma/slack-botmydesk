import logging
from typing import Optional

from decouple import config
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext

from bmd_api_client.exceptions import BookMyDeskException
from bmd_core.models import BotMyDeskUser
import bmd_api_client.client
import bmd_core.services
import bmd_hooks.services.slash


botmydesk_logger = logging.getLogger("botmydesk")


def on_interactive_block_action(
    botmydesk_user: BotMyDeskUser, action: str, payload: dict
):
    """Respond to user (inter)actions. Some are follow-ups, some are aliases."""
    try:
        service_module = {
            "send_bookmydesk_login_code": handle_interactive_send_bookmydesk_login_code,
            "revoke_botmydesk": handle_interactive_bmd_revoke_botmydesk,
            "open_preferences": bmd_hooks.services.slash.handle_preferences_gui,  # Alias
            "mark_working_from_home_today": bmd_core.services.handle_user_working_home_today,
            "mark_working_at_the_office_today": bmd_core.services.handle_user_working_in_office_today,
            "mark_working_externally_today": bmd_core.services.handle_user_working_externally_today,
            "mark_not_working_today": bmd_core.services.handle_user_not_working_today,
        }[action]
    except KeyError:
        raise NotImplementedError(f"Unknown block action: {action}")

    service_module(botmydesk_user, payload)


def on_interactive_view_submission(
    botmydesk_user: BotMyDeskUser, payload: dict
) -> Optional[dict]:
    view_callback_id = payload["view"]["callback_id"]

    try:
        service_module = {
            "bmd-modal-authorize-login-code": handle_interactive_bmd_authorize_login_code_submit,
        }[view_callback_id]
    except KeyError:
        raise NotImplementedError(f"Unknown view callback ID: {view_callback_id}")

    return service_module(botmydesk_user, payload)


def handle_interactive_send_bookmydesk_login_code(
    botmydesk_user: BotMyDeskUser, payload: dict
):
    view_data = {
        "type": "modal",
        "callback_id": "bmd-modal-authorize-login-code",
        "title": {
            "type": "plain_text",
            "text": gettext(f"Connecting {settings.BOTMYDESK_NAME}"),
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"Check your mailbox for *{botmydesk_user.slack_email}*. Enter the BookMyDesk login code you've received."
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "otp_user_input_block",
                "label": {
                    "type": "plain_text",
                    "text": gettext("Login code"),
                },
                "element": {
                    "action_id": "otp_user_input",
                    "focus_on_load": True,
                    "type": "plain_text_input",
                    "dispatch_action_config": {
                        "trigger_actions_on": ["on_enter_pressed"]
                    },
                    "placeholder": {
                        "type": "plain_text",
                        "text": "123456",
                    },
                    "min_length": 6,
                    "max_length": 6,
                },
            },
        ],
        "submit": {"type": "plain_text", "text": gettext("Verify login code")},
    }

    email_address = botmydesk_user.slack_email

    if (
        settings.DEBUG
        and config("DEV_EMAIL_ADDRESS", cast=str, default=None) is not None
    ):
        email_address = config("DEV_EMAIL_ADDRESS", cast=str)

    # Request code first, as it MAY fail.
    web_client = bmd_core.services.slack_web_client()

    try:
        bmd_api_client.client.request_login_code(email=email_address)
    except BookMyDeskException as error:
        web_client.chat_postEphemeral(
            channel=botmydesk_user.slack_user_id,
            user=botmydesk_user.slack_user_id,
            text=gettext(f"Sorry, failed to request BookMyDesk login code: `{error}`"),
        ).validate()

        return

    web_client.views_update(
        view_id=payload["view"]["id"],
        hash=payload["view"]["hash"],
        view=view_data,
    ).validate()


def handle_interactive_bmd_revoke_botmydesk(
    botmydesk_user: BotMyDeskUser, payload: dict
):
    web_client = bmd_core.services.slack_web_client()
    view_data = {
        "type": "modal",
        "callback_id": "bmd-disconnected",
        "title": {
            "type": "plain_text",
            "text": gettext(f"{settings.BOTMYDESK_NAME} disconnected"),
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"I've disconnected from your BookMyDesk-account. You can reconnect me in the future by running `{settings.SLACK_SLASHCOMMAND_BMD}` again.\n\nBye! 👋"
                    ),
                },
            },
        ],
    }
    # @see https://api.slack.com/surfaces/modals/using#updating_apis
    result = web_client.views_update(
        view_id=payload["view"]["id"],
        hash=payload["view"]["hash"],
        view=view_data,
    )
    result.validate()

    try:
        # Logout in background.
        bmd_api_client.client.logout(botmydesk_user)
    except BookMyDeskException:
        pass  # Whatever

    # Clear session data. For now, we're not deleting the user to keep their preferences.
    botmydesk_user.clear_tokens()

    title = gettext(f"{settings.BOTMYDESK_NAME} disconnected")
    web_client.chat_postMessage(
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
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        f"I've disconnected from your BookMyDesk-account. You can reconnect me in the future by running `{settings.SLACK_SLASHCOMMAND_BMD}` again.\n\nBye! 👋"
                    ),
                },
            },
        ],
    ).validate()


def handle_interactive_bmd_authorize_login_code_submit(
    botmydesk_user: BotMyDeskUser, payload: dict
) -> Optional[dict]:
    otp = payload["view"]["state"]["values"]["otp_user_input_block"]["otp_user_input"][
        "value"
    ]

    email_address = botmydesk_user.slack_email

    if (
        settings.DEBUG
        and config("DEV_EMAIL_ADDRESS", cast=str, default=None) is not None
    ):
        email_address = config("DEV_EMAIL_ADDRESS", cast=str)

    try:
        login_result = bmd_api_client.client.token_login(
            username=email_address, otp=otp
        )
    except BookMyDeskException:
        return {
            "response_action": "errors",
            "errors": {
                "otp_user_input_block": gettext(
                    "Error validating your login code. You can try it another time or restart this flow to have a new code sent to you."
                )
            },
        }

    botmydesk_user.update(
        bookmydesk_access_token=login_result.access_token(),
        bookmydesk_access_token_expires_at=timezone.now()
        + timezone.timedelta(minutes=settings.BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES),
        bookmydesk_refresh_token=login_result.refresh_token(),
    )

    title = gettext(f"{settings.BOTMYDESK_NAME} connected")
    bmd_core.services.slack_web_client().chat_postMessage(
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
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Great! You've connected me to your BookMyDesk-account 👏"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": gettext(
                        "Check out your preferences by clicking the button below, or by going to the 'Home' tab of this bot."
                    ),
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
                            "text": gettext(
                                f"⚙️ {settings.BOTMYDESK_NAME} preferences"
                            ),
                        },
                        "value": "open_preferences",
                    },
                ],
            },
        ],
    ).validate()

    return {"response_action": "clear"}
