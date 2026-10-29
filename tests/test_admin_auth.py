from argon2 import PasswordHasher

from rag_app.admin_auth import AdminAuth


def test_admin_auth_issues_and_verifies_signed_session() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="session-secret",
    )

    token = auth.authenticate("correct")

    assert token is not None
    assert auth.verify(token) is True
    assert auth.verify(f"{token}x") is False


def test_admin_auth_rejects_wrong_password() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="session-secret",
    )

    assert auth.authenticate("wrong") is None
