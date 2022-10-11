# syntax=docker/dockerfile:1

FROM python:3-alpine AS base-app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
WORKDIR /code

RUN apk add \
    mariadb-dev \
    py3-mysqlclient \
    python3-dev \
    musl-dev \
    postgresql-dev \
    build-base \
    gettext
RUN python3 -m venv $VIRTUAL_ENV

# Credits to: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --upgrade pip && pip3 install poetry



### Production.
FROM base-app AS prod-app
ARG BUILD_GUNICORN_SOCKET
ENV GUNICORN_SOCKET=$BUILD_GUNICORN_SOCKET

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install --only main
COPY src/ /code/

#ENTRYPOINT poetry run gunicorn --log-level debug --bind unix:$BUILD_GUNICORN_SOCKET --workers 1 --max-requests 100 --timeout 30 botmydesk.wsgi
ENTRYPOINT poetry run gunicorn --bind unix:$GUNICORN_SOCKET --workers 1 --max-requests 100 --timeout 30 botmydesk.wsgi



### Development.
FROM base-app AS dev-app

COPY src/poetry.lock src/pyproject.toml /code/
RUN poetry install

#ENTRYPOINT poetry run /code/manage.py dev_socket_mode
#ENTRYPOINT poetry run /code/manage.py runserver 0.0.0.0:8000
