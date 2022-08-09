from django.conf import settings
import requests

def on_slash_command(payload: dict):
    """Pass me your slash command payload to map."""
    command = payload["command"]

    try:
        service_module = {
            settings.SLACK_SLASHCOMMAND_AUTHORIZE: slash_commands_authorize,
            settings.SLACK_SLASHCOMMAND_REVOKE: slash_commands_revoke,
        }[command]
    except KeyError:
        raise NotImplementedError(command)

    service_module(**payload)


def slash_commands_authorize(user_id: str, text: str, **kwargs):
    print("Authorize {}: OTP '{}'".format(user_id, text))

    # TODO Read user email address.
    username = None

    password = text.strip()

    if len(password) != 6:
        raise AssertionError('Unexpected OTP format')

    # text = text.strip()
    username, password = text.split(' ', maxsplit=1)
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


def slash_commands_revoke(user_id: str, **kwargs):
    print("Revoke {}: {}".format(user_id, user_id))
