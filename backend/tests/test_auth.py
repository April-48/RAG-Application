"""Auth route tests — signup, login, /me, invalid credentials."""

from __future__ import annotations

from tests.conftest import auth_header, login_token, signup_user


def test_signup_creates_user(client) -> None:
    user = signup_user(client, "alice@example.com")
    assert user["email"] == "alice@example.com"
    assert "id" in user


def test_login_returns_access_token(client) -> None:
    signup_user(client, "bob@example.com")
    response = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_me_returns_current_user(client) -> None:
    user = signup_user(client, "carol@example.com")
    token = login_token(client, "carol@example.com")
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    me = response.json()
    assert me["email"] == "carol@example.com"
    assert me["id"] == user["id"]


def test_invalid_login_fails(client) -> None:
    signup_user(client, "dave@example.com")
    response = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
