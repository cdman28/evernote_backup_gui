"""
tests_gui/test_find_exe.py
evernote_backup_gui의 get_possible_exe_locations 및 find_evernote_exe 단위 테스트
"""

import os
import pytest
from evernote_backup_gui import get_possible_exe_locations, find_evernote_exe


def test_get_possible_exe_locations():
    locations = get_possible_exe_locations()
    assert len(locations) > 0
    # 필수 후보 경로들이 포함되어 있는지 검증
    assert any("evernote-backup" in loc for loc in locations)
    # 중복이 없는지 검증
    assert len(locations) == len(set(locations))


def test_find_evernote_exe_when_exists(monkeypatch, tmp_path):
    fake_exe = tmp_path / "evernote-backup.exe"
    fake_exe.write_text("fake binary")

    monkeypatch.setattr(
        "evernote_backup_gui.get_possible_exe_locations",
        lambda: [str(fake_exe)],
    )

    found = find_evernote_exe()
    assert found == os.path.abspath(str(fake_exe))


def test_find_evernote_exe_when_not_exists(monkeypatch):
    monkeypatch.setattr(
        "evernote_backup_gui.get_possible_exe_locations",
        lambda: ["/nonexistent/path/evernote-backup.exe"],
    )

    found = find_evernote_exe()
    assert found is None
