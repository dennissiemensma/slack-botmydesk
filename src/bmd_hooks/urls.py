from django.urls import path

from bmd_hooks.views import SlackInteractivityEventView, SlackSlashCommandView

app_name = "hooks"

urlpatterns = [
    path("slack/interactivity", SlackInteractivityEventView.as_view()),
    path("slack/slashcommand", SlackSlashCommandView.as_view()),
]
