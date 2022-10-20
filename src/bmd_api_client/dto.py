from typing import List, Optional

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext


class JsonResponseHolder:
    _response: dict

    def __init__(self, response: dict):
        self._response = response


class LocationMapSeat(JsonResponseHolder):
    def id(self) -> str:
        return self._response["id"]

    def name(self) -> str:
        return self._response["name"]


class LocationMap(JsonResponseHolder):
    def id(self) -> str:
        return self._response["id"]

    def name(self) -> str:
        return self._response["name"]

    def seats(self) -> List[LocationMapSeat]:
        return [LocationMapSeat(x) for x in self._response["seats"]]


class Location(JsonResponseHolder):
    def id(self) -> str:
        return self._response["id"]

    def name(self) -> str:
        return self._response["name"]

    def maps(self) -> List[LocationMap]:
        return [LocationMap(x) for x in self._response["maps"]]


class Seat(JsonResponseHolder):
    def id(self) -> str:
        return self._response["id"]

    def map_name(self) -> str:
        return self._response["map"]["name"]


class Reservation(JsonResponseHolder):
    def id(self) -> str:
        return self._response["id"]

    def is_created_by_same_user(self) -> bool:
        return self._response["user"]["id"] == self._response["createdByUserId"]

    def date_start(self) -> timezone.datetime:
        return timezone.datetime.fromisoformat(self._response["dateStart"])

    def date_end(self) -> timezone.datetime:
        return timezone.datetime.fromisoformat(self._response["dateEnd"])

    def status(self) -> str:
        """reserved | checkedIn | checkedOut | cancelled | expired | cancelled | expired"""
        return self._response["status"]

    def checked_in_time(self) -> Optional[str]:
        try:
            return self._response["checkedInTime"]
        except KeyError:
            return None

    def checked_out_time(self) -> Optional[str]:
        try:
            return self._response["checkedOutTime"]
        except KeyError:
            return None

    def from_time(self) -> str:
        return self._response["from"]

    def to_time(self) -> str:
        return self._response["to"]

    def type(self) -> str:
        """normal | visitor | home"""
        return self._response["type"]

    def seat(self) -> Optional[Seat]:
        try:
            return Seat(self._response["seat"])
        except KeyError:
            return None

    def location_name_shortcut(self) -> str:
        if (
            self.seat() is not None
            and self.seat().map_name()
            == settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME
        ):
            return self.seat().map_name()
        elif self.seat() is not None and self.type() == "normal":
            return self.seat().map_name()
        elif self.seat() is None and self.type() == "home":
            return gettext("Home")
        else:
            return "❓"

    def emoji_shortcut(self) -> str:
        if (
            self.seat() is not None
            and self.seat().map_name()
            == settings.BOTMYDESK_WORK_EXTERNALLY_LOCATION_NAME
        ):
            return "🚋"
        elif self.seat() is not None and self.type() == "normal":
            return "🏢"
        elif self.seat() is None and self.type() == "home":
            return "🏡"
        else:
            return "❓"


class TokenLoginResult(JsonResponseHolder):
    def access_token(self) -> str:
        return self._response["access_token"]

    def refresh_token(self) -> str:
        return self._response["refresh_token"]


class V3BookMyDeskProfileResult(JsonResponseHolder):
    # def email(self) -> str:
    #     return self._response['email']
    def id(self) -> str:
        return self._response["id"]

    def first_name(self) -> str:
        return self._response["firstName"]

    def infix(self) -> str:
        return self._response["infix"]

    def last_name(self) -> str:
        return self._response["lastName"]

    def first_company_id(self) -> str:
        """The first one found."""
        return self._response["companies"][0]["id"]


class V3CompanyExtendedResult(JsonResponseHolder):
    def locations(self) -> List[Location]:
        return [Location(x) for x in self._response["locations"]]


class V3ReservationsResult(JsonResponseHolder):
    def reservations(self) -> List[Reservation]:
        return [Reservation(x) for x in self._response["items"]]
