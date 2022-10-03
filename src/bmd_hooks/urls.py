from django.urls import path

from bmd_hooks.views import (
    SlackEventView,
    SlackInteractivityView,
    SlackSlashCommandView,
)

app_name = "hooks"

urlpatterns = [
    path("slack/event", SlackEventView.as_view()),
    path("slack/interactivity", SlackInteractivityView.as_view()),
    path("slack/slashcommand", SlackSlashCommandView.as_view()),
]
