#!/bin/bash
set -e

if [ "$1" = 'gunicorn' ]; then
    exec poetry run /code/manage.py migrate --noinput;
    exec poetry run /code/manage.py compilemessages;

        # See https://docs.gunicorn.org/en/stable/settings.html#bind
    # Use "--log-level debug" for more details.
    exec poetry run gunicorn \
        --bind 0.0.0.0:8000 \
        --workers $GUNICORN_WORKERS \
        --max-requests $GUNICORN_MAX_REQUESTS \
        --timeout $GUNICORN_TIMEOUT \
        botmydesk.wsgi;
fi

exec "$@"
