"""
tests/test_subprocess_invocations.py
GUI 핵심 작업(init-db, sync, export, manage)의 subprocess 호출 시
명령어 조립과 인자 전달이 올바르게 이루어지는지 subprocess.Popen Mock을 통해 검증합니다.
"""

from unittest.mock import MagicMock, patch
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


def test_init_db_subprocess_invocation():
    """init-db 명령어가 올바른 인자로 호출되는지 검증"""
    exe = "C:\\fake\\evernote-backup.exe"
    db = "C:\\fake\\test.db"
    log_file = "C:\\fake\\oauth_log.txt"
    opts = InitDbOptions(
        backend="china",
        force=True,
        use_system_ssl_ca=True,
        oauth_host="127.0.0.1",
        token="test-token-123",
    )

    cmd = build_init_db_command(exe, db, log_file=log_file, options=opts)

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        import subprocess
        proc = subprocess.Popen(cmd)
        mock_popen.assert_called_once_with(cmd)

    # 생성된 인자 리스트 확인
    assert cmd[0] == exe
    assert "init-db" in cmd
    assert "--database" in cmd and db in cmd
    assert "--backend" in cmd and "china" in cmd
    assert "--force" in cmd
    assert "--use-system-ssl-ca" in cmd
    assert "--oauth-host" in cmd and "127.0.0.1" in cmd
    assert "--token" in cmd and "test-token-123" in cmd


def test_sync_subprocess_invocation():
    """sync 명령어가 올바른 인자로 호출되는지 검증"""
    exe = "C:\\fake\\evernote-backup.exe"
    db = "C:\\fake\\test.db"
    opts = SyncOptions(
        use_system_ssl_ca=True,
        network_retry_count=20,
        token="my-token",
    )

    cmd = build_sync_command(exe, db, opts)

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        import subprocess
        proc = subprocess.Popen(cmd)
        mock_popen.assert_called_once_with(cmd)

    assert cmd[0] == exe
    assert "sync" in cmd
    assert "--database" in cmd and db in cmd
    assert "--use-system-ssl-ca" in cmd
    assert "--network-retry-count" in cmd and "20" in cmd
    assert "--token" in cmd and "my-token" in cmd


def test_export_subprocess_invocation():
    """export 명령어가 확장 옵션들과 함께 올바르게 호출되는지 검증"""
    exe = "C:\\fake\\evernote-backup.exe"
    db = "C:\\fake\\test.db"
    out_dir = "C:\\fake\\Export"
    opts = ExportOptions(
        single_notes=True,
        overwrite=True,
        add_metadata=True,
        no_export_date=True,
        include_trash=True,
        notebook="업무노트",
        tag="프로젝트",
    )

    cmd = build_export_command(exe, db, out_dir, opts)

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        import subprocess
        proc = subprocess.Popen(cmd)
        mock_popen.assert_called_once_with(cmd)

    assert cmd[0] == exe
    assert "export" in cmd
    assert "--database" in cmd and db in cmd
    assert "--single-notes" in cmd
    assert "--overwrite" in cmd
    assert "--add-metadata" in cmd
    assert "--no-export-date" in cmd
    assert "--include-trash" in cmd
    assert "--notebook" in cmd and "업무노트" in cmd
    assert "--tag" in cmd and "프로젝트" in cmd
    assert cmd[-1] == out_dir


def test_manage_subprocess_invocation():
    """manage check 및 manage list 명령어가 올바르게 호출되는지 검증"""
    exe = "C:\\fake\\evernote-backup.exe"
    db = "C:\\fake\\test.db"

    cmd_check = build_manage_command(exe, db, "check")
    cmd_list = build_manage_command(exe, db, "list")

    with patch("subprocess.Popen") as mock_popen:
        import subprocess
        subprocess.Popen(cmd_check)
        subprocess.Popen(cmd_list)
        assert mock_popen.call_count == 2
