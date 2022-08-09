# syntax=docker/dockerfile:1

FROM python:3 AS base-app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code

RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv

# Credits to: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY poetry.lock pyproject.toml /code/
RUN pip3 install pip --upgrade && \
    pip3 install poetry && \
    poetry install --no-dev



FROM base-app AS dev-app
RUN poetry install
ENTRYPOINT poetry run /code/manage.py runserver 0.0.0.0:8000



FROM base-app AS prod-app
COPY src/ /code/
ENTRYPOINT poetry run gunicorn --timeout 10 --workers 4 --max-requests 100 --bind 127.0.0.1:8080 botmydesk.wsgi
