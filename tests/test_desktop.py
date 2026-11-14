from pathlib import Path
from desktop import user_data_dir


def test_user_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv('HUIYAN_DATA_DIR', str(tmp_path/'private'))
    assert user_data_dir() == tmp_path/'private'


def test_user_data_dir_defaults_to_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv('HUIYAN_DATA_DIR', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    assert user_data_dir() == tmp_path/'Huiyan'/'data'
