"""
에버노트 백업 도구 GUI
evernote-backup v1.14.0 CLI를 래핑한 사용자 친화적 인터페이스

주요 기능:
- 원클릭 OAuth 인증 (GUI 내부에서 자동 처리)
- 백업(동기화 + ENEX 내보내기) 실행 및 취소
- 실시간 진행률/로그 표시
- DB 상태 자동 감지 (기존 토큰 재사용)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import os
import sys
import subprocess
import webbrowser
import platform
import sqlite3
import tempfile
import time
import queue
import re
import shutil
from datetime import datetime

try:
    import pyperclip

    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

from version_check import (
    SUPPORTED_CLI_VERSION,
    VersionStatus,
    check_version_compatibility,
)
from command_builder import (
    ExportOptions,
    SyncOptions,
    InitDbOptions,
    build_export_command,
    build_sync_command,
    build_init_db_command,
    build_manage_command,
)


# =============================================================================
# 유틸리티 함수
# =============================================================================


def get_safe_db_path():
    """SQLite에 안전한 데이터베이스 경로를 자동으로 찾아 반환합니다."""
    if platform.system() == "Windows":
        candidates = [
            r"C:\EvernoteDB\evernote_backup.db",
            r"C:\temp\evernote_backup.db",
            os.path.join(os.environ.get("TEMP", ""), "evernote_backup.db"),
            r"C:\Users\Public\evernote_backup.db",
        ]
    else:
        candidates = [
            os.path.expanduser("~/evernote_backup.db"),
            "/tmp/evernote_backup.db",
            os.path.join(tempfile.gettempdir(), "evernote_backup.db"),
        ]

    for db_path in candidates:
        if _is_path_safe_for_sqlite(db_path):
            try:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                return db_path
            except Exception:
                continue

    raise Exception(
        "사용 가능한 안전한 데이터베이스 경로를 찾을 수 없습니다.\n"
        "관리자 권한으로 실행하거나 C 드라이브에 쓰기 권한을 확인해 주세요."
    )


def _is_path_safe_for_sqlite(db_path):
    """SQLite에서 사용하기 안전한 경로인지 확인합니다."""
    try:
        db_path.encode("ascii")
        if platform.system() == "Windows" and len(db_path) > 260:
            return False
        parent_dir = os.path.dirname(db_path)
        if os.path.exists(parent_dir) and not os.access(parent_dir, os.W_OK):
            return False
        return True
    except (UnicodeEncodeError, OSError):
        return False


def get_database_path():
    """데이터베이스 경로를 가져옵니다. 실패 시 임시 경로를 반환합니다."""
    try:
        return get_safe_db_path()
    except Exception:
        return os.path.join(
            tempfile.gettempdir(), f"evernote_backup_{os.getpid()}.db"
        )


def get_export_dir():
    """기본 내보내기 폴더 경로를 반환합니다."""
    base = os.path.dirname(get_database_path())
    out = os.path.join(base, "Export")
    os.makedirs(out, exist_ok=True)
    return out


def test_database_path(db_path):
    """DB 경로의 유효성을 검사합니다. (성공 여부, 메시지) 튜플을 반환합니다."""
    try:
        parent_dir = os.path.dirname(db_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        if not os.access(parent_dir, os.W_OK):
            return False, f"디렉토리 쓰기 권한 없음: {parent_dir}"
        return True, "OK"
    except Exception as e:
        return False, str(e)


def get_possible_exe_locations():
    """evernote-backup.exe를 탐색할 후보 경로 목록을 반환합니다."""
    exe_name = "evernote-backup.exe" if platform.system() == "Windows" else "evernote-backup"
    # PyInstaller onefile 실행 시 __file__은 임시 추출 폴더를 가리키므로
    # sys.executable(실제 exe 경로)에서 폴더를 구한다
    if getattr(sys, "frozen", False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    exec_dir = os.path.dirname(sys.executable)
    cwd = os.getcwd()

    candidates = [
        os.path.join(script_dir, exe_name),  # GUI exe와 같은 폴더 (최우선)
        os.path.join(cwd, exe_name),          # 현재 작업 디렉터리
        exe_name,                             # PATH 내 상대경로
        os.path.join(script_dir, "bin", exe_name),
        os.path.join(script_dir, "cli", exe_name),
        os.path.join(cwd, "bin", exe_name),
        os.path.join(cwd, "cli", exe_name),
        shutil.which(exe_name) or "",
    ]
    seen = set()
    result = []
    for path in candidates:
        if not path:
            continue
        norm_path = os.path.normpath(os.path.abspath(path))
        if norm_path not in seen:
            seen.add(norm_path)
            result.append(norm_path)
    return result


def find_evernote_exe():
    """evernote-backup.exe 파일을 찾아 절대 경로를 반환합니다."""
    for path in get_possible_exe_locations():
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def get_db_info(db_path):
    """기존 DB에서 요약 정보를 읽어옵니다."""
    info = {
        "exists": False,
        "notes": 0,
        "notebooks": 0,
        "has_token": False,
        "backend": "",
    }
    if not os.path.exists(db_path):
        return info

    info["exists"] = True
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        for query, key in [
            ("SELECT COUNT(*) FROM notes", "notes"),
            ("SELECT COUNT(*) FROM notebooks", "notebooks"),
        ]:
            try:
                cur.execute(query)
                info[key] = cur.fetchone()[0]
            except Exception:
                pass

        try:
            cur.execute("SELECT value FROM config WHERE name='auth_token'")
            row = cur.fetchone()
            info["has_token"] = bool(row and row[0])
        except Exception:
            pass

        try:
            cur.execute("SELECT value FROM config WHERE name='backend'")
            row = cur.fetchone()
            info["backend"] = row[0] if row else ""
        except Exception:
            pass

        conn.close()
    except Exception:
        pass

    return info


def format_elapsed(seconds):
    """초를 사람이 읽기 쉬운 형태로 변환합니다."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}초"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}분 {s}초"
    else:
        h, rem = divmod(seconds, 3600)
        m, _ = divmod(rem, 60)
        return f"{h}시간 {m}분"


# =============================================================================
# GUI 메인 클래스
# =============================================================================


