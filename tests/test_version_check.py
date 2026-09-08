"""
tests_gui/test_version_check.py
version_check 모듈 단위 테스트
- 버전 문자열 파싱 성공 / 실패
- 버전 완전 일치 (MATCH)
- 버전 불일치 (MINOR_MISMATCH, MAJOR_MISMATCH)
"""

import pytest
from version_check import (
    parse_version_string,
    format_version_tuple,
    check_version_compatibility,
    VersionStatus,
    SUPPORTED_CLI_VERSION,
)


def test_parse_version_string_success():
    # 표준 CLI 출력 형식
    assert parse_version_string("evernote-backup.exe, version 1.14.0") == (1, 14, 0)
    assert parse_version_string("evernote-backup, version 1.13.1") == (1, 13, 1)
    assert parse_version_string("1.14.0") == (1, 14, 0)
    assert parse_version_string("v2.0.1") == (2, 0, 1)
    assert parse_version_string("version 1.5") == (1, 5, 0)


def test_parse_version_string_failure():
    assert parse_version_string("") is None
    assert parse_version_string("invalid string") is None
    assert parse_version_string("no-numbers-here") is None


def test_format_version_tuple():
    assert format_version_tuple((1, 14, 0)) == "1.14.0"
    assert format_version_tuple(None) == "알 수 없음"


def test_check_version_compatibility_match(monkeypatch):
    # mock run_cli_version to return expected version
    monkeypatch.setattr(
        "version_check.run_cli_version",
        lambda exe_path, timeout=5.0: "evernote-backup.exe, version 1.14.0",
    )
    res = check_version_compatibility("dummy.exe", expected_version="1.14.0")
    assert res.status == VersionStatus.MATCH
    assert res.can_proceed is True
    assert res.detected_version == "1.14.0"


def test_check_version_compatibility_minor_mismatch(monkeypatch):
    monkeypatch.setattr(
        "version_check.run_cli_version",
        lambda exe_path, timeout=5.0: "evernote-backup.exe, version 1.13.1",
    )
    res = check_version_compatibility("dummy.exe", expected_version="1.14.0")
    assert res.status == VersionStatus.MINOR_MISMATCH
    assert res.can_proceed is True
    assert "마이너" in res.message


def test_check_version_compatibility_major_mismatch(monkeypatch):
    monkeypatch.setattr(
        "version_check.run_cli_version",
        lambda exe_path, timeout=5.0: "evernote-backup.exe, version 2.0.0",
    )
    res = check_version_compatibility("dummy.exe", expected_version="1.14.0")
    assert res.status == VersionStatus.MAJOR_MISMATCH
    assert res.can_proceed is False
    assert "주요(Major) 버전 불일치" in res.message


def test_check_version_compatibility_unknown_or_failed(monkeypatch):
    monkeypatch.setattr(
        "version_check.run_cli_version",
        lambda exe_path, timeout=5.0: None,
    )
    res = check_version_compatibility("dummy.exe", expected_version="1.14.0")
    assert res.status == VersionStatus.UNKNOWN
    assert res.can_proceed is True
