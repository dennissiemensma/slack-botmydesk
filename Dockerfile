# syntax=docker/dockerfile:1

FROM python:3-alpine AS base-app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
WORKDIR /code

RUN apk add --update \
    mariadb-dev \
    py3-mysqlclient \
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
ARG BUILD_GUNICORN_SOCKET
ENV GUNICORN_SOCKET=$BUILD_GUNICORN_SOCKET
ENV DJANGO_DEBUG=False

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install --only main
COPY src/ /code/

ENTRYPOINT poetry run gunicorn --bind unix:$GUNICORN_SOCKET --workers 1 --max-requests 100 --timeout 30 botmydesk.wsgi


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

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install
# No ENTRYPOINT, run manually instead (e.g. docker-compose file).
