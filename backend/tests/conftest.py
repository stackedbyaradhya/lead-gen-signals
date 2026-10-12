import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.main import create_app
from app.models import Base


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://outcome:outcome@127.0.0.1:55432/outcome_test",
)


@pytest.fixture(autouse=True)
def clean_database():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture
def app():
    return create_app(TEST_DATABASE_URL)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def csv_upload():
    def upload(client, text, filename="leads.csv"):
        return client.post(
            "/api/imports",
            files={"file": (filename, text.encode("utf-8"), "text/csv")},
        )

    return upload