class EvernoteBackupApp:
    VERSION = "v1.14.4"
    BUILD_DATE = "2026.09"

    # 무시 가능한 에러 패턴 (동기화 중 건너뛸 수 있는 항목)
    IGNORABLE_PATTERNS = [
        "failed to download note",
        "note.will be skipped",
        "linkednotebook.is not accessible",
        "remoteserver returned system error",
        "permission_denied",
        "not_found",
        "authentication failed",
        "shared notebook.not found",
        "business notebook.expired",
    ]

    def __init__(self, root):
        self.root = root
        self.root.title(f"에버노트 백업 도구 (GUI for evernote-backup {self.VERSION})")
        self.root.geometry("960x860")
        self.root.minsize(820, 720)

        # 상태 변수
        self.is_working = False
        self.is_logged_in = False
        self.database_path = get_database_path()
        self.export_dir = get_export_dir()

        # 프로세스 관리 (취소 기능용)
        self._current_process = None
        self._cancel_requested = False
        self._db_connection = None
        self._clipboard_monitor_active = False
        self._clipboard_last = ""

        # 진행률 추적
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        self.sync_start_time: float = 0.0

        # DB 실시간 모니터링
        self._db_monitor_active = False
        self._db_monitor_initial_notes = 0

        # 실시간 로그를 위한 큐
        self.log_queue = queue.Queue()

        # EXE 경로
        self.evernote_exe = None

        # UI 구성
        self._setup_variables()
        self._setup_styles()
        self._setup_fonts()
        self._create_widgets()
        self._validate_and_init_database()
        self._check_evernote_exe()
        self._check_log_queue()

        # 시작 로그
        self._log("🚀 에버노트 백업 도구 시작")
        self._log(f"🖥️ OS: {platform.system()} | Python: {sys.version.split()[0]}")
        self._log(f"💾 DB: {self.database_path}")
        self._log(f"📁 내보내기: {self.export_dir}")

    # =========================================================================
    # 초기 설정
    # =========================================================================

    def _check_evernote_exe(self):
        """EXE 파일을 검증하고 CLI 버전 호환성을 확인합니다."""
        self.evernote_exe = find_evernote_exe()
        if not self.evernote_exe:
            self._log("❌ evernote-backup.exe를 찾을 수 없습니다")
            self._log("💡 이 GUI와 같은 폴더에 배치해 주세요")
            self._show_exe_missing_dialog()
            return

        self._log(f"✅ evernote-backup.exe 발견: {self.evernote_exe}")

        # 버전 호환성 검사 (version_check 모듈 활용)
        check_res = check_version_compatibility(self.evernote_exe)
        self._log(f"🔎 CLI 버전: {check_res.message}")

        if check_res.status == VersionStatus.MATCH:
            self._log(f"✅ CLI 버전이 권장 버전(v{SUPPORTED_CLI_VERSION})과 일치합니다.")
        elif check_res.status == VersionStatus.PATCH_MISMATCH:
            self._log(f"ℹ️ {check_res.message}")
        elif check_res.status == VersionStatus.MINOR_MISMATCH:
            self._log(f"⚠️ {check_res.message}")
            # 마이너 버전 불일치: 경고 후 사용자 확인
            proceed = messagebox.askyesno(
                "CLI 버전 차이 알림",
                f"{check_res.message}\n\n계속 진행하시겠습니까?",
                icon="warning",
            )
            if not proceed:
                self._log("⏹ 사용자가 버전 차이로 인해 실행을 중단했습니다.")
                self.btn_oauth.config(state=tk.DISABLED)
                self.btn_backup.config(state=tk.DISABLED)
                self._set_status("CLI 버전 차이로 기능이 일시 중지됨", "warning")
        elif check_res.status == VersionStatus.MAJOR_MISMATCH:
            self._log(f"❌ {check_res.message}")
            messagebox.showerror("호환 불가 CLI 버전", check_res.message)
            self.btn_oauth.config(state=tk.DISABLED)
            self.btn_backup.config(state=tk.DISABLED)
            self._set_status("호환되지 않는 CLI 버전 (실행 차단)", "error")
        else:
            self._log(f"⚠️ {check_res.message}")

    def _show_exe_missing_dialog(self):
        """EXE 파일 누락 시 검색된 경로 목록과 함께 상세 안내 다이얼로그를 표시합니다."""
        dialog = tk.Toplevel(self.root)
        dialog.title("필수 파일 누락")
        dialog.geometry("560x420")
        dialog.grab_set()
        dialog.transient(self.root)
        dialog.resizable(False, False)

        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 280
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 210
        dialog.geometry(f"560x420+{x}+{y}")

        frame = tk.Frame(dialog, padx=20, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="⚠️ evernote-backup.exe 파일이 필요합니다",
            font=("맑은 고딕", 12, "bold"),
            fg=self.colors["error"],
        ).pack(pady=(0, 8))

        tk.Label(
            frame,
            text=(
                "이 프로그램은 evernote-backup.exe와 함께 사용해야 합니다.\n"
                "아래 검색 경로에 evernote-backup.exe 파일이 존재하지 않습니다:"
            ),
            font=("맑은 고딕", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 6))

        # 검색된 경로 목록 표시 (스크롤 박스)
        searched_paths = get_possible_exe_locations()
        path_box = scrolledtext.ScrolledText(
            frame, height=5, font=("Consolas", 8), bg="#F5F5F5", relief=tk.SUNKEN
        )
        path_box.pack(fill=tk.X, pady=(0, 10))
        for p in searched_paths:
            path_box.insert(tk.END, f"• {p}\n")
        path_box.config(state=tk.DISABLED)

        tk.Label(
            frame,
            text=(
                "📥 설치 방법:\n"
                "  1. 아래 버튼으로 GitHub 릴리스 페이지를 엽니다.\n"
                "  2. 최신 Windows용 zip을 받아 evernote-backup.exe를 추출합니다.\n"
                "  3. 이 GUI 프로그램과 같은 폴더에 넣어주세요.\n"
                "  4. 프로그램을 다시 실행해 주세요."
            ),
            font=("맑은 고딕", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 12))

        btn_frame = tk.Frame(frame)
        btn_frame.pack()

        tk.Button(
            btn_frame,
            text="📥 GitHub에서 다운로드",
            command=lambda: webbrowser.open(
                "https://github.com/vzhd1701/evernote-backup/releases"
            ),
            font=("맑은 고딕", 10, "bold"),
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=15,
            pady=5,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="닫기",
            command=dialog.destroy,
            font=("맑은 고딕", 10),
            padx=15,
            pady=5,
        ).pack(side=tk.LEFT)

    def _setup_variables(self):
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar(value=self.export_dir)

        # Export 옵션 변수 (3-1단계)
        self.opt_single_notes = tk.BooleanVar(value=False)
        self.opt_overwrite = tk.BooleanVar(value=True)
        self.opt_add_metadata = tk.BooleanVar(value=False)
        self.opt_no_export_date = tk.BooleanVar(value=False)
        self.opt_include_trash = tk.BooleanVar(value=False)
        self.opt_notebook_filter = tk.StringVar(value="")
        self.opt_tag_filter = tk.StringVar(value="")

        # 고급 설정 변수 (3-3단계)
        self.oauth_method_var = tk.StringVar(value="import")
        self.opt_use_system_ssl = tk.BooleanVar(value=False)
        self.opt_oauth_host = tk.StringVar(value="")
        self.opt_manual_token = tk.StringVar(value="")
        self.show_advanced = tk.BooleanVar(value=False)

    def _setup_styles(self):
        self.colors = {
            "green": "#1B7F37",        # 짙은 에버노트 녹색 — 흰 배경 위에서 선명
            "bg": "#FFFFFF",            # 깨끗한 흰색 배경
            "text": "#1A1A1A",          # 거의 검정 — 최고 가독성
            "light": "#555555",          # 보조 텍스트 — 충분히 진한 회색
            "success": "#1B7F37",        # 성공 = 짙은 녹색
            "warning": "#C65100",        # 경고 = 짙은 주황 (명도 낮춤)
            "error": "#C62828",          # 오류 = 짙은 빨강
            "primary": "#1565C0",        # 기본 파랑 (짙은 톤)
            "btn_bg": "#1565C0",         # 일반 버튼 배경 — 진한 파랑
            "btn_green": "#157A30",      # 핵심 버튼(인증/백업) — 진한 에버노트 녹색
            "btn_text": "#FFFFFF",       # 버튼 글자 — 순백
            "btn_disabled": "#BDBDBD",   # 비활성 버튼
            "border": "#BDBDBD",         # 테두리
            "cancel": "#C62828",         # 취소/중지 — 짙은 빨강
            "section_fg": "#1A1A1A",     # 섹션 제목 — 검정 (녹색 대신)
            "section_accent": "#1B7F37", # 섹션 아이콘/강조 색
            "log_bg": "#FAFAFA",         # 로그 배경 — 약간 회색
        }

    def _setup_fonts(self):
        self.fonts = {
            "title": ("맑은 고딕", 20, "bold"),
            "subtitle": ("맑은 고딕", 10),
            "section": ("맑은 고딕", 11, "bold"),
            "btn_lg": ("맑은 고딕", 12, "bold"),
            "btn_md": ("맑은 고딕", 10, "bold"),
            "btn_sm": ("맑은 고딕", 9),
            "label": ("맑은 고딕", 9, "bold"),
            "text": ("맑은 고딕", 9),        # 8→9: 가독성 향상
            "small": ("맑은 고딕", 9),       # 8→9
            "status": ("맑은 고딕", 10, "bold"), # 9→10
            "log": ("Consolas", 9),          # 고정폭 폰트로 로그 정렬
        }

    # =========================================================================
    # UI 생성
    # =========================================================================

    def _create_widgets(self):
        container = tk.Frame(self.root, bg=self.colors["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self._create_header(container)

        main_frame = tk.Frame(container, bg=self.colors["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(main_frame, bg=self.colors["bg"])
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        right_col = tk.Frame(main_frame, bg=self.colors["bg"])
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 왼쪽: 설정 패널들
        self._create_db_section(left_col)
        self._create_oauth_section(left_col)
        self._create_backup_section(left_col)

        # 오른쪽 상단: 동기화 정보 + 진단 도구 (나란히)
        info_panel = tk.Frame(right_col, bg=self.colors["bg"])
        info_panel.pack(fill=tk.X, pady=(0, 6))
        self._create_status_section(info_panel)
        self._create_tools_section(info_panel)

        # 오른쪽: 로그
        self._create_log_section(right_col)

    def _create_header(self, parent):
        header = tk.Frame(parent, bg=self.colors["bg"])
        header.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            header,
            text="📋 에버노트 백업 도구",
            font=self.fonts["title"],
            fg=self.colors["green"],
            bg=self.colors["bg"],
        ).pack()

        tk.Label(
            header,
            text=f"GUI for evernote-backup {self.VERSION} | {self.BUILD_DATE}",
            font=self.fonts["subtitle"],
            fg=self.colors["text"],
            bg=self.colors["bg"],
        ).pack()

        btn_frame = tk.Frame(header, bg=self.colors["bg"])
        btn_frame.pack(pady=(5, 0))

        for btn_text, cmd in [
            ("📋 사용법", self._show_usage),
            ("🔗 정보", self._show_about),
        ]:
            tk.Button(
                btn_frame,
                text=btn_text,
                command=cmd,
                font=self.fonts["btn_sm"],
                bg=self.colors["btn_bg"],
                fg=self.colors["btn_text"],
                padx=12,
                pady=3,
            ).pack(side=tk.LEFT, padx=4)

    def _create_db_section(self, parent):
        frame = tk.LabelFrame(
            parent,
            text="💾 DB 설정",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=10,
            pady=8,
        )
        frame.pack(fill=tk.X, pady=(0, 10))

        self.db_status_label = tk.Label(
            frame, text="🔍 확인 중...", font=self.fonts["small"]
        )
        self.db_status_label.pack(anchor=tk.W, pady=(0, 3))

        self.db_info_label = tk.Label(
            frame, text="", font=self.fonts["small"], fg=self.colors["light"]
        )
        self.db_info_label.pack(anchor=tk.W, pady=(0, 3))

        tk.Label(frame, text="경로:", font=self.fonts["label"]).pack(anchor=tk.W)

        path_frame = tk.Frame(frame)
        path_frame.pack(fill=tk.X, pady=2)

        self.db_path_var = tk.StringVar(value=self.database_path)
        tk.Entry(
            path_frame,
            textvariable=self.db_path_var,
            font=self.fonts["text"],
            state="readonly",
            width=35,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            path_frame,
            text="변경",
            command=self._change_db_path,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=8,
            pady=2,
        ).pack(side=tk.RIGHT, padx=(5, 0))

    def _create_oauth_section(self, parent):
        frame = tk.LabelFrame(
            parent,
            text="🔐 OAuth 로그인",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=10,
            pady=8,
        )
        frame.pack(fill=tk.X, pady=(0, 8))

        self.oauth_status_label = tk.Label(
            frame,
            text="🔑 로그인 필요",
            font=self.fonts["small"],
            fg=self.colors["warning"],
        )
        self.oauth_status_label.pack(anchor=tk.W, pady=(0, 4))

        # OAuth 인증 방식 선택
        m_frame = tk.LabelFrame(frame, text="인증 방식 선택", font=self.fonts["small"], padx=6, pady=4)
        m_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Radiobutton(
            m_frame,
            text="📌 에버노트 앱 세션 자동 가져오기 (import - 추천)",
            variable=self.oauth_method_var,
            value="import",
            font=self.fonts["small"],
        ).pack(anchor=tk.W)
        tk.Radiobutton(
            m_frame,
            text="🌐 웹 브라우저 인증 (desktop)",
            variable=self.oauth_method_var,
            value="desktop",
            font=self.fonts["small"],
        ).pack(anchor=tk.W)
        tk.Radiobutton(
            m_frame,
            text="⚡ MCP 로컬 서버 인증 (mcp)",
            variable=self.oauth_method_var,
            value="mcp",
            font=self.fonts["small"],
        ).pack(anchor=tk.W)

        self.btn_oauth = tk.Button(
            frame,
            text="🔐 OAuth 인증 시작",
            font=self.fonts["btn_md"],
            bg=self.colors["btn_green"],
            fg=self.colors["btn_text"],
            activebackground="#0E5E22",
            activeforeground="#FFFFFF",
            disabledforeground="#FFFFFF",
            command=self._start_oauth,
            padx=15,
            pady=5,
            width=20,
        )
        self.btn_oauth.pack(pady=(0, 4))

        self.oauth_progress_label = tk.Label(
            frame,
            text="",
            font=self.fonts["small"],
            fg=self.colors["light"],
            wraplength=280,
            justify=tk.LEFT,
        )
        self.oauth_progress_label.pack(anchor=tk.W)

        # --- URL 도우미 (OAuth 진행 중에만 표시) ---
        self.url_helper_frame = tk.Frame(frame, bg=self.colors["bg"])

        tk.Label(
            self.url_helper_frame,
            text="브라우저가 안 열리면 콘솔 URL을 아래에 붙여넣기:",
            font=self.fonts["small"],
            fg=self.colors["light"],
            bg=self.colors["bg"],
        ).pack(anchor=tk.W)

        url_row = tk.Frame(self.url_helper_frame, bg=self.colors["bg"])
        url_row.pack(fill=tk.X, pady=(2, 0))

        self.oauth_url_var = tk.StringVar()
        self.oauth_url_entry = tk.Entry(
            url_row,
            textvariable=self.oauth_url_var,
            font=self.fonts["text"],
            width=28,
        )
        self.oauth_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_open_url = tk.Button(
            url_row,
            text="🌐 열기",
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=6,
            pady=2,
            command=self._open_oauth_url_manual,
        )
        self.btn_open_url.pack(side=tk.RIGHT, padx=(4, 0))

        # --- 3-3 고급 설정 접이식 섹션 ---
        self.btn_toggle_advanced = tk.Button(
            frame,
            text="⚙️ 고급 인증/네트워크 설정 ▼",
            command=self._toggle_advanced_options,
            font=self.fonts["small"],
            relief=tk.FLAT,
            fg=self.colors["primary"],
            cursor="hand2",
        )
        self.btn_toggle_advanced.pack(anchor=tk.W, pady=(4, 0))

        self.advanced_frame = tk.Frame(frame)

        b_row = tk.Frame(self.advanced_frame)
        b_row.pack(fill=tk.X, pady=(2, 2))
        tk.Label(b_row, text="서버:", font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Radiobutton(b_row, text="글로벌", variable=self.backend_var, value="evernote", font=self.fonts["small"]).pack(side=tk.LEFT, padx=3)
        tk.Radiobutton(b_row, text="인샹(중국)", variable=self.backend_var, value="china", font=self.fonts["small"]).pack(side=tk.LEFT)

        tk.Checkbutton(
            self.advanced_frame,
            text="시스템 SSL CA 사용 (--use-system-ssl-ca)",
            variable=self.opt_use_system_ssl,
            font=self.fonts["small"],
        ).pack(anchor=tk.W)

        h_row = tk.Frame(self.advanced_frame)
        h_row.pack(fill=tk.X, pady=1)
        tk.Label(h_row, text="OAuth 호스트:", font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Entry(h_row, textvariable=self.opt_oauth_host, font=self.fonts["text"], width=18).pack(side=tk.LEFT, padx=4)

        t_row = tk.Frame(self.advanced_frame)
        t_row.pack(fill=tk.X, pady=1)
        tk.Label(t_row, text="수동 토큰:", font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Entry(t_row, textvariable=self.opt_manual_token, font=self.fonts["text"], width=20, show="*").pack(side=tk.LEFT, padx=4)

    def _toggle_advanced_options(self):
        """고급 설정 섹션을 접거나 펼칩니다."""
        if self.show_advanced.get():
            self.advanced_frame.pack_forget()
            self.show_advanced.set(False)
            self.btn_toggle_advanced.config(text="⚙️ 고급 인증/네트워크 설정 ▼")
        else:
            self.advanced_frame.pack(fill=tk.X, pady=(4, 2))
            self.show_advanced.set(True)
            self.btn_toggle_advanced.config(text="⚙️ 고급 인증/네트워크 설정 ▲")

    def _create_backup_section(self, parent):
        frame = tk.LabelFrame(
            parent,
            text="💾 백업 및 내보내기 설정",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=10,
            pady=8,
        )
        frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(frame, text="내보내기 폴더:", font=self.fonts["label"]).pack(anchor=tk.W)

        folder_frame = tk.Frame(frame)
        folder_frame.pack(fill=tk.X, pady=2)

        tk.Entry(
            folder_frame,
            textvariable=self.output_path,
            font=self.fonts["text"],
            width=35,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            folder_frame,
            text="찾기",
            command=self._browse_output,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=8,
            pady=2,
        ).pack(side=tk.RIGHT, padx=(5, 0))

        # --- 3-1 세부 내보내기 옵션 ---
        opt_box = tk.LabelFrame(frame, text="내보내기 세부 옵션", font=self.fonts["small"], padx=6, pady=4)
        opt_box.pack(fill=tk.X, pady=(6, 4))

        cb_row1 = tk.Frame(opt_box)
        cb_row1.pack(fill=tk.X)
        tk.Checkbutton(cb_row1, text="덮어쓰기 (--overwrite)", variable=self.opt_overwrite, font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Checkbutton(cb_row1, text="개별 노트 분할 (--single-notes)", variable=self.opt_single_notes, font=self.fonts["small"]).pack(side=tk.LEFT, padx=(8, 0))

        cb_row2 = tk.Frame(opt_box)
        cb_row2.pack(fill=tk.X)
        tk.Checkbutton(cb_row2, text="메타데이터 포함", variable=self.opt_add_metadata, font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Checkbutton(cb_row2, text="날짜 제외", variable=self.opt_no_export_date, font=self.fonts["small"]).pack(side=tk.LEFT, padx=(6, 0))
        tk.Checkbutton(cb_row2, text="휴지통 포함", variable=self.opt_include_trash, font=self.fonts["small"]).pack(side=tk.LEFT, padx=(6, 0))

        filter_box = tk.Frame(opt_box)
        filter_box.pack(fill=tk.X, pady=(3, 1))

        f_nb = tk.Frame(filter_box)
        f_nb.pack(fill=tk.X, pady=1)
        tk.Label(f_nb, text="노트북 필터:", font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Entry(f_nb, textvariable=self.opt_notebook_filter, font=self.fonts["text"]).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        f_tg = tk.Frame(filter_box)
        f_tg.pack(fill=tk.X, pady=1)
        tk.Label(f_tg, text="태그 필터:    ", font=self.fonts["small"]).pack(side=tk.LEFT)
        tk.Entry(f_tg, textvariable=self.opt_tag_filter, font=self.fonts["text"]).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # 백업 시작 + 중지 버튼
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=(8, 0))

        self.btn_backup = tk.Button(
            btn_frame,
            text="🚀 백업 시작",
            font=self.fonts["btn_lg"],
            bg=self.colors["btn_green"],
            fg=self.colors["btn_text"],
            activebackground="#0E5E22",
            activeforeground="#FFFFFF",
            disabledforeground="#FFFFFF",
            command=self._start_backup,
            state="disabled",
            padx=20,
            pady=6,
        )
        self.btn_backup.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_cancel = tk.Button(
            btn_frame,
            text="⏹ 중지",
            font=self.fonts["btn_lg"],
            bg=self.colors["cancel"],
            fg=self.colors["btn_text"],
            activebackground="#8E0000",
            activeforeground="#FFFFFF",
            disabledforeground="#FFFFFF",
            command=self._cancel_backup,
            state="disabled",
            padx=15,
            pady=6,
        )
        self.btn_cancel.pack(side=tk.LEFT)

    def _create_tools_section(self, parent):
        """3-2 DB 진단 기능 (manage check, manage list) 섹션을 생성합니다."""
        frame = tk.LabelFrame(
            parent,
            text="🛠️ 진단 및 관리 도구",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=10,
            pady=6,
        )
        frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.btn_manage_check = tk.Button(
            frame,
            text="🔍 DB 무결성 검사 (check)",
            command=self._start_manage_check,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=6,
            pady=3,
        )
        self.btn_manage_check.pack(fill=tk.X, pady=(0, 4))

        self.btn_manage_list = tk.Button(
            frame,
            text="📋 노트북 목록 조회 (list)",
            command=self._start_manage_list,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=6,
            pady=3,
        )
        self.btn_manage_list.pack(fill=tk.X)

    def _start_manage_check(self):
        """DB 무결성 검사(manage check)를 시작합니다."""
        if not self._check_can_run_tool():
            return
        self._log("🔍 [진단] DB 무결성 검사 (manage check)를 시작합니다...")
        threading.Thread(target=self._run_manage_task, args=("check", "DB 무결성 검사"), daemon=True).start()

    def _start_manage_list(self):
        """백업된 노트북 목록 조회(manage list)를 시작합니다."""
        if not self._check_can_run_tool():
            return
        self._log("📋 [조회] 백업 데이터베이스 노트북 목록 (manage list)을 조회합니다...")
        threading.Thread(target=self._run_manage_task, args=("list", "노트북 목록 조회"), daemon=True).start()

    def _check_can_run_tool(self):
        """도구 실행 전 DB 존재 여부 및 작업 중 상태를 확인합니다."""
        if not self.evernote_exe:
            messagebox.showerror("오류", "evernote-backup.exe 파일을 찾을 수 없습니다.")
            return False
        if not os.path.exists(self.database_path):
            messagebox.showwarning("DB 없음", "데이터베이스 파일이 존재하지 않습니다.\n먼저 OAuth 인증 및 동기화를 진행해 주세요.")
            return False
        if self.is_working:
            messagebox.showwarning("진행 중", "현재 다른 작업이 진행 중입니다.")
            return False
        return True

    def _run_manage_task(self, subcommand: str, task_name: str):
        """백그라운드에서 evernote-backup manage [check|list]를 실행하고 로그에 출력합니다."""
        try:
            self.is_working = True
            self.root.after(0, lambda: self._set_status(f"{task_name} 실행 중...", "warning"))

            cmd = build_manage_command(self.evernote_exe, self.database_path, subcommand)
            self._queue_log(f"🔧 실행: {' '.join(cmd)}")

            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
            )
            assert proc.stdout is not None

            for line in proc.stdout:
                line = line.strip()
                if line:
                    self._queue_log(f"[{subcommand.upper()}] {line}")

            proc.wait()
            if proc.returncode == 0:
                self._queue_log(f"✅ {task_name} 완료")
                self.root.after(0, lambda: self._set_status(f"{task_name} 완료", "success"))
            else:
                self._queue_log(f"⚠️ {task_name} 비정상 종료 (종료 코드: {proc.returncode})")
                self.root.after(0, lambda: self._set_status(f"{task_name} 오류 발생", "error"))
        except Exception as e:
            self._queue_log(f"❌ {task_name} 실행 오류: {str(e)}")
            self.root.after(0, lambda: self._set_status(f"{task_name} 실패", "error"))
        finally:
            self.is_working = False

    def _create_status_section(self, parent):
        frame = tk.LabelFrame(
            parent,
            text="📊 동기화 상태",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=8,
            pady=6,
        )
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=3)

        self.status_label = tk.Label(
            frame,
            text="대기 중",
            font=self.fonts["status"],
            fg=self.colors["success"],
            bg=self.colors["bg"],
        )
        self.status_label.pack(anchor=tk.W)

        self.progress_detail_label = tk.Label(
            frame,
            text="",
            font=self.fonts["small"],
            fg=self.colors["light"],
            bg=self.colors["bg"],
        )
        self.progress_detail_label.pack(anchor=tk.W)

        self.progress_numbers_label = tk.Label(
            frame,
            text="",
            font=self.fonts["small"],
            fg=self.colors["text"],
            bg=self.colors["bg"],
        )
        self.progress_numbers_label.pack(anchor=tk.W)

    def _create_log_section(self, parent):
        frame = tk.LabelFrame(
            parent,
            text="📄 로그",
            font=self.fonts["section"],
            fg=self.colors["section_fg"],
            padx=10,
            pady=10,
        )
        frame.pack(fill=tk.BOTH, expand=True)

        self.text_log = scrolledtext.ScrolledText(
            frame,
            font=self.fonts["log"],
            bg=self.colors["log_bg"],
            fg=self.colors["text"],
            wrap=tk.WORD,
            relief=tk.SUNKEN,
            borderwidth=1,
        )
        self.text_log.pack(fill=tk.BOTH, expand=True)

        log_btns = tk.Frame(frame)
        log_btns.pack(fill=tk.X, pady=(5, 0))

        tk.Button(
            log_btns,
            text="💾 로그 저장",
            command=self._save_log,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=8,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            log_btns,
            text="🗑️ 로그 지우기",
            command=self._clear_log,
            font=self.fonts["btn_sm"],
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=8,
            pady=2,
        ).pack(side=tk.LEFT)

    # =========================================================================
    # OAuth 인증 (GUI 내부에서 자동 처리)
    # =========================================================================

    def _start_oauth(self):
        """OAuth 인증을 시작합니다.

        evernote-backup CLI는 sys.stdout.isatty() 체크를 하기 때문에
        subprocess.PIPE로는 실행할 수 없습니다.
        따라서 CREATE_NEW_CONSOLE로 실제 콘솔 창을 띄워 isatty를 통과시키고,
        프로세스 종료 후 DB에서 토큰 존재 여부를 확인하여 성공/실패를 판단합니다.
        """
        if not self.evernote_exe:
            messagebox.showerror(
                "오류",
                "evernote-backup.exe 파일을 찾을 수 없습니다.\n"
                "이 GUI와 같은 폴더에 배치해 주세요.",
            )
            return

        if self.is_working:
            messagebox.showwarning("진행 중", "이미 작업이 진행 중입니다.")
            return

        is_valid, err = test_database_path(self.database_path)
        if not is_valid:
            messagebox.showerror(
                "DB 경로 오류", f"데이터베이스 경로에 문제가 있습니다:\n{err}"
            )
            return

        self._close_db_connection()
        self.btn_oauth.config(
            state=tk.DISABLED, text="🔐 인증 진행 중...",
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.oauth_progress_label.config(
            text="콘솔 창이 열립니다. 브라우저에서 인증을 완료해 주세요."
        )
        self._set_status("OAuth 인증 진행 중...", "warning")
        self._log("🔐 OAuth 인증을 시작합니다...")

        # URL 도우미 표시
        self.oauth_url_var.set("")
        self.url_helper_frame.pack(fill=tk.X, pady=(8, 0))

        # 클립보드 자동 감시 시작 (현재 클립보드 내용으로 초기화하여 이전 URL 재감지 방지)
        self._clipboard_monitor_active = True
        try:
            self._clipboard_last = self.root.clipboard_get()
        except Exception:
            self._clipboard_last = ""
        self._start_clipboard_monitor()

        threading.Thread(target=self._oauth_task, daemon=True).start()

    def _oauth_task(self):
        """별도 스레드에서 OAuth 콘솔 프로세스를 실행합니다.

        핵심 흐름:
        1) CREATE_NEW_CONSOLE로 실제 콘솔 창을 띄움 → isatty() 통과
        2) CLI가 자동으로 브라우저를 열어 OAuth 페이지를 표시
        3) 프로세스 종료 후 DB에서 토큰 존재 여부를 확인
        4) --verbose --log 로 디버그 로그를 파일에 기록 (오류 추적용)
        """
        log_file = None
        try:
            db_path = self.database_path
            if platform.system() == "Windows":
                db_path = db_path.replace("/", "\\")

            # 디버그 로그 파일 경로 (오류 추적용)
            log_dir = os.path.dirname(db_path)
            log_file = os.path.join(log_dir, "oauth_log.txt")
            if os.path.exists(log_file):
                os.remove(log_file)

            init_opts = InitDbOptions(
                backend=self.backend_var.get(),
                force=True,
                oauth_method=self.oauth_method_var.get(),
                use_system_ssl_ca=self.opt_use_system_ssl.get(),
                oauth_host=self.opt_oauth_host.get().strip() or None,
                token=self.opt_manual_token.get().strip() or None,
            )
            cmd = build_init_db_command(
                self.evernote_exe,
                db_path,
                log_file=log_file,
                options=init_opts,
            )
            self._queue_log(f"🔧 실행: {' '.join(cmd)}")

            # 실제 콘솔 창을 띄워서 isatty() 체크를 통과시킴
            if platform.system() == "Windows":
                process = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                process = subprocess.Popen(cmd)

            self._current_process = process
            self._queue_log("📺 콘솔 창이 열렸습니다. OAuth 인증을 진행해 주세요.")
            self._queue_log("💡 브라우저가 자동으로 열립니다. 에버노트 로그인 후 '허용'을 클릭하세요.")

            self.root.after(
                0,
                lambda: self.oauth_progress_label.config(
                    text=(
                        "📺 콘솔 창이 열렸습니다.\n"
                        "1. 브라우저가 자동으로 열립니다\n"
                        "   (안 열리면 콘솔의 URL을 복사 → 아래 붙여넣기)\n"
                        "2. 에버노트에 로그인하세요\n"
                        "3. '일괄 백업 허용'을 클릭하세요\n"
                        "4. 콘솔 창이 자동으로 닫힙니다"
                    )
                ),
            )
            self.root.after(
                0,
                lambda: self._set_status(
                    "브라우저에서 에버노트 인증을 완료해 주세요", "warning"
                ),
            )

            # 프로세스가 끝날 때까지 대기
            while process.poll() is None:
                time.sleep(0.5)

            exit_code = process.poll()
            self._current_process = None

            # 로그 파일 내용을 GUI 로그에 표시 (디버깅/오류 추적용)
            if log_file and os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        for log_line in f:
                            log_line = log_line.strip()
                            if log_line:
                                self._queue_log(f"  LOG: {log_line}")
                except Exception:
                    pass

            # 프로세스 종료 후 DB에서 토큰 확인
            time.sleep(0.5)
            db_info = get_db_info(self.database_path)

            if db_info["has_token"]:
                self.root.after(0, self._on_oauth_success)
            elif exit_code == 0:
                self.root.after(
                    0,
                    lambda: self._on_oauth_fail(
                        "프로세스는 완료되었지만 인증 토큰이 저장되지 않았습니다.\n"
                        "브라우저에서 인증을 완료했는지 확인해 주세요."
                    ),
                )
            else:
                # 로그 파일에서 오류 메시지 추출
                error_detail = ""
                if log_file and os.path.exists(log_file):
                    try:
                        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                            error_detail = f.read().strip()
                        if len(error_detail) > 300:
                            error_detail = "..." + error_detail[-300:]
                    except Exception:
                        pass

                fail_msg = f"인증 프로세스가 실패했습니다. (종료 코드: {exit_code})"
                if error_detail:
                    fail_msg += f"\n\n로그:\n{error_detail}"
                else:
                    fail_msg += "\n콘솔 창의 메시지를 확인하고 다시 시도해 주세요."

                self.root.after(
                    0,
                    lambda msg=fail_msg: self._on_oauth_fail(msg),
                )

        except Exception as e:
            self.root.after(0, lambda msg=str(e): self._on_oauth_fail(msg))
        finally:
            # 임시 로그 파일 정리
            if log_file and os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except Exception:
                    pass

    def _open_oauth_url_manual(self):
        """사용자가 수동으로 입력한 URL을 브라우저에서 엽니다."""
        url = self.oauth_url_var.get().strip()
        if not url:
            messagebox.showwarning("URL 없음", "콘솔 창에 표시된 URL을 붙여넣어 주세요.")
            return
        if not url.startswith("http"):
            messagebox.showwarning("잘못된 URL", "http:// 또는 https:// 로 시작하는 URL을 넣어 주세요.")
            return
        try:
            webbrowser.open(url)
            self._log(f"🌐 수동 URL로 브라우저를 열었습니다: {url[:60]}...")
            self.oauth_progress_label.config(
                text="✅ 브라우저가 열렸습니다.\n에버노트에서 '일괄 백업 허용'을 클릭하세요."
            )
        except Exception as e:
            self._log(f"❌ 브라우저 열기 실패: {e}")

    def _start_clipboard_monitor(self):
        """클립보드를 주기적으로 확인하여 에버노트 OAuth URL이 복사되면 자동으로 브라우저를 엽니다."""
        if not self._clipboard_monitor_active:
            return
        try:
            clip = self.root.clipboard_get()
        except Exception:
            clip = ""

        if (
            clip
            and clip != self._clipboard_last
            and re.search(
                r"(?:https?://.*(?:evernote|yinxiang).*OAuth\.action)|(?:evernote://.*)",
                clip,
                re.IGNORECASE,
            )
        ):
            self._clipboard_last = clip
            self._log(f"📋 클립보드에서 OAuth URL 감지! 브라우저를 자동으로 엽니다.")
            self.oauth_url_var.set(clip.strip())
            try:
                webbrowser.open(clip.strip())
                self.oauth_progress_label.config(
                    text="✅ 브라우저 자동 열림!\n에버노트에서 '일괄 백업 허용'을 클릭하세요."
                )
                self._set_status("브라우저에서 에버노트 인증을 완료해 주세요", "warning")
            except Exception as e:
                self._log(f"⚠️ 자동 브라우저 열기 실패: {e}")

        if self._clipboard_monitor_active:
            self.root.after(500, self._start_clipboard_monitor)

    def _stop_clipboard_monitor(self):
        """클립보드 감시를 중지합니다."""
        self._clipboard_monitor_active = False

    def _on_oauth_success(self):
        """OAuth 인증이 성공했을 때 호출됩니다."""
        self._stop_clipboard_monitor()
        self.url_helper_frame.pack_forget()
        self.is_logged_in = True
        self.btn_oauth.config(
            state=tk.NORMAL, text="✅ 인증 완료 (재인증)",
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.btn_backup.config(
            state=tk.NORMAL,
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.oauth_status_label.config(
            text="✅ OAuth 로그인 완료!", fg=self.colors["success"]
        )
        self.oauth_progress_label.config(text="")
        self._set_status("로그인 완료! 백업을 시작할 수 있습니다.", "success")
        self._log("✅ OAuth 인증이 완료되었습니다")
        self._update_db_info()

        messagebox.showinfo(
            "인증 완료",
            "OAuth 인증이 성공적으로 완료되었습니다!\n"
            "이제 '백업 시작' 버튼을 클릭하여 백업할 수 있습니다.",
        )

    def _on_oauth_fail(self, msg):
        """OAuth 인증이 실패했을 때 호출됩니다."""
        self._stop_clipboard_monitor()
        self.url_helper_frame.pack_forget()
        self.btn_oauth.config(
            state=tk.NORMAL, text="🔐 OAuth 인증 시작",
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.oauth_progress_label.config(text="")
        self._set_status("인증 실패", "error")
        self._log(f"❌ OAuth 인증 실패: {msg}")

        messagebox.showerror(
            "인증 실패", f"OAuth 인증에 실패했습니다.\n\n{msg}\n\n다시 시도해 주세요."
        )

    # =========================================================================
    # 백업 실행 (취소 기능 포함)
    # =========================================================================

    def _start_backup(self):
        """백업을 시작합니다."""
        if not self.evernote_exe:
            messagebox.showerror(
                "오류",
                "evernote-backup.exe 파일을 찾을 수 없습니다.\n"
                "이 GUI와 같은 폴더에 배치해 주세요.",
            )
            return

        if not self.is_logged_in:
            messagebox.showwarning("경고", "먼저 OAuth 로그인을 완료해 주세요.")
            return

        if self.is_working:
            messagebox.showwarning("진행 중", "이미 백업이 진행 중입니다.")
            return

        if not messagebox.askyesno(
            "백업 시작",
            "백업을 시작하시겠습니까?\n\n"
            "노트가 많으면 시간이 오래 걸릴 수 있습니다.",
        ):
            return

        try:
            os.makedirs(self.output_path.get(), exist_ok=True)
        except Exception as e:
            messagebox.showerror("폴더 오류", f"출력 폴더 생성 실패:\n{str(e)}")
            return

        # 상태 초기화
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        self._cancel_requested = False
        self.sync_start_time = time.time()

        threading.Thread(target=self._backup_task, daemon=True).start()

    def _cancel_backup(self):
        """진행 중인 백업을 안전하게 중지합니다."""
        if not self.is_working:
            return

        if not messagebox.askyesno(
            "백업 중지",
            "정말 백업을 중지하시겠습니까?\n\n"
            "이미 동기화된 데이터는 보존됩니다.",
        ):
            return

        self._cancel_requested = True
        self._log("⏹ 백업 중지를 요청했습니다. 현재 작업이 끝나면 중지됩니다...")
        self._set_status("중지 요청됨... 잠시만 기다려 주세요.", "warning")

        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def _backup_task(self):
        """실제 백업 작업(동기화 → 내보내기)을 수행하는 스레드입니다."""
        try:
            self.is_working = True
            self.root.after(0, self._backup_ui_start)

            self._queue_log("🚀 백업을 시작합니다...")
            self._queue_log(f"📍 DB: {self.database_path}")
            self._queue_log(f"📁 출력: {self.output_path.get()}")

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            # ── 1단계: 동기화 (Sync) ──
            self._run_sync_phase(env, startupinfo)

            if self._cancel_requested:
                raise InterruptedError("사용자가 백업을 중지했습니다.")

            # ── 2단계: 내보내기 (Export) ──
            self._run_export_phase(env, startupinfo)

            if self._cancel_requested:
                raise InterruptedError("사용자가 백업을 중지했습니다.")

            # ── 완료 ──
            elapsed = format_elapsed(time.time() - self.sync_start_time)
            self._queue_log(f"✅ 백업이 완료되었습니다! (소요 시간: {elapsed})")
            self.root.after(0, lambda e=elapsed: self._backup_ui_success(e))

        except InterruptedError:
            self._queue_log("⏹ 백업이 사용자에 의해 중지되었습니다.")
            self.root.after(
                0, lambda: self._set_status("백업이 중지되었습니다.", "warning")
            )
        except Exception as e:
            self._queue_log(f"❌ 백업 오류: {str(e)}")
            self.root.after(0, lambda msg=str(e): self._backup_ui_error(msg))
        finally:
            self._current_process = None
            self.root.after(0, self._backup_ui_finish)

    def _run_sync_phase(self, env, startupinfo):
        """동기화 단계를 실행합니다."""
        self.sync_phase = "동기화"
        self.root.after(
            0, lambda: self._set_status("에버노트 서버와 동기화 중...", "warning")
        )
        self.root.after(0, lambda: self._set_progress_detail("서버에 연결 중..."))

        sync_opts = SyncOptions(
            use_system_ssl_ca=self.opt_use_system_ssl.get(),
            token=self.opt_manual_token.get().strip() or None,
        )
        cmd = build_sync_command(self.evernote_exe, self.database_path, sync_opts)
        self._queue_log(f"🔧 Sync: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
            universal_newlines=True,
            startupinfo=startupinfo,
        )
        self._current_process = proc
        assert proc.stdout is not None

        failed_notes = []

        while True:
            if self._cancel_requested:
                proc.terminate()
                break

            line = proc.stdout.readline()
            if line == "" and proc.poll() is not None:
                break
            if not line:
                continue

            line = line.strip()
            if not line:
                continue

            # "N note(s) to download." 패턴으로 총 노트 수 파싱
            match_to_dl = re.search(r"(\d+)\s*note[s(].*?to\s*download", line, re.IGNORECASE)
            if match_to_dl:
                self.total_notes = int(match_to_dl.group(1))
                self.root.after(0, self._update_progress)

            # "Downloading N note(s)..." 패턴 - DB 모니터링 시작
            match_downloading = re.search(r"Downloading\s+(\d+)\s*note", line, re.IGNORECASE)
            if match_downloading:
                n = int(match_downloading.group(1))
                self.total_notes = n
                self.root.after(0, self._update_progress)
                self.root.after(0, self._start_db_monitor)

            # 다운로드 완료 감지 (Synchronization completed 메시지)
            if "Synchronization completed" in line or "up to date" in line.lower():
                self.root.after(0, self._stop_indeterminate_progress)
                self.root.after(0, self._stop_db_monitor)

            # 무시 가능한 에러
            if self._is_ignorable_error(line):
                self._queue_log(f"⚠️ 건너뜀: {line}")
                failed_notes.append(line)
            # Rate Limit 감지
            elif "rate limit" in line.lower() or "throttle" in line.lower():
                self._queue_log("⏳ Rate Limit 감지 — 자동 대기 중...")
                self.root.after(
                    0,
                    lambda: self._set_status("Rate Limit — 자동 재시도 중...", "warning"),
                )
            else:
                self._queue_log(f"SYNC: {line}")
                self.root.after(
                    0,
                    lambda l=line: self._set_progress_detail(
                        f"동기화: {l[:60]}"
                    ),
                )

        self._current_process = None
        self.root.after(0, self._stop_indeterminate_progress)
        self.root.after(0, self._stop_db_monitor)

        if failed_notes:
            self._queue_log(f"⚠️ 동기화 중 건너뛴 노트: {len(failed_notes)}개")

    def _run_export_phase(self, env, startupinfo):
        """내보내기 단계를 실행합니다."""
        self.sync_phase = "내보내기"
        self.current_note = 0
        export_count = 0

        self.root.after(
            0, lambda: self._set_status("ENEX 파일로 내보내는 중...", "warning")
        )
        self.root.after(0, lambda: self._set_progress_detail("내보내기 준비 중..."))

        export_opts = ExportOptions(
            single_notes=self.opt_single_notes.get(),
            overwrite=self.opt_overwrite.get(),
            add_metadata=self.opt_add_metadata.get(),
            no_export_date=self.opt_no_export_date.get(),
            include_trash=self.opt_include_trash.get(),
            notebook=self.opt_notebook_filter.get().strip() or None,
            tag=self.opt_tag_filter.get().strip() or None,
        )
        cmd = build_export_command(
            self.evernote_exe,
            self.database_path,
            self.output_path.get(),
            export_opts,
        )
        self._queue_log(f"🔧 Export: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
            universal_newlines=True,
            startupinfo=startupinfo,
        )
        self._current_process = proc
        assert proc.stdout is not None

        while True:
            if self._cancel_requested:
                proc.terminate()
                break

            line = proc.stdout.readline()
            if line == "" and proc.poll() is not None:
                break
            if not line:
                continue

            line = line.strip()
            if not line:
                continue

            self._queue_log(f"EXPORT: {line}")

            if any(
                kw in line.lower()
                for kw in ["export", "writing", "notebook", "note"]
            ):
                export_count += 1
                self.current_note = export_count
                self.root.after(0, self._update_progress)
                self.root.after(
                    0,
                    lambda l=line: self._set_progress_detail(
                        f"내보내기: {l[:60]}"
                    ),
                )

        self._current_process = None

        if proc.returncode and proc.returncode != 0 and not self._cancel_requested:
            raise Exception(f"내보내기 실패 (종료 코드: {proc.returncode})")

    def _is_ignorable_error(self, line):
        """무시 가능한 오류인지 확인합니다."""
        lower = line.lower()
        return any(p in lower for p in self.IGNORABLE_PATTERNS)

    # =========================================================================
    # UI 상태 업데이트
    # =========================================================================

    def _backup_ui_start(self):
        """백업 시작 시 UI 상태를 전환합니다."""
        self.btn_backup.config(
            state=tk.DISABLED, text="⏳ 백업 중...",
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.btn_cancel.config(
            state=tk.NORMAL,
            bg=self.colors["cancel"], fg=self.colors["btn_text"],
        )
        self.btn_oauth.config(
            state=tk.DISABLED,
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.progress["value"] = 0

    def _backup_ui_success(self, elapsed_str):
        """백업 성공 시 결과를 표시하고 폴더 열기를 제안합니다."""
        self._set_status(f"백업 완료! (소요 시간: {elapsed_str})", "success")
        self.progress_detail_label.config(text="")
        self._update_db_info()

        if messagebox.askyesno(
            "백업 완료",
            f"백업이 성공적으로 완료되었습니다!\n"
            f"소요 시간: {elapsed_str}\n\n"
            f"내보내기 폴더를 열어볼까요?",
        ):
            self._open_export_folder()

    def _backup_ui_error(self, msg):
        """백업 오류 시 안내를 표시합니다."""
        self._set_status("백업 중 오류 발생", "error")
        messagebox.showerror(
            "백업 오류",
            f"백업 중 오류가 발생했습니다:\n\n{msg}\n\n"
            f"로그를 확인해 주세요.",
        )

    def _backup_ui_finish(self):
        """백업 종료 후 UI를 복원합니다."""
        self.progress["value"] = 0
        self.is_working = False
        self._cancel_requested = False
        self.btn_backup.config(
            state=tk.NORMAL if self.is_logged_in else tk.DISABLED,
            text="🚀 백업 시작",
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self.btn_cancel.config(
            state=tk.DISABLED,
            bg=self.colors["cancel"], fg=self.colors["btn_text"],
        )
        self.btn_oauth.config(
            state=tk.NORMAL,
            bg=self.colors["btn_green"], fg=self.colors["btn_text"],
        )
        self._set_progress_detail("")
        self.progress_numbers_label.config(text="")

    def _update_progress(self):
        """진행률 바와 숫자 표시를 업데이트합니다."""
        if self.progress["mode"] == "determinate" and self.total_notes > 0:
            pct = min((self.current_note / self.total_notes) * 100, 100)
            self.progress["value"] = pct

        elapsed = ""
        if self.sync_start_time:
            elapsed = format_elapsed(time.time() - self.sync_start_time)

        phase = "동기화" if self.sync_phase == "동기화" else "내보내기"
        count_text = f"{phase}: {self.current_note}"
        if self.total_notes > 0:
            count_text += f"/{self.total_notes:,}"
        if elapsed:
            count_text += f" | 경과: {elapsed}"

        self.progress_numbers_label.config(text=count_text)

    def _start_indeterminate_progress(self):
        """다운로드 중 비결정 모드(애니메이션)로 전환합니다."""
        self.progress.stop()
        self.progress.config(mode="indeterminate")
        self.progress.start(40)

    def _stop_indeterminate_progress(self):
        """비결정 모드를 해제하고 결정 모드로 복귀합니다."""
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 0

    def _start_db_monitor(self):
        """동기화 중 DB 노트 수·파일 크기를 2초마다 폴링하여 실시간 진행 상황을 표시합니다."""
        self._db_monitor_active = True
        self._db_monitor_initial_notes = self._query_db_note_count()
        self._poll_db_progress()

    def _stop_db_monitor(self):
        """DB 폴링을 중지합니다."""
        self._db_monitor_active = False

    def _query_db_note_count(self) -> int:
        """DB에서 현재 노트 수를 읽어옵니다. 잠금 상태면 0을 반환합니다."""
        try:
            conn = sqlite3.connect(self.database_path, timeout=0.5)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM notes")
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _query_db_file_size_str(self) -> str:
        """DB 파일 크기를 사람이 읽기 쉬운 문자열로 반환합니다."""
        try:
            size = os.path.getsize(self.database_path)
            if size >= 1024 ** 3:
                return f"{size / 1024**3:.2f} GB"
            elif size >= 1024 ** 2:
                return f"{size / 1024**2:.1f} MB"
            else:
                return f"{size / 1024:.0f} KB"
        except Exception:
            return "?"

    def _poll_db_progress(self):
        """2초마다 DB를 폴링하여 노트 다운로드 수와 파일 크기를 진행률 패널에 표시합니다."""
        if not self._db_monitor_active:
            return

        current = self._query_db_note_count()
        file_size = self._query_db_file_size_str()
        downloaded = max(0, current - self._db_monitor_initial_notes)
        elapsed = format_elapsed(time.time() - self.sync_start_time) if self.sync_start_time else ""

        if self.total_notes > 0:
            pct = min(downloaded / self.total_notes * 100, 100)
            self.progress["value"] = pct
            self.progress_detail_label.config(
                text=f"🔽 {downloaded:,} / {self.total_notes:,}개 ({pct:.0f}%) | 파일: {file_size}"
            )
        else:
            self.progress_detail_label.config(
                text=f"🔽 다운로드 중... | 파일: {file_size}"
            )

        count_text = f"노트: {current:,}개 (DB 전체) | {elapsed}"
        self.progress_numbers_label.config(text=count_text)

        self.root.after(2000, self._poll_db_progress)

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def _browse_output(self):
        """출력 폴더 선택 다이얼로그를 엽니다."""
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)

    def _change_db_path(self):
        """DB 경로를 변경합니다."""
        new_path = filedialog.asksaveasfilename(
            title="데이터베이스 파일 위치 선택",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.database_path),
            initialfile="evernote_backup.db",
        )
        if new_path:
            is_valid, err = test_database_path(new_path)
            if is_valid:
                self._close_db_connection()
                self.database_path = new_path
                self.db_path_var.set(new_path)
                self._validate_and_init_database()
                self._log(f"💾 DB 경로 변경: {new_path}")
            else:
                messagebox.showerror(
                    "경로 오류", f"선택한 경로를 사용할 수 없습니다:\n{err}"
                )

    def _validate_and_init_database(self):
        """DB 유효성 검사 및 상태 표시를 업데이트합니다."""
        try:
            is_valid, err = test_database_path(self.database_path)
            if not is_valid:
                self.db_status_label.config(
                    text=f"❌ DB 오류: {err}", fg=self.colors["error"]
                )
                self._log(f"❌ DB 오류: {err}")

                temp_path = os.path.join(tempfile.gettempdir(), "evernote_backup.db")
                is_temp_valid, _ = test_database_path(temp_path)
                if is_temp_valid:
                    self.database_path = temp_path
                    self.db_path_var.set(temp_path)
                    self._log(f"📍 임시 경로 사용: {temp_path}")
                else:
                    messagebox.showerror(
                        "DB 오류",
                        "사용 가능한 DB 경로를 찾을 수 없습니다.\n"
                        "관리자 권한으로 실행해 보세요.",
                    )
                    return

            self.db_status_label.config(
                text="✅ DB 경로 정상", fg=self.colors["success"]
            )
            self._update_db_info()

        except Exception as e:
            self.db_status_label.config(
                text=f"❌ DB 오류: {str(e)}", fg=self.colors["error"]
            )
            self._log(f"❌ DB 초기화 오류: {str(e)}")

    def _update_db_info(self):
        """DB 상세 정보를 읽어서 UI에 표시합니다.

        기존 DB에 토큰이 있으면 자동으로 로그인 상태로 전환하여,
        프로그램을 재시작해도 바로 백업을 시작할 수 있습니다.
        """
        info = get_db_info(self.database_path)

        if info["exists"] and (info["notes"] > 0 or info["notebooks"] > 0):
            text = f"📊 노트: {info['notes']}개 | 노트북: {info['notebooks']}개"
            if info["backend"]:
                text += f" | 서버: {info['backend']}"
            self.db_info_label.config(text=text)

            if info["has_token"]:
                self.is_logged_in = True
                self.btn_backup.config(
                    state=tk.NORMAL,
                    bg=self.colors["btn_green"], fg=self.colors["btn_text"],
                )
                self.btn_oauth.config(
                    text="✅ 인증 완료 (재인증)",
                    bg=self.colors["btn_green"], fg=self.colors["btn_text"],
                )
                self.oauth_status_label.config(
                    text="✅ 기존 인증 토큰 감지됨", fg=self.colors["success"]
                )
                self._log("🔑 기존 인증 토큰이 유효합니다. 바로 백업 가능합니다.")
        elif info["exists"]:
            self.db_info_label.config(text="📊 빈 데이터베이스")
        else:
            self.db_info_label.config(text="📊 새 데이터베이스")

    def _close_db_connection(self):
        """DB 연결을 안전하게 닫습니다."""
        if self._db_connection:
            try:
                self._db_connection.close()
            except Exception:
                pass
            self._db_connection = None

    def _open_export_folder(self):
        """내보내기 폴더를 시스템 탐색기에서 엽니다."""
        folder = self.output_path.get()
        if os.path.exists(folder):
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    # =========================================================================
    # 로그 관리
    # =========================================================================

    def _check_log_queue(self):
        """로그 큐에 쌓인 메시지를 UI에 반영합니다 (100ms 주기)."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._check_log_queue)

    def _queue_log(self, msg):
        """백그라운드 스레드에서 로그를 안전하게 큐에 추가합니다."""
        self.log_queue.put(msg)

    def _log(self, msg):
        """로그 위젯에 타임스탬프와 함께 메시지를 출력합니다."""
        self.text_log.config(state=tk.NORMAL)
        self.text_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)

    def _save_log(self):
        """로그 내용을 파일로 저장합니다."""
        filepath = filedialog.asksaveasfilename(
            title="로그 파일 저장",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log")],
            initialfile=f"evernote_backup_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if filepath:
            try:
                self.text_log.config(state=tk.NORMAL)
                content = self.text_log.get("1.0", tk.END)
                self.text_log.config(state=tk.DISABLED)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                self._log(f"💾 로그 저장 완료: {filepath}")
                messagebox.showinfo("저장 완료", f"로그가 저장되었습니다:\n{filepath}")
            except Exception as e:
                messagebox.showerror("저장 실패", f"로그 저장 실패:\n{str(e)}")

    def _clear_log(self):
        """로그를 초기화합니다."""
        self.text_log.config(state=tk.NORMAL)
        self.text_log.delete("1.0", tk.END)
        self.text_log.config(state=tk.DISABLED)
        self._log("🗑️ 로그가 초기화되었습니다")

    def _set_status(self, msg, level="info"):
        """상태 바 메시지를 설정합니다."""
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        colors = {
            "info": self.colors["text"],
            "success": self.colors["success"],
            "warning": self.colors["warning"],
            "error": self.colors["error"],
        }
        self.status_label.config(
            text=f"{icons.get(level, 'ℹ️')} {msg}",
            fg=colors.get(level, self.colors["text"]),
        )

    def _set_progress_detail(self, msg):
        """진행률 상세 텍스트를 설정합니다."""
        self.progress_detail_label.config(text=msg)

    # =========================================================================
    # 정보 다이얼로그
    # =========================================================================

    def _show_usage(self):
        """사용법 다이얼로그를 표시합니다."""
        dialog = tk.Toplevel(self.root)
        dialog.title("📋 사용법")
        dialog.geometry("650x550")
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = tk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("맑은 고딕", 10), bg="#f8f9fa", fg="#333333"
        )
        text.pack(fill=tk.BOTH, expand=True)

        text.insert(
            tk.END,
            f"""📋 에버노트 백업 도구 사용법

이 프로그램은 evernote-backup {self.VERSION}의 GUI 버전입니다.

🔧 필수 요구사항:
• evernote-backup.exe 파일이 이 GUI와 같은 폴더에 있어야 합니다
• 다운로드: https://github.com/vzhd1701/evernote-backup/releases

📝 사용 단계:

1️⃣ OAuth 인증
   • 'OAuth 인증 시작' 버튼을 클릭합니다
   • 검은색 콘솔 창이 열리고, 브라우저가 자동으로 열립니다
   • 만약 브라우저가 안 열리면:
     ─ 콘솔 창에서 URL(http://...)을 마우스로 드래그합니다
     ─ 마우스 우클릭 또는 Enter 키로 복사합니다
     ─ GUI의 URL 입력란에 붙여넣고 '열기' 버튼을 클릭합니다
     ─ 또는 복사만 하면 GUI가 자동으로 감지하여 브라우저를 엽니다
   • 에버노트에 로그인하고 '일괄 백업 허용' 버튼을 클릭합니다
   • 콘솔 창이 자동으로 닫히고 GUI에서 완료를 알려줍니다

2️⃣ 백업 실행
   • 백업할 폴더를 선택합니다
   • '백업 시작' 버튼을 클릭합니다
   • 완료될 때까지 기다립니다
   • 중간에 '중지' 버튼으로 안전하게 멈출 수 있습니다

⚙️ 기타 기능:
• 로그 저장: 작업 로그를 파일로 저장할 수 있습니다
• DB 변경: 데이터베이스 저장 위치를 변경할 수 있습니다
• 재인증: 토큰이 만료되면 다시 인증할 수 있습니다

⚠️ 참고사항:
• Rate Limit이 발생하면 자동으로 대기 후 재시도합니다
• 첫 백업은 노트 수에 따라 시간이 오래 걸릴 수 있습니다
• 네트워크 연결이 안정적이어야 합니다
• ENEX 형식으로 내보내기됩니다 (Notion, Obsidian 등에서 사용 가능)

💻 시스템 요구사항:
• Windows 10/11 (64비트)
• 안정적인 인터넷 연결

📅 {self.BUILD_DATE} — MIT License""",
        )
        text.config(state=tk.DISABLED)

        tk.Button(
            dialog,
            text="닫기",
            command=dialog.destroy,
            font=("맑은 고딕", 11),
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=30,
            pady=8,
        ).pack(pady=(10, 20))

    def _show_about(self):
        """프로젝트 정보 다이얼로그를 표시합니다."""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔗 정보")
        dialog.geometry("550x400")
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = tk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("맑은 고딕", 10), bg="#f8f9fa", fg="#333333"
        )
        text.pack(fill=tk.BOTH, expand=True)

        text.insert(
            tk.END,
            f"""🔗 evernote-backup 정보

📚 원저작자: vzhd1701
📄 라이선스: MIT License

🔧 이 GUI는 evernote-backup CLI 도구를 래핑한 버전입니다.

🎯 주요 기능:
• OAuth 2.0 인증 지원
• 안정적인 노트 동기화
• 완전한 백업 및 복원
• ENEX 형식 내보내기 지원
• Rate Limit 자동 처리

🖥️ GUI 특징:
• 원클릭 OAuth 인증 (자동 URL 캡처)
• 실시간 진행상황 표시
• 백업 중지 가능
• 로그 저장 기능
• 완료 후 폴더 바로 열기
• 기존 인증 토큰 자동 감지

🌐 GitHub: https://github.com/vzhd1701/evernote-backup

📅 GUI {self.BUILD_DATE} | 엔진 {self.VERSION}""",
        )
        text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=(10, 20))

        tk.Button(
            btn_frame,
            text="🔗 GitHub 방문",
            command=lambda: webbrowser.open(
                "https://github.com/vzhd1701/evernote-backup"
            ),
            font=("맑은 고딕", 11),
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=20,
            pady=8,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="닫기",
            command=dialog.destroy,
            font=("맑은 고딕", 11),
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_text"],
            padx=30,
            pady=8,
        ).pack(side=tk.LEFT)


# =============================================================================
# 메인 실행
# =============================================================================


def main():
    root = tk.Tk()
    app = EvernoteBackupApp(root)

    def on_close():
        if app.is_working:
            if messagebox.askokcancel(
                "종료 확인", "백업이 진행 중입니다. 정말 종료하시겠습니까?"
            ):
                if app._current_process:
                    try:
                        app._current_process.terminate()
                    except Exception:
                        pass
                app._close_db_connection()
                root.destroy()
        else:
            app._close_db_connection()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
