# https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html#django-first-steps
import os

from celery import Celery
from celery.schedules import crontab


# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "botmydesk.settings")

app = Celery("botmydesk")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "refresh-all-bookmydesk-sessions": {
        "task": "bmd_core.tasks.refresh_all_bookmydesk_sessions",
        "schedule": crontab(hour=0, minute=0),
    },
    "sync-botmydesk-app-homes": {
        "task": "bmd_core.tasks.sync_botmydesk_app_homes",
        "schedule": crontab(hour="*/4", minute=5),
    },
}
