"""Harness check for A3-style tests: two users, two independent browsers (cookie jars)."""

import pytest

pytestmark = pytest.mark.integration


def test_two_users_each_see_only_themselves(make_client, login_as):
    alice_browser, bob_browser = make_client(), make_client()
    alice = login_as(alice_browser, "alice")
    bob = login_as(bob_browser, "bob")

    assert alice.id != bob.id
    assert alice_browser.get("/api/me").json()["id"] == str(alice.id)
    assert bob_browser.get("/api/me").json()["id"] == str(bob.id)
    assert bob_browser.get("/api/me").json()["email"] == "bob@example.com"


def test_two_users_logout_is_per_session(make_client, login_as, csrf_headers):
    alice_browser, bob_browser = make_client(), make_client()
    login_as(alice_browser, "alice")
    login_as(bob_browser, "bob")

    assert alice_browser.post("/auth/logout", headers=csrf_headers).status_code == 204

    assert alice_browser.get("/api/me").status_code == 401
    assert bob_browser.get("/api/me").status_code == 200


def test_two_users_identity_comes_only_from_the_cookie(make_client, login_as, settings):
    alice_browser, bob_browser = make_client(), make_client()
    alice = login_as(alice_browser, "alice")
    login_as(bob_browser, "bob")

    # A stolen cookie is the only way to become Alice: whoever presents it is Alice.
    bob_browser.cookies.set(
        settings.session_cookie_name, alice_browser.cookies.get(settings.session_cookie_name)
    )
    assert bob_browser.get("/api/me").json()["id"] == str(alice.id)
