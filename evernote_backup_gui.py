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

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

# --------- Cross-PC safe paths (원본과 완전히 동일) ---------
def get_safe_db_path():
    if platform.system() == "Windows":
        candidates = [
            r"C:\EvernoteDB\evernote_backup.db",
            r"C:\temp\evernote_backup.db",
            os.path.join(os.environ.get('TEMP', ''), "evernote_backup.db"),
            r"C:\Users\Public\evernote_backup.db"
        ]
    else:
        candidates = [
            os.path.expanduser("~/evernote_backup.db"),
            "/tmp/evernote_backup.db",
            os.path.join(tempfile.gettempdir(), "evernote_backup.db")
        ]

    for db_path in candidates:
        if is_path_safe_for_sqlite(db_path):
            try:
                parent_dir = os.path.dirname(db_path)
                os.makedirs(parent_dir, exist_ok=True)
                return db_path
            except Exception:
                continue

    raise Exception("사용 가능한 안전한 데이터베이스 경로를 찾을 수 없습니다.\n관리자 권한으로 실행하거나 C 드라이브에 쓰기 권한을 확인해주세요.")

def is_path_safe_for_sqlite(db_path):
    try:
        db_path.encode('ascii')
        if platform.system() == "Windows" and len(db_path) > 260:
            return False

        path_parts = os.path.normpath(db_path).split(os.sep)
        for part in path_parts:
            if part and part[0].isdigit():
                return False

        parent_dir = os.path.dirname(db_path)
        if os.path.exists(parent_dir):
            if not os.access(parent_dir, os.W_OK):
                return False

        return True
    except (UnicodeEncodeError, OSError):
        return False

def get_db_base_dir():
    db_path = get_safe_db_path()
    return os.path.dirname(db_path)

def get_database_path():
    try:
        return get_safe_db_path()
    except Exception:
        fallback_path = os.path.join(tempfile.gettempdir(), f"evernote_backup_{os.getpid()}.db")
        return fallback_path

def get_export_dir():
    base = get_db_base_dir()
    out = os.path.join(base, "Export")
    os.makedirs(out, exist_ok=True)
    return out

