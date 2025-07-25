from http import HTTPStatus
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from allauth.account.models import EmailAddress


@pytest.fixture(autouse=True)
def email_verification_settings(settings):
    settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
    settings.ACCOUNT_EMAIL_VERIFICATION = "mandatory"
    settings.ACCOUNT_AUTHENTICATION_METHOD = "email"
    return settings


@pytest.mark.parametrize(
    "query,expected_url",
    [
        ("", settings.LOGIN_REDIRECT_URL),
        ("?next=/foo", "/foo"),
    ],
)
def test_signup(
    client,
    db,
    settings,
    password_factory,
    get_last_email_verification_code,
    query,
    expected_url,
    mailoutbox,
):
    password = password_factory()
    resp = client.post(
        reverse("account_signup") + query,
        {
            "username": "johndoe",
            "email": "john@example.com",
            "password1": password,
            "password2": password,
        },
    )
    assert get_user_model().objects.filter(username="johndoe").count() == 1
    code = get_last_email_verification_code(client, mailoutbox)
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    resp = client.get(reverse("account_email_verification_sent"))
    assert resp.status_code == HTTPStatus.OK
    resp = client.post(reverse("account_email_verification_sent"), data={"code": code})
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == expected_url


def test_signup_prevent_enumeration(
    client, db, settings, password_factory, user, mailoutbox
):
    password = password_factory()
    resp = client.post(
        reverse("account_signup"),
        {
            "username": "johndoe",
            "email": user.email,
            "password1": password,
            "password2": password,
        },
    )
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    assert not get_user_model().objects.filter(username="johndoe").exists()
    assert mailoutbox[0].subject == "[example.com] Account Already Exists"
    resp = client.get(reverse("account_email_verification_sent"))
    assert resp.status_code == HTTPStatus.OK
    resp = client.post(reverse("account_email_verification_sent"), data={"code": ""})
    assert resp.status_code == HTTPStatus.OK
    assert resp.context["form"].errors == {"code": ["This field is required."]}
    resp = client.post(reverse("account_email_verification_sent"), data={"code": "123"})
    assert resp.status_code == HTTPStatus.OK
    assert resp.context["form"].errors == {"code": ["Incorrect code."]}
    # Max attempts
    resp = client.post(reverse("account_email_verification_sent"), data={"code": "456"})
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_login")


@pytest.mark.parametrize("change_email", (False, True))
def test_add_or_change_email(
    auth_client,
    user,
    get_last_email_verification_code,
    change_email,
    settings,
    mailoutbox,
):
    settings.ACCOUNT_CHANGE_EMAIL = change_email
    settings.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True
    email = "additional@email.org"
    assert EmailAddress.objects.filter(user=user).count() == 1
    with patch("allauth.account.signals.email_added") as email_added_signal:
        with patch("allauth.account.signals.email_changed") as email_changed_signal:
            resp = auth_client.post(
                reverse("account_email"), {"action_add": "", "email": email}
            )
            assert resp["location"] == reverse("account_email_verification_sent")
            assert not email_added_signal.send.called
            assert not email_changed_signal.send.called
    assert EmailAddress.objects.filter(email=email).count() == 0
    code = get_last_email_verification_code(auth_client, mailoutbox)
    resp = auth_client.get(reverse("account_email_verification_sent"))
    assert resp.status_code == HTTPStatus.OK
    resp = auth_client.post(
        reverse("account_email_verification_sent"), {"action": "resend"}
    )
    assert EmailAddress.objects.filter(email=email).count() == 0
    assert resp.status_code == HTTPStatus.FOUND
    code2 = get_last_email_verification_code(auth_client, mailoutbox)
    assert code != code2
    with patch("allauth.account.signals.email_added") as email_added_signal:
        with patch("allauth.account.signals.email_changed") as email_changed_signal:
            with patch(
                "allauth.account.signals.email_confirmed"
            ) as email_confirmed_signal:
                resp = auth_client.post(
                    reverse("account_email_verification_sent"), data={"code": code2}
                )
                assert resp.status_code == HTTPStatus.FOUND
                assert resp["location"] == settings.LOGIN_REDIRECT_URL
                assert email_added_signal.send.called
                assert email_confirmed_signal.send.called
                assert email_changed_signal.send.called == change_email
    assert EmailAddress.objects.filter(email=email, verified=True).count() == 1
    assert EmailAddress.objects.filter(user=user).count() == (1 if change_email else 2)


def test_email_verification_login_redirect(
    client, db, settings, password_factory, email_verification_settings
):
    password = password_factory()
    resp = client.post(
        reverse("account_signup"),
        {
            "username": "johndoe",
            "email": "user@email.org",
            "password1": password,
            "password2": password,
        },
    )
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    resp = client.get(reverse("account_login"))
    assert resp["location"] == reverse("account_email_verification_sent")


