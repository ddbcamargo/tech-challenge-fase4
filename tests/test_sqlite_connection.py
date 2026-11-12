"""Regressão: no Windows, bancos temporários devem ser fechados antes de remover a pasta."""

import sqlite3
from pathlib import Path

import pytest

from fase4.infrastructure.database import connect


def test_connect_closes_connection_after_context(tmp_path: Path):
    path = tmp_path / "records.sqlite3"
    with connect(path) as con:
        con.execute("CREATE TABLE samples (id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO samples(id) VALUES (1)")
        assert con.execute("SELECT count(*) FROM samples").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        con.execute("SELECT 1")
    # O teste de exclusão detectaria um handle de SQLite aberto no Windows.
    path.unlink()
    assert not path.exists()


def test_connect_closes_and_rolls_back_on_exception(tmp_path: Path):
    path = tmp_path / "rollback.sqlite3"
    with connect(path) as con:
        con.execute("CREATE TABLE samples (id INTEGER PRIMARY KEY)")
    with pytest.raises(RuntimeError, match="rollback expected"):
        with connect(path) as con:
            con.execute("INSERT INTO samples(id) VALUES (1)")
            raise RuntimeError("rollback expected")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        con.execute("SELECT 1")
    with connect(path) as other:
        assert other.execute("SELECT count(*) FROM samples").fetchone()[0] == 0
    path.unlink()
