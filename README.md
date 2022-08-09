# Slack: BotMyDesk

## Setup
- Create you app/bot: https://api.slack.com/apps
- Make sure it has two "slash commands":

_You can choose any command name you'd like and configure/override it as env var of this bot._

| Slash command    | Description                                                                       | Parameters                            |
|:-----------------|-----------------------------------------------------------------------------------|:--------------------------------------|
| `/bmd-authorize` | Authorize bot access for your BMD account using: https://app.bookmydesk.com/login | ``email-address one-time-login-code`` |
| `/bmd-revoke`    | Revoke bot access for your BMD account                                            | -                                     |

You will need your:
- App-Level token
- Bot-level token

_You should configure these as env vars as well._


## Installation
### Dev
```shell
poetry config virtualenvs.in-project true
poetry install

cp docker-compose.override.yml.DEV.TEMPLATE docker-compose.override.yml
cp .env.TEMPLATE .env

docker-compose up -d
```


### Prod
```shell
cp docker-compose.override.yml.PROD.TEMPLATE docker-compose.override.yml

# Either load your .env on your server or use real env vars. Either way see the env template for what you need.
cp .env.TEMPLATE .env
```
