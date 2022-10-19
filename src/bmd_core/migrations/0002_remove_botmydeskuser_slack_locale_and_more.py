# Generated by Django 4.1.2 on 2022-10-12 17:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bmd_core", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="botmydeskuser",
            name="slack_locale",
        ),
        migrations.AddField(
            model_name="botmydeskuser",
            name="preferred_locale",
            field=models.CharField(
                choices=[("en", "en"), ("nl", "nl")], default="en", max_length=16
            ),
        ),
    ]
