"""
command_builder.py
evernote-backup CLI 명령 조립 및 옵션 정의 모듈 (SRP 및 Clean Architecture 준수)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExportOptions:
    """내보내기(export) 옵션 데이터클래스"""
    single_notes: bool = False
    overwrite: bool = True
    add_metadata: bool = False
    no_export_date: bool = False
    include_trash: bool = False
    notebook: Optional[str] = None
    tag: Optional[str] = None


@dataclass
class SyncOptions:
    """동기화(sync) 옵션 데이터클래스"""
    use_system_ssl_ca: bool = False
    network_retry_count: Optional[int] = None
    token: Optional[str] = None


@dataclass
class InitDbOptions:
    """DB 초기화 및 인증(init-db) 옵션 데이터클래스"""
    backend: str = "evernote"
    force: bool = True
    oauth_method: str = "desktop"  # 'desktop', 'import', 'mcp'
    use_system_ssl_ca: bool = False
    oauth_host: Optional[str] = None
    token: Optional[str] = None


@dataclass
class BlacklistOptions:
    """블랙리스트 관리(manage blacklist) 옵션 데이터클래스"""
    add_note_ids: List[str] = field(default_factory=list)
    add_notebook_ids: List[str] = field(default_factory=list)
    del_note_ids: List[str] = field(default_factory=list)
    del_notebook_ids: List[str] = field(default_factory=list)
    reset_notes: bool = False
    reset_notebooks: bool = False


def build_export_command(
    exe_path: str,
    db_path: str,
    export_dir: str,
    options: ExportOptions,
) -> List[str]:
    """ExportOptions 객체를 기반으로 CLI export 명령 리스트를 생성합니다."""
    cmd = [
        exe_path,
        "export",
        "--database",
        db_path,
    ]

    if options.single_notes:
        cmd.append("--single-notes")
    if options.include_trash:
        cmd.append("--include-trash")
    if options.no_export_date:
        cmd.append("--no-export-date")
    if options.add_metadata:
        cmd.append("--add-metadata")
    if options.overwrite:
        cmd.append("--overwrite")

    if options.notebook and options.notebook.strip():
        for nb in options.notebook.split(","):
            nb_clean = nb.strip()
            if nb_clean:
                cmd.extend(["--notebook", nb_clean])

    if options.tag and options.tag.strip():
        for tg in options.tag.split(","):
            tg_clean = tg.strip()
            if tg_clean:
                cmd.extend(["--tag", tg_clean])

    cmd.append(export_dir)
    return cmd


def build_sync_command(
    exe_path: str,
    db_path: str,
    options: Optional[SyncOptions] = None,
) -> List[str]:
    """SyncOptions 객체를 기반으로 CLI sync 명령 리스트를 생성합니다."""
    cmd = [
        exe_path,
        "sync",
        "--database",
        db_path,
    ]

    if options:
        if options.use_system_ssl_ca:
            cmd.append("--use-system-ssl-ca")
        if options.network_retry_count and options.network_retry_count > 0:
            cmd.extend(["--network-retry-count", str(options.network_retry_count)])
        if options.token and options.token.strip():
            cmd.extend(["--token", options.token.strip()])

    return cmd


def build_init_db_command(
    exe_path: str,
    db_path: str,
    log_file: Optional[str] = None,
    options: Optional[InitDbOptions] = None,
) -> List[str]:
    """InitDbOptions 객체를 기반으로 CLI init-db 명령 리스트를 생성합니다."""
    cmd = [exe_path]

    if log_file:
        cmd.extend(["--verbose", "--log", log_file])

    cmd.extend(["init-db", "--database", db_path])

    opts = options or InitDbOptions()
    if opts.force:
        cmd.append("--force")
    if opts.backend:
        cmd.extend(["--backend", opts.backend])
    if opts.oauth_method and opts.oauth_method.strip():
        cmd.extend(["--oauth-method", opts.oauth_method.strip()])
    if opts.use_system_ssl_ca:
        cmd.append("--use-system-ssl-ca")
    if opts.oauth_host and opts.oauth_host.strip():
        cmd.extend(["--oauth-host", opts.oauth_host.strip()])
    if opts.token and opts.token.strip():
        cmd.extend(["--token", opts.token.strip()])

    return cmd


def build_manage_command(
    exe_path: str,
    db_path: str,
    subcommand: str,  # 'check' or 'list'
) -> List[str]:
    """CLI manage 하위 명령(check, list 등) 리스트를 생성합니다."""
    # manage check 또는 manage list에 공통 -d/--database 인자
    return [
        exe_path,
        "manage",
        subcommand,
        "--database",
        db_path,
    ]


def build_manage_blacklist_command(
    exe_path: str,
    db_path: str,
    options: Optional[BlacklistOptions] = None,
) -> List[str]:
    """CLI manage blacklist 명령 리스트를 생성합니다."""
    cmd = [
        exe_path,
        "manage",
        "blacklist",
        "--database",
        db_path,
    ]

    if not options:
        # 옵션 없음 = 현재 블랙리스트 조회
        return cmd

    # add-note-id들 추가
    for note_id in options.add_note_ids:
        if note_id.strip():
            cmd.extend(["--add-note-id", note_id.strip()])

    # add-notebook-id들 추가
    for notebook_id in options.add_notebook_ids:
        if notebook_id.strip():
            cmd.extend(["--add-notebook-id", notebook_id.strip()])

    # del-note-id들 삭제
    for note_id in options.del_note_ids:
        if note_id.strip():
            cmd.extend(["--del-note-id", note_id.strip()])

    # del-notebook-id들 삭제
    for notebook_id in options.del_notebook_ids:
        if notebook_id.strip():
            cmd.extend(["--del-notebook-id", notebook_id.strip()])

    # reset-notes
    if options.reset_notes:
        cmd.append("--reset-notes")

    # reset-notebooks
    if options.reset_notebooks:
        cmd.append("--reset-notebooks")

    return cmd
