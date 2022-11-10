# syntax=docker/dockerfile:1

FROM python:3-alpine AS base-app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
WORKDIR /code

RUN apk add --update \
    python3-dev \
    musl-dev \
    postgresql-dev \
    build-base \
    musl-locales \
    musl-locales-lang \
    gettext

# Credits to: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --upgrade pip && pip3 install poetry



### Production app.
FROM base-app AS prod-app
ARG BUILD_GUNICORN_WORKERS=1
ARG BUILD_GUNICORN_MAX_REQUESTS=100
ARG BUILD_GUNICORN_TIMEOUT=30

ENV GUNICORN_WORKERS=$BUILD_GUNICORN_WORKERS
ENV GUNICORN_MAX_REQUESTS=$BUILD_GUNICORN_MAX_REQUESTS
ENV GUNICORN_TIMEOUT=$BUILD_GUNICORN_TIMEOUT
ENV DJANGO_DEBUG=False

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install --only main
COPY src/ /code/

# See https://docs.gunicorn.org/en/stable/settings.html#bind
# Use "--log-level debug" for more details.
ENTRYPOINT poetry run /code/manage.py migrate --noinput ; \
           poetry run /code/manage.py compilemessages ; \
           poetry run gunicorn \
                --bind 0.0.0.0:8000 \
                --workers $GUNICORN_WORKERS \
                --max-requests $GUNICORN_MAX_REQUESTS \
                --timeout $GUNICORN_TIMEOUT \
                botmydesk.wsgi


### Production task scheduler.
FROM prod-app AS prod-app-scheduler
ENV DJANGO_DEBUG=False
ENTRYPOINT poetry run celery -A botmydesk beat -l INFO


### Production task worker.
FROM prod-app AS prod-app-worker
ENV DJANGO_DEBUG=False
ENTRYPOINT poetry run celery -A botmydesk worker -l INFO



### Development.
FROM base-app AS dev-app
ENV DJANGO_SECRET_KEY=development
ENV DJANGO_DEBUG=True

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install
# No ENTRYPOINT, run manually instead (e.g. docker-compose file).
