from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.auth.tokens import create_access_token
from app.core.config import settings
from app.data_plane.gateway.main import app as gateway_app
from app.db.base import Base
from app.db.session import get_session
from app.main import app

DEFAULT_TEST_ADDRESS = "0x000000000000000000000000000000000000dEaD"


def auth_headers(address: str | None = None) -> dict[str, str]:
    addr = address or DEFAULT_TEST_ADDRESS
    token = create_access_token(addr)
    return {"Authorization": f"Bearer {token}"}


def _get_test_db_url() -> str:
    parsed = urlparse(settings.database_url)
    return urlunparse(parsed._replace(path="/studio_test"))


def _get_postgres_db_url() -> str:
    parsed = urlparse(settings.database_url)
    return urlunparse(parsed._replace(path="/postgres"))


test_engine = create_async_engine(_get_test_db_url(), poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


_db_initialized = False


@pytest_asyncio.fixture(autouse=True)
async def _setup_test_db():
    global _db_initialized
    if not _db_initialized:
        postgres_engine = create_async_engine(
            _get_postgres_db_url(),
            isolation_level="AUTOCOMMIT",
        )
        try:
            async with postgres_engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = 'studio_test'")
                )
                if not res.scalar():
                    await conn.execute(text("CREATE DATABASE studio_test"))
        except Exception:
            # Postgres not reachable; db fixture tests will fail with connection error
            pass
        finally:
            await postgres_engine.dispose()

        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            pass
        _db_initialized = True


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
        # Truncate all tables after each test
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest_asyncio.fixture
async def api(db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_session] = _override_get_session
    transport = httpx.ASGITransport(app=app)
    headers = auth_headers()
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


async def _no_db():
    # Scaffold endpoints raise before touching the DB; no Postgres needed.
    yield None


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_session] = _no_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(gateway_app)
