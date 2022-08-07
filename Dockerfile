# syntax=docker/dockerfile:1

FROM python:3 AS base-app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /src

RUN apt-get update && \
    apt-get install -y \
        xxd \
        python3 \
        python3-pip \
        python3-venv

# Credits to: https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY pyproject.toml /src/
RUN pip3 install pip --upgrade && \
    pip3 install poetry && \
    poetry install --no-dev


FROM base-app AS dev-app
RUN poetry install
ENTRYPOINT python3 manage.py runserver 0.0.0.0:8000


FROM base-app AS prod-app
RUN apt-get install -y xxd
RUN printf "\nDJANGO_SECRET_KEY=$( xxd -l30 -ps /dev/urandom)\n" > .env
