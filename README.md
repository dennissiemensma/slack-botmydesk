# Slack: BotMyDesk
_This project is NOT officially affiliated with BookMyDesk in any way!_

## Setup
Create your Slack app/bot: 
- Go to: https://api.slack.com/apps
- _"Create an app"_ -> _"From scratch"_
- App name, for example: _"BotMyDesk"_

After creation, go to _"Socket Mode"_ first! 

Enable it and create an App-level token, which you'll need later anyway.
The default ``connections:write`` scope will suffice.

Set the generated in App-level token as ``SLACK_APP_TOKEN`` env var (or in ``.env``) later.


- Now go to _"App Home"_, scroll down the page and ensure to activate (direct) messaging for your **App** by clicking the checkbox for:
```
Allow users to send Slash commands and messages from the messages tab
```

- Go to _"Slash Commands"_, create a new command and make sure it has the following "slash command(s)":

| Slash command | Description                               | Parameters                           |
|:--------------|-------------------------------------------|:-------------------------------------|
| `/bmd`        | Access BotMyDesk commands and preferences | help                                 |

_Note: You can choose any command name you'd like and override it as ``SLACK_SLASHCOMMAND_BMD`` env var._


- We're almost done. Go to _"OAuth & Permissions"_, scroll down to _"Scopes"_ and set these **Bot Token Scopes**:
```
commands
chat:write
im:read
im:write
users:read
users:read.email
```

Finally, scroll up at _"OAuth & Permissions"_ and click the **Install to Workspace** button.
This will prompt you to install it for your workspace and redirect back to _"OAuth & Permissions"_. 

You should now see a _"Bot User OAuth Token"_ there. Save it and set it (later) as ``SLACK_BOT_TOKEN`` env var (or in your ``.env`` below).


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
- Did you change strings? Generate PO file using all translation tags/strings in codebase.:
```shell
./manage.py makemessages --no-wrap --no-location --locale nl 
```
- The source translation (PO) file, e.g. [src/locales/nl/LC_MESSAGES/django.po](src/locales/nl/LC_MESSAGES/django.po), should be updated.
- Translate any additions or changes with `Poedit` (or whatever program you'd like to use).


### Production/deploy

```@TODO: Finish when deploying to prod server.```
```shell
cp docker-compose.override.yml.PROD.TEMPLATE docker-compose.override.yml

# Either load your .env on your server or use real env vars. Either way see the env template for what you need.
cp .env.TEMPLATE .env
```

Make sure to run database migrations before running:
```shell
./manage.py migrate
```