def test_database_path(db_path):
    try:
        parent_dir = os.path.dirname(db_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        if not os.access(parent_dir, os.W_OK):
            return False, f"디렉토리 쓰기 권한 없음: {parent_dir}"
        return True, "OK"
    except Exception as e:
        return False, str(e)

# --------- EXE 파일 찾기 (강화된 버전) ---------
def find_evernote_exe():
    """evernote-backup.exe 파일을 안정적으로 찾기"""
    possible_locations = [
        "evernote-backup.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "evernote-backup.exe"),
        os.path.join(os.path.dirname(sys.executable), "evernote-backup.exe"),
        shutil.which("evernote-backup.exe") or "",
        shutil.which("evernote-backup") or "",
    ]

    for path in possible_locations:
        if path and os.path.isfile(path):
            try:
                # 실행 가능한지 테스트
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 or "evernote" in str(result.stdout).lower():
                    return os.path.abspath(path)
            except:
                continue

    return None

# --------------------------------------

class EvernoteBackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("에버노트 백업 도구 (GUI for evernote-backup v1.13.1)")
        self.root.geometry("900x750")
        self.root.minsize(750, 650)

        # 원본과 완전히 동일한 변수들
        self.is_working = False
        self.is_logged_in = False
        self.database_path = get_database_path()
        self.export_dir = get_export_dir()
        self.oauth_url = None
        self.oauth_process = None
        self._db_connection = None

        # EXE 관련 (새로 추가)
        self.evernote_exe = None

        # 원본과 동일한 진행률 추적 변수들
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"

        # Rate Limit 처리용 (원본과 동일)
        self.rate_limit_timer = None

        # 실시간 로그를 위한 큐 (원본과 동일)
        self.log_queue = queue.Queue()

        self.setup_variables()
        self.setup_styles()
        self.setup_fonts()
        self.create_widgets()
        self.validate_and_init_database()

        # EXE 파일 검증 (새로 추가)
        self.check_evernote_exe()

        # 주기적으로 로그 큐 확인 (원본과 동일)
        self.check_log_queue()

        self.log_message("🚀 에버노트 백업 도구 시작 (GUI for evernote-backup v1.13.1)")
        self.log_message(f"🖥️ OS: {platform.system()}")
        self.log_message(f"💾 DB 경로: {self.database_path}")
        self.log_message(f"📁 내보내기 폴더: {self.export_dir}")

    def check_evernote_exe(self):
        """EXE 파일 검증 (새로 추가)"""
        self.evernote_exe = find_evernote_exe()

        if self.evernote_exe:
            self.log_message(f"✅ evernote-backup.exe 발견: {self.evernote_exe}")
            try:
                # 버전 정보 확인
                result = subprocess.run([self.evernote_exe, "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.stdout:
                    version = result.stdout.strip()
                    self.log_message(f"📌 버전: {version}")
            except:
                pass
        else:
            self.log_message("❌ evernote-backup.exe 파일을 찾을 수 없습니다")
            self.log_message("📥 GitHub에서 다운로드: https://github.com/vzhd1701/evernote-backup/releases")

            answer = messagebox.askyesno("필수 파일 누락", 
                "evernote-backup.exe 파일이 필요합니다.\n\n" +
                "이 GUI와 같은 폴더에 배치해야 합니다.\n\n" +
                "GitHub 다운로드 페이지를 열까요?")
            if answer:
                webbrowser.open("https://github.com/vzhd1701/evernote-backup/releases")

    def setup_variables(self):
        # 원본과 완전히 동일
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar(value=self.export_dir)

    def setup_styles(self):
        # 원본과 완전히 동일한 색상 시스템
        self.colors = {
            'evernote_green': '#00A82D',
            'background': '#F8F9FA',
            'text': '#333333',
            'light_text': '#666666',
            'success': '#00A82D',
            'warning': '#FF6F00',
            'error': '#D32F2F',
            'primary': '#1976D2',
            'button_bg': '#4A90E2',  # 모든 버튼 통일
            'button_text': 'white',
            'button_disabled': '#CCCCCC',
            'border': '#CCCCCC'
        }

    def setup_fonts(self):
        # 원본과 완전히 동일한 폰트 시스템
        self.fonts = {
            'title': ('맑은 고딕', 20, 'bold'),
            'subtitle': ('맑은 고딕', 10),
            'section_title': ('맑은 고딕', 11, 'bold'),
            'button_large': ('맑은 고딕', 12, 'bold'),
            'button_medium': ('맑은 고딕', 10, 'bold'),
            'button_small': ('맑은 고딕', 9),
            'label': ('맑은 고딕', 9, 'bold'),
            'text': ('맑은 고딕', 8),
            'small_text': ('맑은 고딕', 8),
            'status': ('맑은 고딕', 9, 'bold'),
            'log': ('맑은 고딕', 8)
        }

    def create_widgets(self):
        # 원본과 완전히 동일한 2컬럼 레이아웃
        container = tk.Frame(self.root, bg=self.colors['background'])
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Header (원본과 완전히 동일)
        header = tk.Frame(container, bg=self.colors['background'])
        header.pack(fill=tk.X, pady=(0, 15))

        title_label = tk.Label(header, text="📋 에버노트 백업 도구", 
                              font=self.fonts['title'], 
                              fg=self.colors['evernote_green'], 
                              bg=self.colors['background'])
        title_label.pack()

        subtitle_label = tk.Label(header, text="GUI for evernote-backup v1.13.1", 
                                 font=self.fonts['subtitle'], 
                                 fg=self.colors['text'], 
                                 bg=self.colors['background'])
        subtitle_label.pack()

        # Info buttons (원본과 완전히 동일)
        info_frame = tk.Frame(container, bg=self.colors['background'])
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_buttons = tk.Frame(info_frame, bg=self.colors['background'])
        info_buttons.pack()

        tk.Button(info_buttons, text="📋 사용법", 
                 command=self.show_program_info,
                 font=self.fonts['button_small'], 
                 bg=self.colors['button_bg'], 
                 fg=self.colors['button_text'],
                 padx=12, pady=3).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(info_buttons, text="🔗 정보", 
                 command=self.show_source_info,
                 font=self.fonts['button_small'], 
                 bg=self.colors['button_bg'], 
                 fg=self.colors['button_text'],
                 padx=12, pady=3).pack(side=tk.LEFT)

        # Main content area - 원본의 정확한 2컬럼 레이아웃
        main_frame = tk.Frame(container, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column - 설정 패널들 (원본과 완전히 동일)
        left_column = tk.Frame(main_frame, bg=self.colors['background'])
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Right column - 로그 (원본과 완전히 동일)
        right_column = tk.Frame(main_frame, bg=self.colors['background'])
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # DB 설정 섹션 (원본과 완전히 동일)
        db_frame = tk.LabelFrame(left_column, text="💾 DB 설정", 
                                font=self.fonts['section_title'], 
                                fg=self.colors['evernote_green'], 
                                padx=10, pady=8)
        db_frame.pack(fill=tk.X, pady=(0, 10))

        self.db_status = tk.Label(db_frame, text="🔍 확인 중...", 
                                 font=self.fonts['small_text'])
        self.db_status.pack(anchor=tk.W, pady=(0, 3))

        tk.Label(db_frame, text="경로:", 
                font=self.fonts['label']).pack(anchor=tk.W)

        db_path_frame = tk.Frame(db_frame)
        db_path_frame.pack(fill=tk.X, pady=2)

        self.db_path_var = tk.StringVar(value=self.database_path)
        self.entry_db_path = tk.Entry(db_path_frame, textvariable=self.db_path_var, 
                                     font=self.fonts['text'], state="readonly", width=35)
        self.entry_db_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(db_path_frame, text="변경", 
                 command=self.change_db_path,
                 font=self.fonts['button_small'], 
                 bg=self.colors['button_bg'], 
                 fg=self.colors['button_text'],
                 padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # OAuth 로그인 섹션 (원본과 완전히 동일 - 2x2 그리드)
        oauth_frame = tk.LabelFrame(left_column, text="🔐 OAuth 로그인", 
                                   font=self.fonts['section_title'], 
                                   fg=self.colors['evernote_green'], 
                                   padx=10, pady=10)
        oauth_frame.pack(fill=tk.X, pady=(0, 10))

        self.oauth_status = tk.Label(oauth_frame, text="🔑 로그인 필요", 
                                    font=self.fonts['small_text'], 
                                    fg=self.colors['warning'])
        self.oauth_status.pack(anchor=tk.W, pady=(0, 8))

        # OAuth 버튼들 - 원본과 완전히 동일한 2x2 그리드
        oauth_grid = tk.Frame(oauth_frame, bg=self.colors['background'])
        oauth_grid.pack(fill=tk.X)

        # 첫 번째 행
        row1 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row1.pack(fill=tk.X, pady=2)

        self.btn_terminal = tk.Button(row1, text="1️⃣ 터미널 열기", 
                                     font=self.fonts['button_small'], 
                                     bg=self.colors['button_bg'], 
                                     fg=self.colors['button_text'],
                                     command=self.start_oauth_terminal,
                                     padx=8, pady=4, width=12)
        self.btn_terminal.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_copy = tk.Button(row1, text="2️⃣ URL 복사", 
                                 font=self.fonts['button_small'], 
                                 bg=self.colors['button_bg'], 
                                 fg=self.colors['button_text'],
                                 command=self.copy_oauth_url,
                                 state="disabled", padx=8, pady=4, width=12)
        self.btn_copy.pack(side=tk.LEFT)

        # 두 번째 행
        row2 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row2.pack(fill=tk.X, pady=2)

        self.btn_browser = tk.Button(row2, text="3️⃣ 브라우저 열기", 
                                    font=self.fonts['button_small'], 
                                    bg=self.colors['button_bg'], 
                                    fg=self.colors['button_text'],
                                    command=self.open_browser,
                                    state="disabled", padx=8, pady=4, width=12)
        self.btn_browser.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_complete = tk.Button(row2, text="4️⃣ 로그인 완료", 
                                     font=self.fonts['button_small'], 
                                     bg=self.colors['button_bg'], 
                                     fg=self.colors['button_text'],
                                     command=self.check_oauth_token,
                                     state="disabled", padx=8, pady=4, width=12)
        self.btn_complete.pack(side=tk.LEFT)

        # 백업 설정 섹션 (원본과 완전히 동일)
        settings = tk.LabelFrame(left_column, text="💾 백업 설정", 
                                font=self.fonts['section_title'], 
                                fg=self.colors['evernote_green'], 
                                padx=10, pady=10)
        settings.pack(fill=tk.X, pady=(0, 10))

        tk.Label(settings, text="폴더:", 
                font=self.fonts['label']).pack(anchor=tk.W)

        folder_frame = tk.Frame(settings)
        folder_frame.pack(fill=tk.X, pady=3)

        self.entry_folder = tk.Entry(folder_frame, textvariable=self.output_path, 
                                    font=self.fonts['text'], width=35)
        self.entry_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(folder_frame, text="찾기", 
                 command=self.browse_output,
                 font=self.fonts['button_small'], 
                 bg=self.colors['button_bg'], 
                 fg=self.colors['button_text'],
                 padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # 백업 시작 버튼 (원본과 완전히 동일)
        self.btn_backup = tk.Button(settings, text="🚀 백업 시작", 
                                   font=self.fonts['button_large'], 
                                   bg=self.colors['button_bg'], 
                                   fg=self.colors['button_text'],
                                   command=self.start_backup,
                                   state="disabled", padx=20, pady=8)
        self.btn_backup.pack(pady=(10, 0))

        # 상태 표시 섹션 (원본과 완전히 동일)
        status = tk.Frame(left_column, bg=self.colors['background'])
        status.pack(fill=tk.X, pady=(10, 0))

        # 진행률 바 (원본과 완전히 동일)
        self.progress = ttk.Progressbar(status, mode="determinate")
        self.progress.pack(fill=tk.X, pady=3)
        self.progress["maximum"] = 100

        # 상태 라벨들 (원본과 완전히 동일)
        self.status_label = tk.Label(status, text="대기 중", 
                                    font=self.fonts['status'], 
                                    fg=self.colors['success'], 
                                    bg=self.colors['background'])
        self.status_label.pack(anchor=tk.W)

        self.progress_detail = tk.Label(status, text="", 
                                       font=self.fonts['small_text'], 
                                       fg=self.colors['light_text'], 
                                       bg=self.colors['background'])
        self.progress_detail.pack(anchor=tk.W)

        self.progress_numbers = tk.Label(status, text="", 
                                        font=self.fonts['small_text'], 
                                        fg=self.colors['text'], 
                                        bg=self.colors['background'])
        self.progress_numbers.pack(anchor=tk.W)

        # 로그 섹션 (원본과 완전히 동일)
        log_frame = tk.LabelFrame(right_column, text="📄 로그", 
                                 font=self.fonts['section_title'], 
                                 fg=self.colors['evernote_green'], 
                                 padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.text_log = scrolledtext.ScrolledText(
            log_frame,
            font=self.fonts['log'],
            bg="#f7f7f7",
            fg="#111",
            wrap=tk.WORD
        )
        self.text_log.pack(fill=tk.BOTH, expand=True)

    # OAuth 관련 메소드들 (exe 기반으로 수정된 버전)
    def start_oauth_terminal(self):
        if not self.evernote_exe:
            messagebox.showerror("오류", "evernote-backup.exe 파일을 찾을 수 없습니다.")
            return
            
        if self.is_working:
            messagebox.showwarning("진행 중", "이미 작업이 진행 중입니다.")
            return
        
        # DB 경로 검증
        is_valid, error_msg = test_database_path(self.database_path)
        if not is_valid:
            messagebox.showerror("DB 경로 오류", f"데이터베이스 경로에 문제가 있습니다:\n{error_msg}")
            return
        
        self.close_db_connection()
        self.log_message("🔐 OAuth 인증을 시작합니다...")
        self.set_status("OAuth URL 생성 중...", "info")
        
        try:
            # 경로 정리
            db_path = self.database_path.replace('/', '\\')
            
            # 🎯 핵심: exe 경로에 공백이 있으면 따옴표로 감싸기
            if " " in self.evernote_exe:
                exe_cmd = f'"{self.evernote_exe}"'
            else:
                exe_cmd = self.evernote_exe
            
            # --force 옵션과 함께 명령어 구성
            cmd = f'start cmd /k "{exe_cmd} init-db --force --database {db_path} --backend evernote"'
            
            self.log_message(f"🔧 실행 명령어: {cmd}")
            os.system(cmd)
            
            self.log_message("✅ 터미널창이 정상적으로 실행되었습니다. OAuth URL을 복사하세요.")
            self.btn_terminal.config(state=tk.DISABLED, text="1️⃣ 실행됨")
            self.btn_copy.config(state=tk.NORMAL)
            self.set_status("터미널이 열렸습니다. OAuth URL을 기다리세요...", "success")
            
        except Exception as e:
            self.log_message(f"❌ OAuth 터미널 오류: {str(e)}")
            messagebox.showerror("오류", f"OAuth 터미널 실행 실패:\n{str(e)}")


    def copy_oauth_url(self):
        """2단계: URL 복사 (원본과 완전히 동일)"""
        # OAuth URL 입력 다이얼로그
        dialog = tk.Toplevel(self.root)
        dialog.title("OAuth URL 입력")
        dialog.geometry("600x350")
        dialog.grab_set()
        dialog.resizable(False, False)

        # 다이얼로그 위치 설정 (원본과 동일)
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        frame = tk.Frame(dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="OAuth URL 입력", 
                font=('맑은 고딕', 14, 'bold'), 
                fg=self.colors['evernote_green']).pack(pady=(0, 10))

        tk.Label(frame, text="터미널에 나타난 OAuth URL을 복사해서 붙여넣어 주세요:", 
                font=self.fonts['text']).pack(pady=(0, 10), anchor=tk.W)

        text_url = tk.Text(frame, height=6, font=self.fonts['text'], wrap=tk.WORD)
        text_url.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_url.focus()

        # 클립보드에서 URL 자동 붙여넣기 시도 (원본과 동일)
        if HAS_CLIPBOARD:
            try:
                clip = pyperclip.paste()
                if clip and ("evernote.com" in clip and "OAuth.action" in clip):
                    text_url.insert(tk.END, clip)
                    self.log_message("📋 클립보드에서 OAuth URL을 감지했습니다")
            except:
                pass

        def on_confirm():
            url = text_url.get("1.0", "end").strip()
            if not url or ("evernote.com" not in url and "OAuth.action" not in url):
                messagebox.showerror("오류", "유효한 OAuth URL을 입력해주세요.\n'evernote.com'과 'OAuth.action'이 포함되어야 합니다.")
                return

            self.oauth_url = url
            dialog.destroy()

            # 버튼 상태 변경 (원본과 동일)
            self.btn_copy.config(state=tk.DISABLED, text="2️⃣ 완료")
            self.btn_browser.config(state=tk.NORMAL)
            self.set_status("URL이 저장되었습니다. 브라우저로 이동하세요.", "success")
            self.log_message("🔗 OAuth URL이 저장되었습니다")

        def on_cancel():
            dialog.destroy()

        # 버튼들 (원본과 동일)
        btns = tk.Frame(frame)
        btns.pack(pady=(10, 0))

        tk.Button(btns, text="확인", command=on_confirm, 
                 bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 font=('맑은 고딕', 11, 'bold'), padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btns, text="취소", command=on_cancel, 
                 font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=20, pady=8).pack(side=tk.LEFT)

    def open_browser(self):
        """3단계: 브라우저 열기 (원본과 완전히 동일)"""
        if not self.oauth_url:
            messagebox.showwarning("경고", "먼저 OAuth URL을 입력해주세요.")
            return

        try:
            webbrowser.open(self.oauth_url)

            # 버튼 상태 변경 (원본과 동일)
            self.btn_browser.config(state=tk.DISABLED, text="3️⃣ 완료")
            self.btn_complete.config(state=tk.NORMAL)
            self.set_status("4단계: 인증 후 '로그인 완료' 버튼을 클릭하세요.", "info")
            self.log_message("🌐 브라우저에서 OAuth URL을 열었습니다")

            # 사용자 안내 메시지 (원본과 동일)
            messagebox.showinfo("브라우저 열림", 
                "브라우저가 열렸습니다!\n\n" +
                "1. 에버노트에 로그인하세요\n" +
                "2. '일괄 백업 허용(Allow Bulk Backup)' 버튼을 클릭하세요\n" +
                "3. 완료되면 4번 '로그인 완료' 버튼을 클릭하세요")

        except Exception as e:
            messagebox.showerror("오류", f"브라우저 열기 실패:\n{str(e)}")

    def check_oauth_token(self):
        """4단계: 로그인 완료 (원본과 완전히 동일)"""
        try:
            if not os.path.exists(self.database_path):
                messagebox.showwarning("경고", "데이터베이스 파일이 생성되지 않았습니다. OAuth 인증을 다시 시도하세요.")
                return

            conn = sqlite3.connect(self.database_path)
            cur = conn.cursor()

            # 액세스 토큰 확인 (원본과 동일)
            cur.execute("SELECT value FROM config WHERE name='access_token'")
            access_token_row = cur.fetchone()

            if not access_token_row:
                cur.execute("SELECT value FROM config WHERE name LIKE '%token%' OR name LIKE '%oauth%'")
                token_rows = cur.fetchall()
                access_token_row = token_rows[0] if token_rows else None

            conn.close()

            if access_token_row and access_token_row[0]:
                # 로그인 성공 (원본과 동일)
                self.is_logged_in = True
                self.btn_complete.config(state=tk.DISABLED, text="4️⃣ 완료")
                self.btn_backup.config(state=tk.NORMAL)
                self.oauth_status.config(text="✅ OAuth 로그인 완료!", fg=self.colors['success'])
                self.set_status("로그인 완료! 백업을 시작할 수 있습니다.", "success")
                self.log_message("✅ OAuth 로그인이 완료되었습니다")
                messagebox.showinfo("로그인 완료", "OAuth 로그인이 성공적으로 완료되었습니다!\n이제 백업을 시작할 수 있습니다.")
            else:
                messagebox.showwarning("로그인 미완료", "아직 로그인이 완료되지 않았습니다.\n브라우저에서 인증을 완료한 후 다시 시도해주세요.")

        except Exception as e:
            self.log_message(f"❌ 로그인 확인 오류: {str(e)}")
            messagebox.showerror("오류", f"로그인 상태 확인 실패:\n{str(e)}")

    # 백업 실행 관련 메소드들 (exe 기반으로 수정)
    def start_backup(self):
        """백업 시작 (원본 로직 + exe 기반)"""
        if not self.evernote_exe:
            messagebox.showerror("오류", "evernote-backup.exe 파일을 찾을 수 없습니다.")
            return

        if not self.is_logged_in:
            messagebox.showwarning("경고", "먼저 OAuth 로그인을 완료해주세요")
            return

        if self.is_working:
            messagebox.showwarning("진행 중", "이미 백업이 진행 중입니다.")
            return

        # 사용자 확인 (원본과 동일)
        if not messagebox.askyesno("백업 시작", "백업을 시작하시겠습니까?\n시간이 오래 걸릴 수 있습니다."):
            return

        try:
            os.makedirs(self.output_path.get(), exist_ok=True)
        except Exception as e:
            messagebox.showerror("폴더 오류", f"출력 폴더 생성 실패:\n{str(e)}")
            return

        # 백업 관련 변수 초기화 (원본과 동일)
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        threading.Thread(target=self.backup_task, daemon=True).start()

    def backup_task(self):
        """실제 백업 작업 (exe 기반으로 완전히 수정)"""
        try:
            self.is_working = True
            self.root.after(0, self.backup_ui_start)

            self.queue_log("🚀 백업을 시작합니다...")
            self.queue_log(f"📍 데이터베이스: {self.database_path}")
            self.queue_log(f"📁 출력 폴더: {self.output_path.get()}")

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            # 1단계: Sync (동기화) - exe 기반
            self.sync_phase = "동기화"
            self.root.after(0, lambda: self.set_status("에버노트 서버와 동기화 중...", "warning"))
            self.root.after(0, lambda: self.set_progress_detail("동기화 진행 중..."))

            cmd_sync = [self.evernote_exe, "sync", "--database", self.database_path]

            process_sync = subprocess.Popen(cmd_sync, stdout=subprocess.PIPE, 
                                          stderr=subprocess.STDOUT, text=True, env=env, 
                                          bufsize=1, universal_newlines=True,
                                          creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)

            failed_notes = []
            rate_limit_detected = False

            while True:
                output = process_sync.stdout.readline()
                if output == '' and process_sync.poll() is not None:
                    break
                if output:
                    line = output.strip()

                    # 진행률 파싱 (원본 로직 유지)
                    if "notes to download" in line:
                        match = re.search(r'(\d+) notes to download', line)
                        if match:
                            self.total_notes = int(match.group(1))
                            self.root.after(0, lambda: self.update_progress_info())

                    if "Downloading" in line and "notes" in line:
                        self.queue_log(f"SYNC: {line}")
                        self.root.after(0, lambda l=line: self.set_progress_detail(f"동기화: {l}"))
                    elif self.is_ignorable_error(line):
                        self.queue_log(f"SYNC-SKIP: {line}")
                        failed_notes.append(self.extract_note_info(line))
                    else:
                        self.queue_log(f"SYNC: {line}")

                    # Rate Limit 처리 (원본과 동일)
                    if "rate limit" in line.lower() or "throttle" in line.lower():
                        rate_limit_detected = True
                        self.queue_log("⏳ Rate Limit 감지. 자동으로 대기 중...")
                        self.root.after(0, lambda: self.set_status("Rate Limit - 자동으로 재시도됩니다...", "success"))
                        self.root.after(0, lambda: self.progress_numbers.config(text="대기 중..."))
                        time.sleep(2)

            if failed_notes:
                self.queue_log(f"⚠️ 동기화 실패 노트: {len(failed_notes)}개")
                self.queue_log("건너뛰어진 노트들은 백업에 포함되지 않습니다")

            # 2단계: Export (내보내기) - exe 기반
            self.sync_phase = "내보내기"
            self.current_note = 0
            self.root.after(0, lambda: self.set_status("ENEX 파일로 내보내는 중...", "warning"))
            self.root.after(0, lambda: self.set_progress_detail("ENEX 내보내기 중..."))

            cmd_export = [self.evernote_exe, "export", "--database", self.database_path, 
                         "--output-dir", self.output_path.get(), "--overwrite"]

            process_export = subprocess.Popen(cmd_export, stdout=subprocess.PIPE, 
                                            stderr=subprocess.STDOUT, text=True, env=env, 
                                            bufsize=1, universal_newlines=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)

            while True:
                output = process_export.stdout.readline()
                if output == '' and process_export.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    self.queue_log(f"EXPORT: {line}")

                    # Export 진행률 파싱
                    if "export" in line.lower() or "file" in line.lower():
                        if self.total_notes > 0:
                            self.current_note = min(self.current_note + 1, self.total_notes)
                            self.root.after(0, lambda: self.update_progress_info())
                            self.root.after(0, lambda l=line: self.set_progress_detail(f"내보내기: {l}"))

            if process_export.returncode != 0:
                raise Exception(f"내보내기 실패 (종료 코드: {process_export.returncode})")

            # 완료
            self.queue_log("✅ 백업이 완료되었습니다!")
            self.root.after(0, self.backup_ui_success)

        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda msg=error_message: self.backup_ui_error(msg))
        finally:
            self.root.after(0, self.backup_ui_finish)

    def is_ignorable_error(self, line):
        """무시 가능한 오류 확인 (원본과 동일)"""
        ignorable_patterns = [
            "Failed to download note",
            "Note.will be skipped",
            "LinkedNotebook.is not accessible", 
            "RemoteServer returned system error",
            "PERMISSION_DENIED",
            "NOT_FOUND",
            "Authentication failed",
            "Shared notebook.not found",
            "Business notebook.expired"
        ]
        line_lower = line.lower()
        return any(pattern.lower() in line_lower for pattern in ignorable_patterns)

    def extract_note_info(self, line):
        """노트 정보 추출 (원본과 동일)"""
        return line

    # UI 업데이트 메소드들 (원본과 동일)
    def backup_ui_start(self):
        """백업 시작 UI 상태 (원본과 동일)"""
        self.btn_backup.config(state=tk.DISABLED, text="백업 중...")

    def backup_ui_success(self):
        """백업 성공 UI 상태 (원본과 동일)"""
        self.set_status("백업 완료!", "success")
        self.progress_detail.config(text="백업이 성공적으로 완료되었습니다")
        messagebox.showinfo("백업 완료", "백업이 성공적으로 완료되었습니다!")

    def backup_ui_error(self, msg):
        """백업 오류 UI 상태 (원본과 동일)"""
        self.queue_log(f"❌ 백업 오류: {msg}")
        messagebox.showerror("백업 오류", f"백업 중 오류가 발생했습니다:\n{msg}")

    def backup_ui_finish(self):
        """백업 종료 UI 상태 (원본과 동일)"""
        # Rate Limit 타이머 정리
        if self.rate_limit_timer:
            self.rate_limit_timer.cancel()
            self.rate_limit_timer = None

        self.progress.stop()
        self.progress["mode"] = "determinate"
        self.progress["value"] = 0
        self.is_working = False
        self.btn_backup.config(state=tk.NORMAL, text="🚀 백업 시작")
        self.set_progress_detail("")
        self.progress_numbers.config(text="")

    def update_progress_info(self):
        """진행률 정보 업데이트 (원본과 동일)"""
        if self.total_notes > 0:
            progress_percent = min((self.current_note / self.total_notes) * 100, 100)
            self.progress["value"] = progress_percent

            if self.sync_phase == "동기화":
                self.progress_numbers.config(text=f"동기화: {self.current_note}/{self.total_notes} 노트")
            elif self.sync_phase == "내보내기":
                self.progress_numbers.config(text=f"내보내기: {self.current_note}/{self.total_notes} 파일")
            else:
                self.progress_numbers.config(text=f"전체 {self.total_notes}개 노트")

    # 유틸리티 메소드들 (원본과 동일)
    def browse_output(self):
        """출력 폴더 선택 (원본과 동일)"""
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)

    def change_db_path(self):
        """DB 경로 변경 (원본과 동일)"""
        new_path = filedialog.asksaveasfilename(
            title="데이터베이스 파일 위치 선택",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.database_path),
            initialfile="evernote_backup.db"
        )
        if new_path:
            is_valid, error_msg = test_database_path(new_path)
            if is_valid:
                self.close_db_connection()
                self.database_path = new_path
                self.db_path_var.set(new_path)
                self.validate_and_init_database()
                self.log_message(f"💾 데이터베이스 경로 변경: {new_path}")
            else:
                messagebox.showerror("경로 오류", f"선택한 경로를 사용할 수 없습니다:\n{error_msg}")

    def validate_and_init_database(self):
        """DB 유효성 검사 및 초기화 (원본과 동일)"""
        try:
            is_valid, error_msg = test_database_path(self.database_path)
            if not is_valid:
                self.db_status.config(text=f"❌ DB 오류: {error_msg}", fg=self.colors['error'])
                self.log_message(f"❌ DB 오류: {error_msg}")

                temp_path = os.path.join(tempfile.gettempdir(), "evernote_backup.db")
                is_temp_valid, _ = test_database_path(temp_path)
                if is_temp_valid:
                    self.database_path = temp_path
                    self.db_path_var.set(temp_path)
                    self.log_message(f"📍 임시 경로 사용: {temp_path}")
                else:
                    messagebox.showerror("데이터베이스 오류", "사용 가능한 데이터베이스 경로를 찾을 수 없습니다.\n관리자 권한으로 실행해보세요.")
                    return

            self.db_status.config(text="✅ DB 경로 정상", fg=self.colors['success'])

        except Exception as e:
            self.db_status.config(text=f"❌ DB 오류: {str(e)}", fg=self.colors['error'])
            self.log_message(f"❌ 데이터베이스 초기화 오류: {str(e)}")
            messagebox.showerror("오류", f"데이터베이스 초기화 실패:\n{str(e)}")

    def close_db_connection(self):
        """DB 연결 종료 (원본과 동일)"""
        if self._db_connection:
            try:
                self._db_connection.close()
            except:
                pass
            self._db_connection = None

    # 로그 관련 메소드들 (원본과 동일)
    def check_log_queue(self):
        """로그 큐 확인 (원본과 동일)"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.check_log_queue)

    def queue_log(self, msg):
        """로그 큐에 메시지 추가 (원본과 동일)"""
        self.log_queue.put(msg)

    def log_message(self, msg):
        """로그 메시지 출력 (원본과 동일)"""
        self.text_log.config(state=tk.NORMAL)
        self.text_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)

    def set_status(self, msg, level="info"):
        """상태 메시지 설정 (원본과 동일)"""
        color = {
            'info': self.colors['text'],
            'success': self.colors['success'],
            'warning': self.colors['warning'],
            'error': self.colors['error']
        }.get(level, self.colors['text'])

        icon = {
            'info': "ℹ️",
            'success': "✅", 
            'warning': "⚠️",
            'error': "❌"
        }.get(level, "ℹ️")

        self.status_label.config(text=f"{icon} {msg}", fg=color)

    def set_progress_detail(self, msg):
        """진행률 상세 설정 (원본과 동일)"""
        self.progress_detail.config(text=msg)

    # 정보 다이얼로그들 (원본과 동일)
    def show_program_info(self):
        """사용법 다이얼로그 (원본 기반 + exe 안내 추가)"""
        info_dialog = tk.Toplevel(self.root)
        info_dialog.title("📋 사용법")
        info_dialog.geometry("650x620")
        info_dialog.grab_set()
        info_dialog.resizable(False, False)

        frame = tk.Frame(info_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text_widget = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=('맑은 고딕', 10),
            bg='#f8f9fa', fg='#333333'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        info_text = r"""📋 에버노트 백업 도구 사용법

이 프로그램은 evernote-backup v1.13.1의 GUI 버전입니다.

🔧 필수 요구사항:
• evernote-backup.exe 파일이 이 GUI와 같은 폴더에 있어야 합니다
• GitHub에서 다운로드: https://github.com/vzhd1701/evernote-backup/releases

📝 사용 단계:

1️⃣ OAuth 로그인 (4단계)
   ① 터미널 열기: OAuth URL 생성을 위한 터미널 실행
   ② URL 복사: 터미널의 OAuth URL을 GUI에 입력
   ③ 브라우저 열기: 에버노트 사이트에서 인증 진행  
   ④ 로그인 완료: 인증 완료 후 백업 가능 상태 확인

2️⃣ 백업 실행
   • 백업할 폴더 선택
   • 백업 시작 버튼 클릭
   • 완료될 때까지 대기

⚠️ 주의사항:
• OAuth는 4단계 순서대로 진행해야 합니다!
• '일괄 백업 허용(Allow Bulk Backup)' 버튼을 꼭 클릭하세요
• Rate Limit이 발생할 수 있습니다 (자동으로 재시도)
• 첫 백업은 시간이 오래 걸립니다
• 네트워크 연결이 안정적이어야 합니다

🎯 특징:
• 원저작자의 검증된 CLI 도구 활용
• 안정적인 백업 및 동기화
• ENEX 형식으로 내보내기 (OneNote, Notion, Obsidian 등에서 사용)
• Rate Limit 자동 처리
• 실시간 진행상황 표시

💻 시스템 요구사항:
• Windows 10/11 (64비트)
• 안정적인 인터넷 연결
• OAuth 인증용 웹브라우저

📅 2025년 9월 버전 - MIT License로 제공됩니다."""

        text_widget.insert(tk.END, info_text)
        text_widget.config(state=tk.DISABLED)

        btn_frame = tk.Frame(info_dialog)
        btn_frame.pack(pady=(10, 20))

        tk.Button(btn_frame, text="닫기", command=info_dialog.destroy,
                 font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=30, pady=8).pack()

    def show_source_info(self):
        """원저작자 정보 다이얼로그 (원본과 동일)"""
        source_dialog = tk.Toplevel(self.root)
        source_dialog.title("🔗 정보")
        source_dialog.geometry("650x420")
        source_dialog.grab_set()
        source_dialog.resizable(False, False)

        frame = tk.Frame(source_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text_widget = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=('맑은 고딕', 10),
            bg='#f8f9fa', fg='#333333'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        source_text = r"""🔗 evernote-backup 정보

📚 원저작자: vzhd1701
📄 라이선스: MIT License  
🔧 GUI 개발: vzhd1701 evernote-backup 기반

이 GUI는 원저작자의 evernote-backup CLI 도구를 래핑한 버전입니다.

🎯 evernote-backup v1.13.1 주요 기능:
- OAuth 2.0 인증 지원
- 안정적인 노트 동기화  
- 완전한 백업 및 복원
- ENEX 형식 내보내기 지원
- Rate Limit 자동 처리

🖥️ 이 GUI의 특징:
- 사용자 친화적 인터페이스
- 실시간 진행상황 표시
- Rate Limit 시각적 표시
- 로그 실시간 출력  
- 4단계 OAuth 간편 로그인

OAuth는 4단계로 진행됩니다:
1. 터미널에서 OAuth URL 생성
2. URL을 GUI에 복사
3. 브라우저에서 인증
4. 인증 완료 확인

⚠️ Rate Limit 안내:
에버노트 서버에서 요청 제한이 있을 수 있습니다.
이 경우 자동으로 대기 후 재시도합니다.

🌐 Windows 환경 최적화
📅 2025년 9월 개발

GitHub: https://github.com/vzhd1701/evernote-backup

evernote-backup은 에버노트의 완전한 백업을 위한 
최고의 오픈소스 도구입니다.

이 GUI는 해당 도구를 더 쉽게 사용할 수 있도록 
인터페이스를 제공합니다."""

        text_widget.insert(tk.END, source_text)
        text_widget.config(state=tk.DISABLED)

        btn_frame = tk.Frame(source_dialog)
        btn_frame.pack(pady=(10, 20))

        tk.Button(btn_frame, text="🔗 GitHub 방문", 
                 command=lambda: webbrowser.open("https://github.com/vzhd1701/evernote-backup"),
                 font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btn_frame, text="닫기", command=source_dialog.destroy,
                 font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=30, pady=8).pack(side=tk.LEFT)

# 메인 실행 부분 (원본과 동일)
def main():
    root = tk.Tk()
    app = EvernoteBackupApp(root)

    def on_close():
        # Rate Limit 타이머 정리 (원본과 동일)
        if hasattr(app, 'rate_limit_timer') and app.rate_limit_timer:
            app.rate_limit_timer.cancel()

        if app.is_working:
            if messagebox.askokcancel("종료 확인", "백업이 진행 중입니다. 정말 종료하시겠습니까?"):
                app.close_db_connection()
                root.destroy()
        else:
            app.close_db_connection()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