def test_email_verification_rate_limits(
    db,
    user_password,
    email_verification_settings,
    settings,
    user_factory,
    password_factory,
    enable_cache,
):
    settings.ACCOUNT_RATE_LIMITS = {"confirm_email": "1/m/key"}
    email = "user@email.org"
    user_factory(email=email, email_verified=False, password=user_password)
    for attempt in range(2):
        resp = Client().post(
            reverse("account_login"),
            {
                "login": email,
                "password": user_password,
            },
        )
        if attempt == 0:
            assert resp.status_code == HTTPStatus.FOUND
            assert resp["location"] == reverse("account_email_verification_sent")
        else:
            assert resp.status_code == HTTPStatus.OK
            assert resp.context["form"].errors == {
                "__all__": ["Too many failed login attempts. Try again later."]
            }


def test_change_email_vs_enumeration_prevention(
    client,
    db,
    settings,
    password_factory,
    get_last_email_verification_code,
    mailoutbox,
    messagesoutbox,
    user,
):
    settings.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True
    password = password_factory()
    resp = client.post(
        reverse("account_signup"),
        {
            "username": "johndoe",
            "email": user.email,
            "password1": password,
            "password2": password,
        },
    )
    # No user signed up.
    assert get_user_model().objects.filter(username="johndoe").count() == 0
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "[example.com] Account Already Exists"
    assert len(messagesoutbox) == 1
    assert (
        messagesoutbox[-1]["message_template"]
        == "account/messages/email_confirmation_sent.txt"
    )

    # Resend
    resp = client.post(reverse("account_email_verification_sent"), {"action": "resend"})
    assert len(mailoutbox) == 1
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    # No new emails sent.
    assert len(mailoutbox) == 1
    # Yet, pretend we did.
    assert len(messagesoutbox) == 2
    assert (
        messagesoutbox[-1]["message_template"]
        == "account/messages/email_confirmation_sent.txt"
    )


def test_change_to_already_existing_email(
    client,
    db,
    settings,
    password_factory,
    get_last_email_verification_code,
    mailoutbox,
    messagesoutbox,
    user,
):
    settings.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True
    settings.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE = True
    password = password_factory()
    resp = client.post(
        reverse("account_signup"),
        {
            "username": "johndoe",
            "email": "new@user.org",
            "password1": password,
            "password2": password,
        },
    )
    # A user signed up.
    new_user = get_user_model().objects.get(username="johndoe")
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "[example.com] Please Confirm Your Email Address"
    assert len(messagesoutbox) == 1
    assert (
        messagesoutbox[-1]["message_template"]
        == "account/messages/email_confirmation_sent.txt"
    )

    # Change to a conflicting email
    resp = client.post(
        reverse("account_email_verification_sent"),
        {"action": "change", "email": user.email},
    )
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    assert len(mailoutbox) == 2
    assert mailoutbox[1].subject == "[example.com] Account Already Exists"
    assert len(messagesoutbox) == 2
    assert (
        messagesoutbox[-1]["message_template"]
        == "account/messages/email_confirmation_sent.txt"
    )
    new_user.refresh_from_db()
    assert new_user.email == "new@user.org"

    # Change back to new email
    resp = client.post(
        reverse("account_email_verification_sent"),
        {"action": "change", "email": "new2@user.org"},
    )
    assert len(mailoutbox) == 3
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"] == reverse("account_email_verification_sent")
    assert mailoutbox[2].subject == "[example.com] Please Confirm Your Email Address"
    assert len(messagesoutbox) == 3
    assert (
        messagesoutbox[-1]["message_template"]
        == "account/messages/email_confirmation_sent.txt"
    )
    new_user.refresh_from_db()
    assert new_user.email == "new2@user.org"

    code = get_last_email_verification_code(client, mailoutbox)
    resp = client.post(reverse("account_email_verification_sent"), data={"code": code})
    assert resp.status_code == HTTPStatus.FOUND
    email_address = EmailAddress.objects.filter(user=new_user).get()
    assert email_address.verified
    assert email_address.email == "new2@user.org"


def test_verified_email_decorator__unverified(
    auth_client, mailoutbox, get_last_email_verification_code
):
    EmailAddress.objects.all().update(verified=False)
    resp = auth_client.get(reverse("tests_account_check_verified_email"))
    assert resp.status_code == HTTPStatus.FOUND
    assert resp["location"].startswith(reverse("account_email_verification_sent"))
    code = get_last_email_verification_code(auth_client, mailoutbox)
    resp = auth_client.post(
        reverse("account_email_verification_sent"),
        data={"code": code, "next": reverse("tests_account_check_verified_email")},
        follow=True,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.content == b"VERIFIED"
