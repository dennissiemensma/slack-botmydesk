class BookMyDeskProfile:
    email: str
    first_name: str
    infix: str
    last_name: str
    company_id: str

    def __init__(self, profile_v3_result: dict):
        self.email = profile_v3_result["result"]["email"]
        self.first_name = profile_v3_result["result"]["firstName"]
        self.infix = profile_v3_result["result"]["infix"]
        self.last_name = profile_v3_result["result"]["lastName"]
        self.company_id = profile_v3_result["result"]["companies"][0]["id"]
