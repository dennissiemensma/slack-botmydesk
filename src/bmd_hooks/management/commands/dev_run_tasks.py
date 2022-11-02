from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import bmd_core.tasks


class Command(BaseCommand):
    help = "DEV ONLY: Runs tasks manually"

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Only supported in DEBUG mode")

        bmd_core.tasks.dispatch_botmydesk_notifications()
