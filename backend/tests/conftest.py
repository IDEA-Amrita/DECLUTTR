import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

import app.models.schemas  # noqa: F401
import app.models.gdrive_schemas  # noqa: F401
from app.main import app as fastapi_app
from app.database import get_session, get_db, Base, create_db
import app.database


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    app.database.engine = engine
    create_db()
    with Session(engine) as session:
        yield session



@pytest.fixture(name="client")
def client_fixture(session: Session):
    def override_get_session():
        yield session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    fastapi_app.dependency_overrides[get_db] = override_get_session
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()



