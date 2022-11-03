"""
Django settings for botmydesk project.

Generated by 'django-admin startproject' using Django 4.1.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

from pathlib import Path
import os

from decouple import config, Csv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("DJANGO_SECRET_KEY", cast=str)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DJANGO_DEBUG", cast=bool, default=False)

ALLOWED_HOSTS = [config("DJANGO_ALLOWED_HOST", cast=str)]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "bmd_core",
    "bmd_hooks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",  # Useless for APIs anyway.
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "botmydesk.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "botmydesk.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": config("DJANGO_DATABASE_ENGINE", cast=str),
        "HOST": config("DJANGO_DATABASE_HOST", cast=str, default=None),
        "PORT": config("DJANGO_DATABASE_PORT", cast=str, default=None),
        "USER": config("DJANGO_DATABASE_USER", cast=str, default=None),
        "PASSWORD": config("DJANGO_DATABASE_PASSWORD", cast=str, default=None),
        "NAME": config("DJANGO_DATABASE_NAME", cast=str),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = config("DJANGO_TIMEZONE")

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locales"),)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

""" Python Logging. """
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname:8} | {message}",
            "style": "{",
        },
        "verbose": {
            "format": "{asctime} {levelname:8} {module:12} {funcName:30} {lineno:4} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "botmydesk": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "bookmydesk_client": {
            "handlers": ["console"],
            "level": "INFO",
            " propagate": False,
        },
        "django.db": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

if DEBUG:
    LOGGING["loggers"]["botmydesk"]["level"] = "DEBUG"
    LOGGING["loggers"]["bookmydesk_client"]["level"] = "DEBUG"

# Project related.
BOTMYDESK_USER_AGENT = "BotMyDesk Slack Bot"
BOTMYDESK_NAME = "BotMyDesk"

SLACK_APP_TOKEN = config(
    "SLACK_APP_TOKEN", cast=str, default=""
)  # Ony required for Socket Mode.
SLACK_BOT_TOKEN = config("SLACK_BOT_TOKEN", cast=str)
SLACK_BOT_SIGNING_SECRET = config("SLACK_BOT_SIGNING_SECRET", cast=str)

BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES = config(
    "DEV_BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES",
    cast=int,
    default=15,  # Low to make it refresh often
)
BOOKMYDESK_API_URL = config("BOOKMYDESK_API_URL", cast=str)
BOOKMYDESK_CLIENT_ID = config("BOOKMYDESK_CLIENT_ID", cast=str)
BOOKMYDESK_CLIENT_SECRET = config("BOOKMYDESK_CLIENT_SECRET", cast=str)

SLACK_SLASHCOMMAND_BMD = config("SLACK_SLASHCOMMAND_BMD", cast=str)

BOTMYDESK_OWNER_SLACK_ID = config("BOTMYDESK_OWNER_SLACK_ID", cast=str, default="")
BOTMYDESK_WHITELISTED_SLACK_IDS = config(
    "BOTMYDESK_WHITELISTED_SLACK_IDS", cast=Csv(post_process=tuple), default=""
)
BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME = config(
    "BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME", cast=str, default=None
)

# Sub commands and aliases
SLACK_SLASHCOMMAND_BMD_DEBUGP = "debug"
SLACK_SLASHCOMMAND_BMD_HELP = "help"
SLACK_SLASHCOMMAND_BMD_SETTINGS = "settings"
SLACK_SLASHCOMMAND_BMD_STATUS = "status"
SLACK_SLASHCOMMAND_BMD_MARK_AT_HOME = "home"
SLACK_SLASHCOMMAND_BMD_MARK_AT_OFFICE = "office"
SLACK_SLASHCOMMAND_BMD_MARK_EXTERNALLY = "extern"
SLACK_SLASHCOMMAND_BMD_MARK_CANCELLED = "clear"

# Celery
# https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html#django-first-steps
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = None
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
# Celery Beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
