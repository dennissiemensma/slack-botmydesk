from typing import List


class V3BookMyDeskProfileResult:
    email: str
    first_name: str
    infix: str
    last_name: str
    company_id: str

    def __init__(self, profile_v3_result: dict):
        self.email = profile_v3_result["email"]
        self.first_name = profile_v3_result["firstName"]
        self.infix = profile_v3_result["infix"]
        self.last_name = profile_v3_result["lastName"]
        self.company_id = profile_v3_result["companies"][0]["id"]


class JsonResponseHolder:
    _response: dict

    def __init__(self, response: dict):
        self._response = response


class LocationMapSeat(JsonResponseHolder):
    def id(self) -> str:
        return self._response['id']

    def name(self) -> str:
        return self._response['name']


class LocationMap(JsonResponseHolder):
    def id(self) -> str:
        return self._response['id']

    def name(self) -> str:
        return self._response['name']

    def seats(self) -> List[LocationMapSeat]:
        return [
            LocationMapSeat(x) for x in self._response['seats']
        ]


class Location(JsonResponseHolder):
    def id(self) -> str:
        return self._response['id']

    def name(self) -> str:
        return self._response['name']

    def maps(self) -> List[LocationMap]:
        return [
            LocationMap(x) for x in self._response['maps']
        ]


class V3CompanyExtendedResult(JsonResponseHolder):
    def locations(self) -> List[Location]:
        return [
            Location(x) for x in self._response['locations']
        ]

