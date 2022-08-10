# Slack: BotMyDesk

## Setup
- Create you app/bot: https://api.slack.com/apps

Required Bot Token Scopes:
```
# App -> OAuth & Permissions -> Scopes (and NOT "User Token Scopes")
commands
chat:write
im:read
im:write
users:read
users:read.email
```

- Also, ensure to activate (direct) messaging for your **App**:
```
# App -> Features -> App Home -> Scroll down the page.
Allow users to send Slash commands and messages from the messages tab
```

You will also need your:
- App-Level token
- Bot-level token

- Make sure it has the following "slash command(s)":

_You can choose any command name you'd like and configure/override it as env var of this bot._

| Slash command  | Description        | Parameters                           |
|:---------------|--------------------|:-------------------------------------|
| `/botmydesk`   | Access bot options | -                                    |


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
