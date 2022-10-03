# Slack: BotMyDesk
_This project is NOT officially affiliated with BookMyDesk in any way!_

## Setup
Create your Slack app/bot: 
- Go to: https://api.slack.com/apps
- _"Create an app"_ -> _"From scratch"_
- App name, for example: _"BotMyDesk"_

----

- After creation, go to **Socket Mode** first.
*This is only required if you want to run this bot in development mode!*

- Enable "Socket Mode" and create an App-level token, which you'll need later anyway. The default ``connections:write`` scope will suffice.


- Now go to **App Home**, scroll down the page and ensure to activate (direct) messaging for your **App** by clicking the checkbox for:

> "Allow users to send Slash commands and messages from the messages tab"

- Go to **Slash Commands**, create a new command and make sure it has the following "slash command(s)":

| Slash command | Description                               | Parameters                           |
|:--------------|-------------------------------------------|:-------------------------------------|
| `/bmd`        | Access BotMyDesk commands and preferences | help                                 |

*Note: You can choose any command name you'd like and override it as ``SLACK_SLASHCOMMAND_BMD`` env var. Also, you can omit the "Request URL" until you go production.*


- Open **OAuth & Permissions**, scroll down to _"Scopes"_ and add these **Bot Token Scopes**:
```
commands
chat:write
im:read
im:write
users:read
users:read.email
users:write
```

- Scroll up at _"OAuth & Permissions"_ and click the **Install to Workspace** button.
This will prompt you to install it for your workspace and redirect back to _"OAuth & Permissions"_. 

- Finally, go back to Slack, open your Bot settings and set these as env var (or in ``.env``) in your development setup:

```shell
# Slack -> Your Bot -> OAuth & Permissions -> Bot User OAuth Token
SLACK_BOT_TOKEN=
# Slack -> Your Bot -> Basic Information -> App Credentials -> Signing Secret
SLACK_BOT_SIGNING_SECRET=
```

```shell
# (only required when running Socket Mode)
# Slack -> Your Bot -> Basic Information -> App-Level Tokens
SLACK_APP_TOKEN=
```


----


## Installation
### (Local) development
If you want your IDE to detect packages code, install ``poetry`` on your host, e.g.:
```shell
# Debian
apt-get install python3-pip
pip install poetry
```

- After that (or if you skipped it):
```shell
poetry config virtualenvs.in-project true
poetry install

cp docker-compose.override.yml.DEV.TEMPLATE docker-compose.override.yml
cp .env.TEMPLATE .env
```

- Set your env vars in ``.env`` or ``docker-compose.override.yml``.

- Run this to bootstrap the app/bot:

```shell
docker-compose up -d
```

#### Translations
- Currently supported: `en`, `nl`
- Did you change strings? Regenerate PO file using all translation tags/strings marked in the codebase:
```shell
docker exec -it botmydesk_dev_app poetry run /code/manage.py makemessages --no-wrap --no-location --locale nl
```
- The source translation (PO) file, e.g. [src/locales/nl/LC_MESSAGES/django.po](src/locales/nl/LC_MESSAGES/django.po), should be updated.
- Translate any additions or changes with `Poedit` (or whatever program you'd like to use).


----

### Production hosting

- Checkout the code base
- Install Docker/Docker-compose
- Run:
```shell
cp docker-compose.override.yml.PROD.TEMPLATE docker-compose.override.yml

# Load your .env on your server or use real env vars. 
# Either way, see the env template for what you need.
cp .env.TEMPLATE .env
```

- Configure all env vars for your hosting. Some should remain blank and will be updated below.

----

- Go back to Slack, open your Bot settings and set these as env var (or in .env) in your BotMyDesk hosting:

```shell
# Slack -> Your Bot -> OAuth & Permissions -> Bot User OAuth Token
SLACK_BOT_TOKEN=
# Slack -> Your Bot -> Basic Information -> App Credentials -> Signing Secret
SLACK_BOT_SIGNING_SECRET=
```

- Build images:
```shell
docker-compose build
```

- Before each (re)deploy, make sure to run database migrations first:
```shell
docker-compose -f docker-compose.override.yml exec app poetry run /code/manage.py migrate --noinput
```

- Run:
```shell
docker-compose up -d
```

----

Your bot should now be ready to receive requests.

Go back to Slack, open your Bot settings for the following configuration.

#### Interactivity & Shortcuts 

- Enter the following "Request URL":
```shell
https://<YOUR BOT HOSTNAME>/hooks/slack/interactivity
```
- Save changes *(bottom)*

#### Slash Commands
- Find the `/bmd` command (or add it) and enter the following "Request URL":
```shell
https://<YOUR BOT HOSTNAME>/hooks/slack/slashcommand
```
- Save changes

#### Event Subscriptions
- Toggle "Enable Events"
- Enter the following "Request URL":
```shell
https://<YOUR BOT HOSTNAME>/hooks/slack/event
```
- It should validate.
- Scroll down to "Subscribe to bot event"
- Add ``app_home_opened `` event *(no permissions required)*
- Save changes *(bottom)*

----

- Live logs:
```shell
docker-compose logs -f
```
