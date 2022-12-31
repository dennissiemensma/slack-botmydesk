# Slack: BotMyDesk
_This project is NOT officially affiliated with BookMyDesk in any way!_

## Development activity
This project has been **discontinued** in favor of a series of events. 

## Notes
- When using the default container setup: Python locales may not work well when switching to a non-English locale.

## Setup
### Creating your Slack app
- Go to: https://api.slack.com/apps
- Click _"Create an app"_ > _"From scratch"_, enter an app name, for example: _"BotMyDesk"_

After creation of your app:

- Open the menu item **Features > OAuth & Permissions**.
- Scroll down to _"Scopes"_ and add these _"Bot Token Scopes"_ (one at a time):
```shell
commands
chat:write
im:read
im:write
im:history
users:read
users:read.email
users:write
```

- Now go to **Features > App Home**, scroll down the page to _"Show Tabs"_ and **enable** the **Home Tab** option.
- Also, (a bit below that) ensure to activate direct messaging for your **App** by checking the checkbox for:

> "Allow users to send Slash commands and messages from the messages tab"

- Continue to **Features > Slash Commands**, create a new slash command and save it:

```shell
Slash command:          /bmd
Request URL:            https://example.com
Short Description:      Trigger BotMyDesk
Usage Hint:             <empty>
```
*Note: You can choose any command name you'd like and override it as ``SLACK_SLASHCOMMAND_BMD`` env var. Also, you can omit the "Request URL" until you go production.*

*Note 2: The request URL does not matter until you actually host the bot somewhere.* 

- Open **Features > Basic Information** and click the **Install to workspace** button. You will now authorize your bot for the workspace you'd like to use it in.

You're done, for now. The remaining configuration depends on whether you want to run this bot locally for development or host it for production usage. Continue below with either route.


----


*Choose either **local development** or **production hosting**, as the configuration in Slack is quite different between these.*

## Local development installation
- **Optional:** If you want your IDE to detect packages code, install ``poetry`` on your host, e.g.:
```shell
# Debian
apt-get install python3-pip
pip install poetry

cd src/
poetry config virtualenvs.in-project true

# You may or may not require some additional dev packages on your host. Good luck Googling.
poetry install
```

- In either case, continue with:
```shell
cp docker-compose.override.yml.DEV.TEMPLATE docker-compose.override.yml
cp .env.TEMPLATE .env
```

- Set your env vars in ``.env`` or ``docker-compose.override.yml``.

For running your bot locally you should use **Socket Mode** in Slack.
- Go to: https://api.slack.com/apps
- Find your bot and go to **Features > Socket Mode**
- Click **Enable Socket Mode**, type a hint for your token in the popup (e.g. "local dev") and click _"Generate"_. 
- This will generate an **App-level token**, set it in your ``.env`` file:

```shell
# Slack -> Your Bot -> Basic Information -> App-Level Tokens
SLACK_APP_TOKEN=
```

- Also go to *Features > OAuth & Permissions** and set both **Bot User OAuth Token** / **Signing Secret** in your ``.env``:  

```shell
# Slack > Your Bot > Features > OAuth & Permissions > Bot User OAuth Token
SLACK_BOT_TOKEN=

# Slack > Your Bot > Basic Information > App Credentials > Signing Secret
SLACK_BOT_SIGNING_SECRET=
```

- After enabling Socket Mode, go to **Features > Event Subscriptions** and toggle **Enable Events** to have it enabled.
- Finally, on the same page, click **Subscribe to bot events** and add this event:

```shell
app_home_opened
```

- Click _"Save Changes"_.

The configuration should be done now! You can try building and running the container/bot now.


- Run this to bootstrap the app/bot:

```shell
docker-compose up -d
```

----

## Developing
### Translations
- Currently supported: `en`, `nl`
- Did you change strings? Regenerate PO file using all translation tags/strings marked in the codebase:
```shell
docker exec -it botmydesk_dev_app poetry run /code/manage.py makemessages --no-wrap --no-location --locale nl
```
- The source translation (PO) file, e.g. [src/locales/nl/LC_MESSAGES/django.po](src/locales/nl/LC_MESSAGES/django.po), should be updated.
- Translate any additions or changes with `Poedit` (or whatever program you'd like to use).

### Helpers
Also:
- Run the `dev_app` with env `DEV_EMAIL_ADDRESS=your@mail.address` to force that mail address being used for login. *E.g. when your Slack dev account has no BookMyDesk account.*
- Run the `dev_app` with env `DEV_BOOKMYDESK_ACCESS_TOKEN_EXPIRY_MINUTES=0` to force a BookMyDesk refresh token call every time.


----


## Production hosting installation

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
# Slack > Your Bot > Features > OAuth & Permissions > Bot User OAuth Token
SLACK_BOT_TOKEN=
# Slack > Your Bot > Settings > Basic Information > App Credentials > Signing Secret
SLACK_BOT_SIGNING_SECRET=
```

- Build images:
```shell
docker-compose build
```

- Run:
```shell
docker-compose up -d
```

- Note that the prod app container _should_ perform some administrative tasks, such as DB migrations.

----

Your bot should now be ready to receive requests. 
However, note that this guide does NOT include how to run Nginx with Certbot for HTTPS. 
You WILL need it for receiving Slack callbacks. 

An easy workaround is to install another Nginx instance with Certbot on your host.
See the default Nginx docker-compose port config (of this project):
```shell
    ports:
     - "8080:80"
```

Restart the container and configure the Nginx vhost **on your host** (which receives HTTPS traffic) to pass all requests upstream to the new port 8080.
```shell
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
```

----

When ready, go back to Slack, open your Bot settings for the following configuration.

#### Interactivity & Shortcuts 

- Toggle "Off" to "On"
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
- It should validate if you configured and hosted this bot correctly.
- Finally, on the same page, click **Subscribe to bot events** and add this event:

```shell
app_home_opened
```

- Click _"Save Changes"_.
- Save changes *(bottom)*

----

- It is supported but **NOT ADVISED** run multiple instances of either the web app or the background worker. They are currently **prone to race conditions**!
```shell
docker-compose up -d --scale app=5
```

- The following processes should run:
```shell
# Task scheduler (DO NOT RUN MULTIPLE!)
poetry run celery -A botmydesk beat
# Task worker
poetry run celery -A botmydesk worker
```

- Live logs:
```shell
docker-compose logs -f
```
