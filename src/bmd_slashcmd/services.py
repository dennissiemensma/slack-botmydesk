from typing import Optional

from django.conf import settings

from bmd_slashcmd.dto import UserInfo


def on_slash_command(user_info: UserInfo, payload: dict) -> dict:
    """Pass me your slash command payload to map."""
    command = payload["command"]
    print(
        f"Incoming slash command '{command}' for {user_info.name} ({user_info.slack_user_id})"
    )

    try:
        service_module = {
            settings.SLACK_SLASHCOMMAND_BMD: handle_slash_command_bmd,
        }[command]
    except KeyError:
        raise NotImplementedError(command)

    return service_module(user_info, **payload)


def handle_slash_command_bmd(user_info: UserInfo, **payload) -> dict:
    """Called on generic bmd."""
    print(f"User triggered slash command: {user_info.slack_user_id}")

    # TODO: Check bot auth state for dynamic stuff
    return {
        "type": "modal",
        "callback_id": "bmd-modal",
        "title": {"type": "plain_text", "text": f"Greetings {user_info.name}!"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "You will need to authorize me to access your BMD account (currently only your Slack email address supported).",
                },
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Step 1/2 to authorize me",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Log in using `{user_info.email}` and await the *login code* being sent by email.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {
                            "type": "plain_text",
                            "text": "Open BMD",
                            "emoji": True,
                        },
                        "value": "open_bmd_login",
                        "url": settings.BOOKMYDESK_LOGIN_URL,
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Enter the *login code* in the next dialog._",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_ℹ️ You can revoke my access later by running `{settings.SLACK_SLASHCOMMAND_BMD}` again._",
                },
            },
            # {
            #     "type": "section",
            #     "text": {
            #         "type": "mrkdwn",
            #         "text": f"Enter you email address ({user_info.email}) over there and have BMD send you a one-time login code \n • Enter to code below to authorize me"
            #     }
            # },
            # {
            #     "type": "input",
            #     "element": {
            #         "type": "plain_text_input",
            #         "action_id": "bmd_otp_code-action"
            #     },
            #     "label": {
            #         "type": "plain_text",
            #         "text": f"BMD OTP code for {user_info.email}",
            #         "emoji": True
            #     }
            # },
            # {
            #     "type": "actions",
            #     "elements": [
            #         {
            #             "type": "button",
            #             "text": {
            #                 "type": "plain_text",
            #                 "text": "Authorize",
            #                 "emoji": True
            #             },
            #             "value": "authorize",
            #         }
            #     ]
            # },
        ],
    }


# def bmd_token_login():
# username = None
#
# import requests
# password = text.strip()
#
# if len(password) != 6:
#     raise AssertionError('Unexpected OTP format')
#
# text = text.strip()
# username, password = text.split(" ", maxsplit=1)
# response = requests.post(
#     url="{}/token".format(settings.BOOKMYDESK_API_URL),
#     data={
#         "grant_type": "password",
#         "client_id": settings.BOOKMYDESK_CLIENT_ID,
#         "client_secret": settings.BOOKMYDESK_CLIENT_SECRET,
#         "username": username,
#         "password": password,
#         "scopes": "",
#     },
#     headers={
#         'Content-Type': "application/x-www-form-urlencoded",
#         'User-Agent': settings.BMD_USER_AGENT,
#     }
# )

# if response.status_code != 200:
#     raise PermissionError()


def on_interactive_action(user_info: UserInfo, action: dict) -> Optional[dict]:
    """Respond to user (inter)actions."""
    action_value = action["value"]
    print(
        f"Incoming interactive '{action_value}' for {user_info.name} ({user_info.slack_user_id})"
    )

    try:
        service_module = {
            "open_bmd_login": handle_interactive_open_bmd_login,
        }[action_value]
    except KeyError:
        raise NotImplementedError(action_value)

    return service_module(user_info, **action)


def handle_interactive_open_bmd_login(user_info: UserInfo, **payload):
    print(f"User clicked BMD login: {user_info.slack_user_id}")
