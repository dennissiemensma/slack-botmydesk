import logging
import traceback
import pprint
from typing import Optional

from django.conf import settings
from django.utils.translation import gettext

import bmd_core.services
import bmd_hooks.services.slash
import bmd_hooks.services.interactivity
import bmd_hooks.services.event


botmydesk_logger = logging.getLogger("botmydesk")


def on_event(payload: dict):
    """https://api.slack.com/events"""
    botmydesk_logger.info(
        f"Processing Slack event: {pprint.pformat(payload, indent=2)}"
    )
    event_type = payload["event"]["type"]

    try:
        service_module = {
            "app_home_opened": bmd_hooks.services.event.handle_app_home_opened_event,
        }[event_type]
    except KeyError:
        raise NotImplementedError(f"Event unknown or not implemented: {event_type}")

    service_module(payload)


def on_slash_command(payload: dict):
    """https://api.slack.com/interactivity/slash-commands"""
    command = payload["command"]
    botmydesk_logger.info(f"Processing Slack slash command: {command}")
    slack_user_id = payload["user_id"]

    try:
        bmd_core.services.validate_botmydesk_user(slack_user_id=slack_user_id)
    except EnvironmentError as error:
        return on_error(error, slack_user_id=slack_user_id)

    botmydesk_user = bmd_core.services.get_botmydesk_user(slack_user_id)
    bmd_core.services.apply_user_locale(botmydesk_user)

    try:
        service_module = {
            settings.SLACK_SLASHCOMMAND_BMD: bmd_hooks.services.slash.handle_slash_command,
        }[command]
    except KeyError:
        raise NotImplementedError(
            f"Slash command unknown or not implemented: {command}"
        )

    service_module(botmydesk_user, payload)


def on_interactivity(payload: dict):
    """https://api.slack.com/interactivity"""
    botmydesk_logger.info(
        f"Processing Slack interactivity: {pprint.pformat(payload, indent=2)}"
    )
    slack_user_id = payload["user"]["id"]

    try:
        bmd_core.services.validate_botmydesk_user(slack_user_id=slack_user_id)
    except EnvironmentError as error:
        return on_error(error, slack_user_id=slack_user_id)

    botmydesk_user = bmd_core.services.get_botmydesk_user(slack_user_id=slack_user_id)
    bmd_core.services.apply_user_locale(botmydesk_user)

    # Handle submits.
    if payload["type"] == "view_submission":
        response_payload = (
            bmd_hooks.services.interactivity.on_interactive_view_submission(
                botmydesk_user, payload
            )
        )

        # Conditional response. E.g. for closing modal dialogs or form errors.
        if response_payload is not None:
            # @TODO respond with response_payload?
            pass

    # Handle UX updates.
    elif payload["type"] == "block_actions":
        for current_action in payload["actions"]:
            bmd_hooks.services.interactivity.on_interactive_block_action(
                botmydesk_user,
                current_action,
                payload,
            )


def on_error(error: Exception, slack_user_id: Optional[str] = None):
    """For stacktrace log, optionally DM user as well."""
    error_trace = "\n".join(traceback.format_exc().splitlines())
    botmydesk_logger.error(
        f"Unexpected error: {error} ({error.__class__})\n{error_trace}"
    )

    if slack_user_id is None:
        return

    title = gettext(f"{settings.BOTMYDESK_NAME}: Unexpected error")
    web_client = bmd_core.services.slack_web_client()
    web_client.chat_postEphemeral(
        channel=slack_user_id,
        user=slack_user_id,
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
                        "text": gettext("I'm not sure what to do, sorry! 🤷‍♀"),
                    },
                    {
                        "type": "mrkdwn",
                        "text": gettext(
                            f"_Please tell my creator that the following happened_:\n\n```{error}```"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": gettext(f"_Triggered by_:\n\n```{error_trace}```"),
                    },
                    {
                        "type": "mrkdwn",
                        # @see https://api.slack.com/reference/surfaces/formatting#linking-urls
                        "text": gettext(
                            f"_Report to <{settings.BOTMYDESK_OWNER_SLACK_ID}>_ 🤨"
                            if settings.BOTMYDESK_OWNER_SLACK_ID
                            else " "
                        ),
                    },
                ],
            },
        ],
    ).validate()
