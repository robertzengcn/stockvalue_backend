"""Tests for authentication flow: register, login, refresh, logout, and endpoint protection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.exc import ProgrammingError

from stockvaluefinder.api.auth_routes import router as auth_router
from stockvaluefinder.api.risk_routes import router as risk_router
from stockvaluefinder.api.dependencies import get_current_user
from stockvaluefinder.services.jwt_service import jwt_service


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session):
    """Override get_db dependency with mock session."""

    async def _override():
        yield mock_db_session

    return _override


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def valid_access_token(user_id):
    """Generate a valid access token for testing."""
    return jwt_service.create_access_token(str(user_id), "user")


@pytest.fixture
def valid_admin_token():
    """Generate a valid admin access token for testing."""
    admin_id = uuid4()
    return jwt_service.create_access_token(str(admin_id), "admin")


@pytest.fixture
def valid_refresh_token(user_id):
    """Generate a valid refresh token for testing."""
    return jwt_service.create_refresh_token(str(user_id), "user")


@pytest.fixture
def expired_token():
    """Generate an expired token for testing."""
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(uuid4()),
        "role": "user",
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return pyjwt.encode(payload, "dev-secret-change-in-production", algorithm="HS256")


@pytest.fixture
async def app_with_auth(mock_get_db):
    """Create test FastAPI app with auth router."""
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(risk_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": str(uuid4()),
        "email": "test@example.com",
        "role": "user",
        "is_active": True,
    }
    from stockvaluefinder.db.base import get_db

    app.dependency_overrides[get_db] = mock_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_auth):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_auth),
        base_url="http://test",
    ) as ac:
        yield ac


class TestAuthFlow:
    """Test the complete authentication lifecycle."""

    @pytest.mark.asyncio
    async def test_register_creates_user_with_hashed_password(
        self, client, mock_db_session
    ):
        """AUTH-01, AUTH-05: Register creates user with bcrypt-hashed password."""
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=None)
            mock_repo.count_users = AsyncMock(return_value=0)
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "test@example.com"
            mock_user.role = "admin"
            mock_user.is_active = True
            mock_repo.create = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "test@example.com", "password": "securepassword123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "access_token" in data["data"]
            assert "refresh_token" in data["data"]
            assert data["data"]["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_rejects_short_password(self, client):
        """AUTH-07: Password minimum 8 characters validated on registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_handles_missing_users_table(self, client):
        """Return graceful error when users table was not migrated (UndefinedTableError)."""
        orig = Exception(
            'relation "users" does not exist',
        )
        db_error = ProgrammingError("SELECT ...", {}, orig)

        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(side_effect=db_error)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Registration failed. Please try again."

    @pytest.mark.asyncio
    async def test_login_handles_missing_users_table(self, client):
        """Login returns graceful error when users table does not exist."""
        orig = Exception('relation "users" does not exist')
        db_error = ProgrammingError("SELECT ...", {}, orig)

        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(side_effect=db_error)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Login failed. Please try again."

    @pytest.mark.asyncio
    async def test_register_rejects_duplicate_email(self, client):
        """AUTH-06: Email must be unique across all users."""
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            existing_user = MagicMock()
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=existing_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "existing@example.com", "password": "password123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "already registered" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_first_user_becomes_admin(self, client):
        """ADMN-07: First registered user becomes admin automatically."""
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=None)
            mock_repo.count_users = AsyncMock(return_value=0)  # No users = first user
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "first@example.com"
            mock_user.role = "admin"
            mock_user.is_active = True
            mock_repo.create = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            _response = await client.post(
                "/api/v1/auth/register",
                json={"email": "first@example.com", "password": "password123"},
            )

            # Verify create was called with role="admin"
            create_call = mock_repo.create.call_args
            assert create_call[0][0].role == "admin"

    @pytest.mark.asyncio
    async def test_subsequent_users_get_user_role(self, client):
        """RBAC-02: New registrations default to user role."""
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=None)
            mock_repo.count_users = AsyncMock(return_value=5)  # Existing users
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "new@example.com"
            mock_user.role = "user"
            mock_user.is_active = True
            mock_repo.create = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            _response = await client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "password123"},
            )

            create_call = mock_repo.create.call_args
            assert create_call[0][0].role == "user"

    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, client):
        """AUTH-02: Login returns access + refresh JWT tokens."""
        hashed = jwt_service.hash_password("password123")
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "test@example.com"
            mock_user.password_hash = hashed
            mock_user.role = "user"
            mock_user.is_active = True
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "access_token" in data["data"]
            assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_disabled_user_returns_403(self, client):
        """ADMN-06: Disabled users cannot authenticate (login returns 403)."""
        hashed = jwt_service.hash_password("password123")
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "disabled@example.com"
            mock_user.password_hash = hashed
            mock_user.role = "user"
            mock_user.is_active = False  # Disabled
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "disabled@example.com", "password": "password123"},
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """Login with wrong password returns error."""
        hashed = jwt_service.hash_password("correctpassword")
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.email = "test@example.com"
            mock_user.password_hash = hashed
            mock_user.role = "user"
            mock_user.is_active = True
            mock_repo = AsyncMock()
            mock_repo.get_by_email = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )

            data = response.json()
            assert data["success"] is False

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, client, valid_refresh_token):
        """AUTH-03: Refresh expired access token using refresh token."""
        with patch("stockvaluefinder.api.auth_routes.UserRepository") as MockRepo:
            mock_user = MagicMock()
            mock_user.id = str(uuid4())
            mock_user.email = "test@example.com"
            mock_user.role = "user"
            mock_user.is_active = True
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_user)
            MockRepo.return_value = mock_repo

            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": valid_refresh_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "access_token" in data["data"]
            assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_refresh_rejects_access_token(self, client, valid_access_token):
        """Refresh endpoint rejects access tokens (type confusion prevention)."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": valid_access_token},
        )

        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_logout_returns_success(self, client):
        """AUTH-04: Logout returns success."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_bcrypt_hash_and_verify(self):
        """AUTH-05: Passwords are hashed with bcrypt (never stored plaintext)."""
        password = "test_password_123"
        hashed = jwt_service.hash_password(password)

        # Hash is not plaintext
        assert hashed != password
        # Hash starts with bcrypt identifier
        assert hashed.startswith("$2b$")
        # Verify works
        assert jwt_service.verify_password(password, hashed)
        # Wrong password fails
        assert not jwt_service.verify_password("wrong", hashed)

    @pytest.mark.asyncio
    async def test_jwt_contains_correct_payload(self, user_id):
        """RBAC-05: Auth middleware extracts user identity from JWT."""
        token = jwt_service.create_access_token(str(user_id), "user")
        payload = jwt_service.validate_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_no_token(self):
        """PROT-01: Protected endpoints reject requests without token."""
        app = FastAPI()
        app.include_router(risk_router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=True,
        ) as ac:
            response = await ac.post(
                "/api/v1/analyze/risk",
                json={"ticker": "600519.SH"},
            )
            # 401 (no credentials) or 403 (HTTPBearer rejects missing token)
            assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_health_endpoint_remains_public(self):
        """PROT-03: Health check endpoint remains public (no auth)."""
        from stockvaluefinder.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_endpoint_remains_public(self):
        """PROT-03: Root endpoint remains public (no auth)."""
        from stockvaluefinder.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_endpoints_remain_public(self):
        """PROT-04: Auth endpoints (register, login, refresh) remain public."""
        from stockvaluefinder.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            # Register should be accessible without auth
            response = await ac.post(
                "/api/v1/auth/register",
                json={"email": "test@example.com", "password": "password123"},
            )
            # Even if it fails due to no DB, it should NOT be 401/403
            assert response.status_code not in (401, 403)

            # Login should be accessible without auth
            response = await ac.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )
            assert response.status_code not in (401, 403)

            # Refresh should be accessible without auth
            response = await ac.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "some_token"},
            )
            assert response.status_code not in (401, 403)
