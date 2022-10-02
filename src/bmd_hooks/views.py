import json
import logging

from django.http import JsonResponse, HttpRequest
from django.views import View


botmydesk_logger = logging.getLogger("botmydesk")


class SlackInteractivityEventView(View):
    def post(self, request: HttpRequest):
        parsed_body = json.loads(request.body)
        event_type = parsed_body.get("type")

        botmydesk_logger.info(f"Incoming Slack interactivity: {event_type}")

        if event_type == "url_verification":
            return JsonResponse({"challenge": parsed_body.get("challenge")})

        botmydesk_logger.info(f"Incoming Slack request: {request.body}")

        return JsonResponse({})  # @TODO
