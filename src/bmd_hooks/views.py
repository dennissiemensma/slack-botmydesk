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


class SlackInteractivityEventView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.error("Dropped invalid Slack interactivity request")
            return HttpResponseBadRequest()

        botmydesk_logger.info(f"Handling Slack interactivity request: {request.body}")

        parsed_body = json.loads(request.body)
        event_type = parsed_body.get("type")

        if event_type == "url_verification":
            return JsonResponse({"challenge": parsed_body.get("challenge")})

        return HttpResponse()  # @TODO


class SlackSlashCommandView(View):
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
            web_client=web_client,
            botmydesk_user=botmydesk_user,
            text=payload.get("text"),
            payload=payload,
        )

        # For now just empty response. We'll send commands tru the web client.
        return HttpResponse()
