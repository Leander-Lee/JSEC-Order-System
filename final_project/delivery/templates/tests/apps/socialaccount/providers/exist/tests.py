from django.test import TestCase

from allauth.socialaccount.providers.exist.provider import ExistProvider
from tests.apps.socialaccount.base import OAuth2TestsMixin
from tests.mocking import MockedResponse


class ExistTests(OAuth2TestsMixin, TestCase):
    provider_id = ExistProvider.id

    def get_mocked_response(self):
        return MockedResponse(
            200,
            """
            {
                "id": 1,
                "username": "josh",
                "first_name": "Josh",
                "last_name": "Sharp",
                "bio": "I made this thing you're using.",
                "url": "http://hellocode.co/",
                "avatar": "https://exist.io/static/media/avatars/josh_2.png",
                "timezone": "Australia/Melbourne",
                "local_time": "2020-07-31T22:33:49.359+10:00",
                "private": false,
                "imperial_units": false,
                "imperial_distance": false,
                "imperial_weight": false,
                "imperial_energy": false,
                "imperial_liquid": false,
                "imperial_temperature": false,
                "attributes": []
            }
        """,
        )

    def get_expected_to_str(self):
        return "josh"
