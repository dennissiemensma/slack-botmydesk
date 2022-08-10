class UserInfo:
    slack_user_id: str
    name: str
    email: str

    def __init__(self, slack_user_id: str, name: str, email: str):
        self.slack_user_id = slack_user_id
        self.name = name
        self.email = email

    def slack_id(self) -> str:
        return self.slack_user_id

    def name(self) -> str:
        return self.name

    def email(self) -> str:
        return self.email
