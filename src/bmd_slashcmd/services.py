from decouple import config


def on_slash_command(payload: dict):
    """ Pass me your slash command payload to map. """
    try:
        service_module = {
            config('CMD_SLASHCOMMAND_AUTHORIZE', cast=str): slash_commands_authorize,
            config('CMD_SLASHCOMMAND_REVOKE', cast=str): slash_commands_revoke,
        }[payload['command']]
    except KeyError:
        raise NotImplementedError(payload['command'])

    service_module(**payload)


def slash_commands_authorize(user_id: str, text: str, **kwargs):
    print('AUTHORIZE', user_id, text)


def slash_commands_revoke(user_id: str, **kwargs):
    print('REVOKE', user_id, )
