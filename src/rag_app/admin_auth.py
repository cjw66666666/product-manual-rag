from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class AdminAuth:
    def __init__(
        self,
        *,
        password_hash: str,
        session_secret: str,
        max_age_seconds: int = 3600,
    ) -> None:
        self._password_hash = password_hash
        self._serializer = URLSafeTimedSerializer(session_secret)
        self._max_age_seconds = max_age_seconds
        self._hasher = PasswordHasher()

    def authenticate(self, password: str) -> str | None:
        try:
            self._hasher.verify(self._password_hash, password)
        except VerificationError:
            return None
        return self._serializer.dumps({"role": "admin"})

    def verify(self, token: str) -> bool:
        if not token:
            return False
        try:
            payload = self._serializer.loads(
                token,
                max_age=self._max_age_seconds,
            )
        except (BadSignature, SignatureExpired):
            return False
        return isinstance(payload, dict) and payload.get("role") == "admin"
