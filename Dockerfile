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
    build-base
RUN python3 -m venv $VIRTUAL_ENV

# Credits to: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY poetry.lock pyproject.toml /code/
RUN python3 -m pip install --upgrade pip && \
    pip3 install poetry && \
    poetry install --no-dev



FROM base-app AS dev-app
RUN poetry install
RUN rm /code/poetry.lock /code/pyproject.toml
#ENTRYPOINT poetry run /code/manage.py runserver 0.0.0.0:8000
#ENTRYPOINT poetry run /code/manage.py dev_socket_mode



FROM base-app AS prod-app
RUN rm /code/poetry.lock /code/pyproject.toml
COPY src/ /code/
ENTRYPOINT poetry run gunicorn --timeout 10 --workers 4 --max-requests 100 --bind 127.0.0.1:8080 botmydesk.wsgi
