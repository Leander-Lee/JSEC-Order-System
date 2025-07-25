from django.test import TestCase

from allauth.socialaccount.providers.hubic.provider import HubicProvider
from tests.apps.socialaccount.base import OAuth2TestsMixin
from tests.mocking import MockedResponse


class HubicTests(OAuth2TestsMixin, TestCase):
    provider_id = HubicProvider.id

    def get_mocked_response(self):
        return MockedResponse(
            200,
            """
{
    "email": "user@example.com",
    "firstname": "Test",
    "activated": true,
    "creationDate": "2014-04-17T17:04:01+02:00",
    "language": "en",
    "status": "ok",
    "offer": "25g",
    "lastname": "User"
}
""",
        )

    def get_expected_to_str(self):
        return "user@example.com"

    def get_login_response_json(self, with_refresh_token=True):
        return '{\
    "access_token": "testac",\
    "expires_in": "3600",\
    "refresh_token": "testrf",\
    "token_type": "Bearer"\
}'
