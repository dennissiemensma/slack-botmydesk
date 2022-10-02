# Slack: BotMyDesk
_This project is NOT officially affiliated with BookMyDesk in any way!_

## Setup
Create your Slack app/bot: 
- Go to: https://api.slack.com/apps
- _"Create an app"_ -> _"From scratch"_
- App name, for example: _"BotMyDesk"_

After creation, go to **Socket Mode** first.
*This is only required if you want to run this bot in development mode!*

Enable "Socket Mode" and create an App-level token, which you'll need later anyway.
The default ``connections:write`` scope will suffice.

- Set the generated **App-level token** as ``SLACK_APP_TOKEN`` env var (or in ``.env``) later.

- Now go to **App Home**, scroll down the page and ensure to activate (direct) messaging for your **App** by clicking the checkbox for:

```
Allow users to send Slash commands and messages from the messages tab
```

- Go to **Slash Commands**, create a new command and make sure it has the following "slash command(s)":

| Slash command | Description                               | Parameters                           |
|:--------------|-------------------------------------------|:-------------------------------------|
| `/bmd`        | Access BotMyDesk commands and preferences | help                                 |

*Note: You can choose any command name you'd like and override it as ``SLACK_SLASHCOMMAND_BMD`` env var.*


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

Finally, scroll up at _"OAuth & Permissions"_ and click the **Install to Workspace** button.
This will prompt you to install it for your workspace and redirect back to _"OAuth & Permissions"_. 

- You should now see a _"Bot User OAuth Token"_ there. Save it and set it (later) as ``SLACK_BOT_TOKEN`` env var (or in your ``.env`` below).


----


## Installation
### (Local) development
Install poetry, e.g.:
```shell
# Debian
apt-get install python3-pip
pip install poetry
```

Now:
```shell
poetry config virtualenvs.in-project true
poetry install

cp docker-compose.override.yml.DEV.TEMPLATE docker-compose.override.yml
cp .env.TEMPLATE .env
```
Set your env vars in ``.env`` or ``docker-compose.override.yml``.
Run this to bootstrap the app/bot:

```shell
docker-compose up -d
```

#### Translations
- Currently supported: `en`, `nl`
- Did you change strings? Generate PO file using all translation tags/strings in codebase:
```shell
./manage.py makemessages --no-wrap --no-location --locale nl 
```
- The source translation (PO) file, e.g. [src/locales/nl/LC_MESSAGES/django.po](src/locales/nl/LC_MESSAGES/django.po), should be updated.
- Translate any additions or changes with `Poedit` (or whatever program you'd like to use).


### Production/deploy

- Checkout the code base
- Install Docker/Docker-compose
- Run:
```shell
cp docker-compose.override.yml.PROD.TEMPLATE docker-compose.override.yml

# Load your .env on your server or use real env vars. 
# Either way, see the env template for what you need.
cp .env.TEMPLATE .env
```

- Build images:
```shell
docker-compose build
```

- Before each deploy, make sure to run database migrations first:
```shell
docker-compose -f docker-compose.override.yml exec app poetry run /code/manage.py migrate --noinput
```

- Run:
```shell
docker-compose up -d
```

- Go back to Slack, open your Bot settings and go to **Interactivity & Shortcuts** and enter the following URL:
```shell
https://<YOUR HOSTNAME>/hooks/slack/interactivity
```

- Add a similar URL for your slash command in the Slack bot settings:
```shell
https://<YOUR HOSTNAME>/hooks/slack/slashcommand
```

Now go to you Bot its **Basic Information** and find the "Signing Secret":

- Set the value of the **Signing Secret** as ``SLACK_BOT_SIGNING_SECRET`` env var (or in ``.env``) in your BotMyDesk hosting.
