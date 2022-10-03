import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views import View
from slack_sdk.signature import SignatureVerifier

import bmd_slashcmd.services
import bmd_hooks.services
import bmd_core.services


botmydesk_logger = logging.getLogger("botmydesk")


def verify_request(request: HttpRequest) -> bool:
    verifier = SignatureVerifier(settings.SLACK_BOT_SIGNING_SECRET)

    return verifier.is_valid_request(body=request.body, headers=request.headers)


class SlackEventView(View):
    """https://api.slack.com/events"""

    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.error("Dropped invalid Slack event request")
            return HttpResponseBadRequest()

        payload = json.loads(request.body)
        event_type = payload.get("type")
        botmydesk_logger.info(f"Handling Slack event request: {payload}")

        if event_type == "url_verification":
            return JsonResponse({"challenge": payload.get("challenge")})

        return HttpResponse()


class SlackInteractivityView(View):
    """https://api.slack.com/reference/interaction-payloads"""

    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.error("Dropped invalid Slack interactivity request")
            return HttpResponseBadRequest()

        payload = json.loads(request.POST.get("payload"))
        botmydesk_logger.info(f"Handling Slack interactivity request: {payload}")

        web_client = bmd_hooks.services.slack_web_client()
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            web_client=web_client, slack_user_id=payload.get("user_id")
        )

        if payload["type"] == "view_submission":
            result = bmd_slashcmd.services.on_interactive_view_submission(
                web_client=web_client,
                botmydesk_user=botmydesk_user,
                payload=payload,
            )

            if result is not None:
                return JsonResponse(result)

        elif payload["type"] == "block_action":
            for current_action in payload["actions"]:
                bmd_slashcmd.services.on_interactive_block_action(
                    web_client=web_client,
                    botmydesk_user=botmydesk_user,
                    action=current_action,
                    **payload,
                )

        return HttpResponse()


class SlackSlashCommandView(View):
    """https://api.slack.com/interactivity/slash-commands"""

    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.error("Dropped invalid Slack slash command request")
            return HttpResponseBadRequest()

        payload = request.POST.dict()
        botmydesk_logger.info(f"Handling Slack slash command request: {payload}")

        web_client = bmd_hooks.services.slack_web_client()
        botmydesk_user = bmd_core.services.get_botmydesk_user(
            web_client=web_client, slack_user_id=payload.get("user_id")
        )

        bmd_slashcmd.services.handle_slash_command(
            web_client=web_client, botmydesk_user=botmydesk_user, **payload
        )

        # For now just empty response. We'll send commands tru the web client.
        return HttpResponse()
