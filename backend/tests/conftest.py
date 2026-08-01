import pytest


@pytest.fixture(autouse=True, scope="session")
def _init_db():
    from app.database import init_db

    init_db()
    yield
