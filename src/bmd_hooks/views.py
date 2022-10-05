import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views import View
from slack_sdk.signature import SignatureVerifier

import bmd_hooks.services.callbacks


botmydesk_logger = logging.getLogger("botmydesk")


def verify_request(request: HttpRequest) -> bool:
    verifier = SignatureVerifier(settings.SLACK_BOT_SIGNING_SECRET)

    return verifier.is_valid_request(body=request.body, headers=request.headers)


class SlackEventView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.warning(
                "Dropped event request failed passing verification"
            )
            return HttpResponseBadRequest()

        payload = json.loads(request.body)

        # This event we can always respond to. No need to pass on.
        if payload.get("type") == "url_verification":
            # @see https://api.slack.com/events/url_verification
            return JsonResponse({"challenge": payload.get("challenge")})

        try:
            bmd_hooks.services.callbacks.on_event(payload)
        except Exception as error:
            bmd_hooks.services.callbacks.on_error(error)

        return HttpResponse()


class SlackInteractivityView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.warning(
                "Dropped interactivity request failed passing verification"
            )
            return HttpResponseBadRequest()

        payload = json.loads(request.POST.get("payload"))

        try:
            bmd_hooks.services.callbacks.on_interactivity(payload)
        except Exception as error:
            bmd_hooks.services.callbacks.on_error(error)

        return HttpResponse()


class SlackSlashCommandView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        if not verify_request(request):
            botmydesk_logger.warning(
                "Dropped slash command request failed passing verification"
            )
            return HttpResponseBadRequest()

        payload = request.POST.dict()

        try:
            bmd_hooks.services.callbacks.on_slash_command(payload)
        except Exception as error:
            bmd_hooks.services.callbacks.on_error(error)

        return HttpResponse()
