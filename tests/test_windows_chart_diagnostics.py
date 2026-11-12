"""Regressão: doctor precisa detectar falhas de importação de DLLs."""

from unittest.mock import patch

from fase4.interfaces import cli


def test_import_status_reports_missing_module():
    with patch.object(cli.importlib.util, "find_spec", return_value=None):
        assert cli._runtime_import_status("pyarrow") == "ausente"


def test_import_status_reports_native_import_error():
    def failing_import(name):
        raise ImportError("DLL load failed while importing lib")

    with patch.object(cli.importlib.util, "find_spec", return_value=object()):
        with patch.object(cli.importlib, "import_module", side_effect=failing_import):
            value = cli._runtime_import_status("pyarrow")
    assert "falha ao importar" in value
    assert "DLL load failed" in value


def test_import_status_succeeds_for_importable_module():
    assert cli._runtime_import_status("json") == "ok"
