from typing import List
from abc import ABC


class JsonResponseHolder(ABC):
    _response: dict

    def __init__(self, response: dict):
        self._response = response


class TokenLoginResult(JsonResponseHolder):
    def access_token(self) -> str:
        return self._response['access_token']

    def refresh_token(self) -> str:
        return self._response['refresh_token']


class V3BookMyDeskProfileResult(JsonResponseHolder):
    # def email(self) -> str:
    #     return self._response['email']

    def first_name(self) -> str:
        return self._response['firstName']

    def infix(self) -> str:
        return self._response['infix']

    def last_name(self) -> str:
        return self._response['lastName']

    def first_company_id(self) -> str:
        """ The first one found. """
        return self._response["companies"][0]["id"]


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

