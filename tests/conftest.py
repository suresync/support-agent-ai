import pytest

from app.db import get_connection, init_db


@pytest.fixture
def db_conn(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    conn = get_connection(path)
    yield conn
    conn.close()
