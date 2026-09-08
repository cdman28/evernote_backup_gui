"""
tests_gui/test_command_builder.py
command_builder 모듈 단위 테스트
- build_export_command 다양한 옵션 조합 검증
- build_sync_command 옵션 검증
- build_init_db_command 옵션 검증
- build_manage_command 검증
"""

import pytest
from command_builder import (
    ExportOptions,
    SyncOptions,
    InitDbOptions,
    build_export_command,
    build_sync_command,
    build_init_db_command,
    build_manage_command,
)


def test_build_export_command_defaults():
    cmd = build_export_command("evernote-backup.exe", "test.db", "Export/", ExportOptions())
    assert cmd == [
        "evernote-backup.exe",
        "export",
        "--database",
        "test.db",
        "--overwrite",
        "Export/",
    ]


def test_build_export_command_all_options():
    opts = ExportOptions(
        single_notes=True,
        overwrite=True,
        add_metadata=True,
        no_export_date=True,
        include_trash=True,
        notebook="업무, 개인",
        tag="중요",
    )
    cmd = build_export_command("evernote-backup.exe", "test.db", "Export/", opts)
    assert "--single-notes" in cmd
    assert "--include-trash" in cmd
    assert "--no-export-date" in cmd
    assert "--add-metadata" in cmd
    assert "--overwrite" in cmd
    assert cmd.count("--notebook") == 2
    assert "업무" in cmd
    assert "개인" in cmd
    assert "--tag" in cmd
    assert "중요" in cmd
    assert cmd[-1] == "Export/"


def test_build_sync_command():
    cmd_default = build_sync_command("evernote-backup.exe", "test.db")
    assert cmd_default == ["evernote-backup.exe", "sync", "--database", "test.db"]

    opts = SyncOptions(use_system_ssl_ca=True, network_retry_count=10, token="my-token")
    cmd = build_sync_command("evernote-backup.exe", "test.db", opts)
    assert "--use-system-ssl-ca" in cmd
    assert "--network-retry-count" in cmd
    assert "10" in cmd
    assert "--token" in cmd
    assert "my-token" in cmd


def test_build_init_db_command():
    cmd = build_init_db_command(
        "evernote-backup.exe",
        "test.db",
        log_file="log.txt",
        options=InitDbOptions(
            backend="china",
            force=True,
            use_system_ssl_ca=True,
            oauth_host="127.0.0.1",
            token="my-auth-token",
        ),
    )
    assert cmd[0] == "evernote-backup.exe"
    assert "--verbose" in cmd
    assert "--log" in cmd
    assert "log.txt" in cmd
    assert "init-db" in cmd
    assert "--database" in cmd
    assert "test.db" in cmd
    assert "--force" in cmd
    assert "--backend" in cmd
    assert "china" in cmd
    assert "--use-system-ssl-ca" in cmd
    assert "--oauth-host" in cmd
    assert "127.0.0.1" in cmd
    assert "--token" in cmd
    assert "my-auth-token" in cmd


def test_build_manage_command():
    cmd_check = build_manage_command("evernote-backup.exe", "test.db", "check")
    assert cmd_check == ["evernote-backup.exe", "manage", "check", "--database", "test.db"]

    cmd_list = build_manage_command("evernote-backup.exe", "test.db", "list")
    assert cmd_list == ["evernote-backup.exe", "manage", "list", "--database", "test.db"]
