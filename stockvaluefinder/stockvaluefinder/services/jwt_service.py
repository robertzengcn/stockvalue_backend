"""JWT token service for authentication.

Handles JWT token generation, validation, and bcrypt password hashing.
Uses PyJWT for token operations and bcrypt for password hashing.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from stockvaluefinder.config import auth_config

logger = logging.getLogger(__name__)


class JWTService:
    """Service for JWT token management and password hashing.

    Provides methods for creating and validating access/refresh tokens,
    and hashing/verifying passwords with bcrypt.
    """

    def __init__(
        self,
        secret: str = auth_config.JWT_SECRET,
        algorithm: str = auth_config.JWT_ALGORITHM,
        access_token_expire_minutes: int = auth_config.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = auth_config.REFRESH_TOKEN_EXPIRE_DAYS,
        bcrypt_rounds: int = auth_config.BCRYPT_ROUNDS,
    ) -> None:
        """Initialize JWT service with configuration.

        Args:
            secret: Secret key for signing JWT tokens.
            algorithm: Algorithm for JWT signing (default HS256).
            access_token_expire_minutes: Access token lifetime in minutes.
            refresh_token_expire_days: Refresh token lifetime in days.
            bcrypt_rounds: Number of bcrypt hashing rounds.
        """
        self._secret = secret
        self._algorithm = algorithm
        self._access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_token_expire = timedelta(days=refresh_token_expire_days)
        self._bcrypt_rounds = bcrypt_rounds

    def create_access_token(self, user_id: str, role: str) -> str:
        """Create a JWT access token.

        Args:
            user_id: User's unique identifier (UUID string).
            role: User's role (admin or user).

        Returns:
            Encoded JWT access token string.
        """
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + self._access_token_expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str, role: str) -> str:
        """Create a JWT refresh token.

        Args:
            user_id: User's unique identifier (UUID string).
            role: User's role at time of token creation (for audit only; refresh endpoint re-fetches from DB).

        Returns:
            Encoded JWT refresh token string.
        """
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "type": "refresh",
            "role": role,
            "iat": now,
            "exp": now + self._refresh_token_expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: Encoded JWT token string.

        Returns:
            Decoded token payload dictionary.

        Raises:
            jwt.ExpiredSignatureError: If token has expired.
            jwt.InvalidTokenError: If token is invalid.
        """
        return jwt.decode(
            token,
            self._secret,
            algorithms=[self._algorithm],
        )

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """Validate an access token and return its payload.

        Args:
            token: Encoded JWT access token string.

        Returns:
            Decoded token payload if valid.

        Raises:
            jwt.InvalidTokenError: If token is invalid or not an access token.
        """
        payload = self.decode_token(token)
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Expected access token, got refresh token")
        return payload

    def validate_refresh_token(self, token: str) -> dict[str, Any]:
        """Validate a refresh token and return its payload.

        Args:
            token: Encoded JWT refresh token string.

        Returns:
            Decoded token payload if valid.

        Raises:
            jwt.InvalidTokenError: If token is invalid or not a refresh token.
        """
        payload = self.decode_token(token)
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("Expected refresh token, got access token")
        return payload

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plaintext password string.

        Returns:
            Bcrypt hashed password string.
        """
        salt = bcrypt.gensalt(rounds=auth_config.BCRYPT_ROUNDS)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a bcrypt hash.

        Args:
            plain_password: Plaintext password to verify.
            hashed_password: Stored bcrypt hash to verify against.

        Returns:
            True if password matches, False otherwise.
        """
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )


# Module-level singleton
jwt_service = JWTService()
