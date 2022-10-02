from django.urls import path

from bmd_hooks.views import SlackInteractivityEventView


app_name = "hooks"

urlpatterns = [
    path("slack/interactivity", SlackInteractivityEventView.as_view()),
]
