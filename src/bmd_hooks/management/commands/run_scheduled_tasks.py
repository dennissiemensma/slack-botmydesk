from django.core.management.base import BaseCommand

import bmd_core.tasks


class Command(BaseCommand):
    help = "Manually runs all scheduled tasks. NOT meant as a replacement!"

    def handle(self, **options):
        bmd_core.tasks.refresh_all_bookmydesk_sessions()
        bmd_core.tasks.sync_botmydesk_app_homes()
        bmd_core.tasks.dispatch_botmydesk_notifications()
        bmd_core.tasks.purge_old_messages()
