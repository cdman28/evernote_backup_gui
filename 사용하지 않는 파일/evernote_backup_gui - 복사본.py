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

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

# --------- Cross‑PC safe paths ---------
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

# --------------------------------------

class EvernoteBackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("에버노트 백업 도구 (GUI for evernote-backup v1.13.1)")
        self.root.geometry("900x750")
        self.root.minsize(750, 650)

        self.is_working = False
        self.is_logged_in = False
        self.database_path = get_database_path()
        self.export_dir = get_export_dir()
        self.oauth_url = None
        self.oauth_process = None
        self._db_connection = None
        
        # 진행률 추적 변수들
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        
        # Rate Limit 처리용
        self.rate_limit_timer = None
        
        # 실시간 로그를 위한 큐
        self.log_queue = queue.Queue()

        self.setup_variables()
        self.setup_styles()
        self.setup_fonts()
        self.create_widgets()
        self.validate_and_init_database()
        
        # 주기적으로 로그 큐 확인
        self.check_log_queue()

        self.log_message("🚀 에버노트 백업 도구 시작 (GUI for evernote-backup v1.13.1)")
        self.log_message(f"🖥️ OS: {platform.system()}")
        self.log_message(f"💾 DB 경로: {self.database_path}")
        self.log_message(f"📁 내보내기 폴더: {self.export_dir}")

    def setup_variables(self):
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar(value=self.export_dir)

    def setup_styles(self):
        # 색상 시스템 - 통일된 버튼 색상
        self.colors = {
            'evernote_green': '#00A82D',
            'background': '#F8F9FA',
            'text': '#333333',
            'light_text': '#666666',
            'success': '#00A82D',
            'warning': '#FF6F00',
            'error': '#D32F2F',
            'primary': '#1976D2',
            # 모든 버튼 색상 통일
            'button_bg': '#4A90E2',  # 깔끔한 파란색
            'button_text': 'white',  # 모든 버튼 흰색 글씨
            'button_disabled': '#CCCCCC',  # 비활성화 버튼
            'border': '#CCCCCC'
        }

    def setup_fonts(self):
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
        container = tk.Frame(self.root, bg=self.colors['background'])
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Header
        header = tk.Frame(container, bg=self.colors['background'])
        header.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(header, text="🗂️ 에버노트 백업 도구",
                              font=self.fonts['title'], fg=self.colors['evernote_green'],
                              bg=self.colors['background'])
        title_label.pack()
        
        subtitle_label = tk.Label(header, text="GUI for evernote-backup v1.13.1",
                                 font=self.fonts['subtitle'], fg=self.colors['text'],
                                 bg=self.colors['background'])
        subtitle_label.pack()

        # Info buttons - 통일된 색상
        info_frame = tk.Frame(container, bg=self.colors['background'])
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_buttons = tk.Frame(info_frame, bg=self.colors['background'])
        info_buttons.pack()
        
        tk.Button(info_buttons, text="📖 사용법", command=self.show_program_info,
                  font=self.fonts['button_small'], bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=12, pady=3).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Button(info_buttons, text="💻 정보", command=self.show_source_info,
                  font=self.fonts['button_small'], bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=12, pady=3).pack(side=tk.LEFT)

        # Main content area
        main_frame = tk.Frame(container, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column (settings)
        left_column = tk.Frame(main_frame, bg=self.colors['background'])
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Right column (log)
        right_column = tk.Frame(main_frame, bg=self.colors['background'])
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # === LEFT COLUMN CONTENT ===

        # Database path
        db_frame = tk.LabelFrame(left_column, text="🗄️ DB 설정",
                                font=self.fonts['section_title'],
                                fg=self.colors['evernote_green'],
                                padx=10, pady=8)
        db_frame.pack(fill=tk.X, pady=(0, 10))

        self.db_status = tk.Label(db_frame, text="확인 중...", font=self.fonts['small_text'])
        self.db_status.pack(anchor=tk.W, pady=(0, 3))

        tk.Label(db_frame, text="경로:", font=self.fonts['label']).pack(anchor=tk.W)
        
        db_path_frame = tk.Frame(db_frame)
        db_path_frame.pack(fill=tk.X, pady=2)

        self.db_path_var = tk.StringVar(value=self.database_path)
        self.entry_db_path = tk.Entry(db_path_frame, textvariable=self.db_path_var,
                                     font=self.fonts['text'], state='readonly', width=35)
        self.entry_db_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 통일된 버튼 색상
        tk.Button(db_path_frame, text="변경", command=self.change_db_path,
                  font=self.fonts['button_small'],
                  bg=self.colors['button_bg'], fg=self.colors['button_text'], 
                  padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # OAuth 섹션
        oauth_frame = tk.LabelFrame(left_column, text="🔐 OAuth 로그인",
                                    font=self.fonts['section_title'],
                                    fg=self.colors['evernote_green'],
                                    padx=10, pady=10)
        oauth_frame.pack(fill=tk.X, pady=(0, 10))

        self.oauth_status = tk.Label(oauth_frame, text="🔑 로그인 필요", 
                                    font=self.fonts['small_text'], fg=self.colors['warning'])
        self.oauth_status.pack(anchor=tk.W, pady=(0, 8))

        # OAuth 버튼들 - 2x2 그리드, 모두 통일된 색상
        oauth_grid = tk.Frame(oauth_frame, bg=self.colors['background'])
        oauth_grid.pack(fill=tk.X)

        # 첫 번째 줄
        row1 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row1.pack(fill=tk.X, pady=2)

        self.btn_terminal = tk.Button(row1, text="1️⃣ 터미널",
                                      font=self.fonts['button_small'],
                                      bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                      command=self.start_oauth_terminal,
                                      padx=8, pady=4, width=12)
        self.btn_terminal.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_copy = tk.Button(row1, text="2️⃣ URL복사",
                                  font=self.fonts['button_small'],
                                  bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                  command=self.copy_oauth_url, state='disabled',
                                  padx=8, pady=4, width=12)
        self.btn_copy.pack(side=tk.LEFT)

        # 두 번째 줄
        row2 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row2.pack(fill=tk.X, pady=2)

        self.btn_browser = tk.Button(row2, text="3️⃣ 브라우저",
                                     font=self.fonts['button_small'],
                                     bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                     command=self.open_browser, state='disabled',
                                     padx=8, pady=4, width=12)
        self.btn_browser.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_complete = tk.Button(row2, text="4️⃣ 완료",
                                      font=self.fonts['button_small'],
                                      bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                      command=self.check_oauth_token, state='disabled',
                                      padx=8, pady=4, width=12)
        self.btn_complete.pack(side=tk.LEFT)

        # Settings
        settings = tk.LabelFrame(left_column, text="📁 백업 설정",
                                 font=self.fonts['section_title'],
                                 fg=self.colors['evernote_green'],
                                 padx=10, pady=10)
        settings.pack(fill=tk.X, pady=(0, 10))

        tk.Label(settings, text="백업 폴더:", font=self.fonts['label']).pack(anchor=tk.W)
        
        folder_frame = tk.Frame(settings)
        folder_frame.pack(fill=tk.X, pady=3)

        self.entry_folder = tk.Entry(folder_frame, textvariable=self.output_path, 
                                    font=self.fonts['text'], width=35)
        self.entry_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 통일된 버튼 색상
        tk.Button(folder_frame, text="변경", command=self.browse_output,
                  font=self.fonts['button_small'],
                  bg=self.colors['button_bg'], fg=self.colors['button_text'], 
                  padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # 백업 버튼 - 통일된 색상
        self.btn_backup = tk.Button(settings, text="📤 백업 시작",
                                   font=self.fonts['button_large'],
                                   bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                   command=self.start_backup, state='disabled',
                                   padx=20, pady=8)
        self.btn_backup.pack(pady=(10, 0))

        # Status
        status = tk.Frame(left_column, bg=self.colors['background'])
        status.pack(fill=tk.X, pady=(10, 0))

        # 진행률 바
        self.progress = ttk.Progressbar(status, mode='determinate')
        self.progress.pack(fill=tk.X, pady=3)
        self.progress['maximum'] = 100

        # 상태 라벨
        self.status_label = tk.Label(status, text="준비됨",
                                     font=self.fonts['status'],
                                     fg=self.colors['success'], bg=self.colors['background'])
        self.status_label.pack(anchor=tk.W)

        # 진행률 상세 정보
        self.progress_detail = tk.Label(status, text="",
                                       font=self.fonts['small_text'],
                                       fg=self.colors['light_text'], bg=self.colors['background'])
        self.progress_detail.pack(anchor=tk.W)
        
        # 진행률 숫자 표시
        self.progress_numbers = tk.Label(status, text="",
                                        font=self.fonts['small_text'],
                                        fg=self.colors['text'], bg=self.colors['background'])
        self.progress_numbers.pack(anchor=tk.W)

        # === RIGHT COLUMN CONTENT (로그) ===

        # Log
        log_frame = tk.LabelFrame(right_column, text="📜 실시간 로그",
                                 font=self.fonts['section_title'],
                                 fg=self.colors['evernote_green'],
                                 padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.text_log = scrolledtext.ScrolledText(
            log_frame, font=self.fonts['log'],
            bg="#f7f7f7", fg="#111",
            wrap=tk.WORD
        )
        self.text_log.pack(fill=tk.BOTH, expand=True)

    # ========== 단계별 OAuth 기능 ==========
    
    def start_oauth_terminal(self):
        """1️⃣ 터미널 열기"""
        if self.is_working:
            messagebox.showwarning("알림", "다른 작업이 진행 중입니다.")
            return
        is_valid, error_msg = test_database_path(self.database_path)
        if not is_valid:
            messagebox.showerror("DB 오류", f"데이터베이스 경로에 문제가 있습니다:\n{error_msg}")
            return
            
        self.close_db_connection()
        
        self.log_message("🖥️ OAuth 터미널 실행")
        self.set_status("터미널에서 OAuth URL 생성 중...", "info")
        
        try:
            self.database_path.encode('ascii')
        except UnicodeEncodeError:
            messagebox.showerror("경로 오류",
                "데이터베이스 경로에 한글이나 특수문자가 포함되어 있습니다.\n"
                "'변경' 버튼을 눌러 영문 경로로 변경해주세요.\n"
                f"현재 경로: {self.database_path}")
            return

        db_path_win = os.path.normpath(self.database_path)
        cmd = [
            sys.executable, "-m", "evernote_backup", "init-db",
            "--force", "--database", db_path_win,
            "--backend", self.backend_var.get(),
            "--oauth-port", "10500", "--oauth-host", "localhost"
        ]
        cmd_str = " ".join([f'"{str(x)}"' if " " in str(x) else str(x) for x in cmd])

        try:
            if platform.system() == "Windows":
                subprocess.Popen([
                    "cmd", "/c", "start", "cmd", "/k", 
                    f"echo ✅ OAuth URL이 표시되면 GUI에서 '2️⃣ URL복사' 버튼을 클릭하세요. && {cmd_str}"
                ])
            elif platform.system() == "Darwin":  # macOS
                script = f'''
                    tell application "Terminal"
                        activate
                        do script "echo ✅ OAuth URL이 표시되면 GUI에서 '2️⃣ URL복사' 버튼을 클릭하세요. && {cmd_str}"
                    end tell
                '''
                subprocess.Popen(["osascript", "-e", script])
            else:  # Linux
                subprocess.Popen([
                    "gnome-terminal", "--", "bash", "-c",
                    f"echo ✅ OAuth URL이 표시되면 GUI에서 '2️⃣ URL복사' 버튼을 클릭하세요. && {cmd_str}; read"
                ])
                
            # 버튼 상태 변경 - 성공 시에도 통일된 색상 (단지 텍스트만 변경)
            self.btn_terminal.config(state=tk.DISABLED, text="✅ 실행됨")
            self.btn_copy.config(state=tk.NORMAL)
            self.set_status("터미널이 열렸습니다. OAuth URL 생성 대기 중...", "success")
            
        except Exception as e:
            self.log_message(f"❌ 터미널 실행 실패: {e}")
            messagebox.showerror("오류", f"터미널 실행 실패:\n{e}")

    def copy_oauth_url(self):
        """2️⃣ URL 복사"""
        dialog = tk.Toplevel(self.root)
        dialog.title("OAuth URL 입력")
        dialog.geometry("600x350")
        dialog.grab_set()
        dialog.resizable(False, False)

        # 중앙 정렬
        dialog.transient(self.root)
        dialog.geometry("+{}+{}".format(
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))

        frame = tk.Frame(dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="🔗 OAuth URL 입력", 
                 font=('맑은 고딕', 14, 'bold'),
                 fg=self.colors['evernote_green']).pack(pady=(0, 10))

        tk.Label(frame, text="터미널에 표시된 OAuth URL을 복사해서 아래에 붙여넣으세요:",
                 font=self.fonts['text']).pack(pady=(0, 10), anchor=tk.W)

        text_url = tk.Text(frame, height=6, font=self.fonts['text'], wrap=tk.WORD)
        text_url.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_url.focus()

        # 클립보드에서 자동으로 가져오기 시도
        if HAS_CLIPBOARD:
            try:
                clip = pyperclip.paste()
                if clip and "evernote.com/OAuth.action" in clip:
                    text_url.insert(tk.END, clip)
                    self.log_message("📋 클립보드에서 OAuth URL 자동 감지")
            except:
                pass

        def on_confirm():
            url = text_url.get("1.0", "end").strip()
            if not url or "evernote.com/OAuth.action" not in url:
                messagebox.showerror("오류", "올바른 OAuth URL을 입력해 주세요.\n\nURL에는 'evernote.com/OAuth.action'이 포함되어야 합니다.")
                return
            
            self.oauth_url = url
            dialog.destroy()
            
            # 버튼 상태 변경 - 통일된 색상
            self.btn_copy.config(state=tk.DISABLED, text="✅ 수신됨")
            self.btn_browser.config(state=tk.NORMAL)
            self.set_status("URL 복사 완료. 이제 브라우저에서 로그인하세요.", "success")
            self.log_message("📋 OAuth URL 수신 완료")

        def on_cancel():
            dialog.destroy()

        btns = tk.Frame(frame)
        btns.pack(pady=(10, 0))
        
        # 다이얼로그 버튼도 통일된 색상
        tk.Button(btns, text="✅ 확인", command=on_confirm,
                  bg=self.colors['button_bg'], fg=self.colors['button_text'], 
                  font=('맑은 고딕', 11, 'bold'),
                  padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(btns, text="❌ 취소", command=on_cancel, 
                  font=('맑은 고딕', 11),
                  bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=20, pady=8).pack(side=tk.LEFT)

    def open_browser(self):
        """3️⃣ 브라우저 로그인"""
        if not self.oauth_url:
            messagebox.showwarning("알림", "먼저 OAuth URL을 입력해 주세요.")
            return
        
        try:
            webbrowser.open(self.oauth_url)
            
            # 버튼 상태 변경 - 통일된 색상
            self.btn_browser.config(state=tk.DISABLED, text="✅ 열림")
            self.btn_complete.config(state=tk.NORMAL)
            self.set_status("브라우저에서 로그인 완료 후 '4️⃣ 완료' 버튼을 클릭하세요.", "info")
            self.log_message("🌐 브라우저 열기 완료")
            
            # 수정된 Bulk Backup 설명
            messagebox.showinfo("브라우저 로그인 안내", 
                               "브라우저가 열렸습니다!\n\n"
                               "📋 로그인 순서:\n"
                               "1. 에버노트 계정으로 로그인하세요\n"
                               "2. 'Bulk Backup' 권한 허용 화면이 나타날 수 있습니다\n"
                               "   → 이것은 정상입니다! '허용(Allow)' 클릭하세요\n"
                               "   → 대용량 백업을 위한 도구입니다\n"
                               "3. 권한 허용이 완료되면 '4️⃣ 완료' 버튼을 클릭하세요\n\n"
                               "⚠️ 'Bulk Backup'은 에버노트 공식 백업 도구이므로 안전합니다!")
            
        except Exception as e:
            messagebox.showerror("브라우저 오류", f"브라우저 열기 실패:\n{e}")

    def check_oauth_token(self):
        """4️⃣ 로그인 완료 확인"""
        try:
            if not os.path.exists(self.database_path):
                messagebox.showwarning("대기", 
                                     "데이터베이스 파일이 아직 생성되지 않았습니다.\n\n"
                                     "터미널에서 OAuth 과정이 완료될 때까지 기다린 후 다시 시도해주세요.")
                return
                
            conn = sqlite3.connect(self.database_path)
            cur = conn.cursor()
            
            # 토큰 확인
            cur.execute("SELECT value FROM config WHERE name='access_token'")
            access_token_row = cur.fetchone()
            
            if not access_token_row:
                cur.execute("SELECT value FROM config WHERE name LIKE '%token%' OR name LIKE '%oauth%'")
                token_rows = cur.fetchall()
                access_token_row = token_rows[0] if token_rows else None
            
            conn.close()
            
            if access_token_row and access_token_row[0]:
                # 로그인 성공!
                self.is_logged_in = True
                self.btn_complete.config(state=tk.DISABLED, text="✅ 완료")
                self.btn_backup.config(state=tk.NORMAL)
                self.oauth_status.config(text="✅ OAuth 로그인 성공!", fg=self.colors['success'])
                self.set_status("로그인 완료! 이제 백업을 시작할 수 있습니다.", "success")
                self.log_message("🎉 OAuth 로그인 성공")
                
                messagebox.showinfo("로그인 완료", 
                                   "🎉 OAuth 인증이 완료되었습니다!\n\n"
                                   "이제 '📤 백업 시작' 버튼을 클릭하여 백업을 진행하세요.")
            else:
                messagebox.showwarning("로그인 미완료", 
                                     "아직 토큰이 저장되지 않았습니다.\n\n"
                                     "브라우저에서 에버노트 로그인 및 권한 허용을 완료한 후 다시 시도해주세요.")
                
        except Exception as e:
            self.log_message(f"❌ 토큰 확인 중 오류: {e}")
            messagebox.showerror("오류", f"토큰 확인 중 오류가 발생했습니다:\n{e}")

    # ========== 백업 프로세스 (Rate Limit + 진행률 처리) ==========
    
    def start_backup(self):
        if not self.is_logged_in:
            messagebox.showwarning("알림", "먼저 OAuth 로그인을 완료해 주세요.")
            return
        if self.is_working:
            messagebox.showwarning("알림", "백업이 이미 진행 중입니다.")
            return
        if not messagebox.askyesno("백업 시작", 
                                  "백업을 시작하시겠습니까?\n\n"
                                  "노트 수량에 따라 시간이 오래 걸릴 수 있습니다."):
            return
        
        try:
            os.makedirs(self.output_path.get(), exist_ok=True)
        except Exception as e:
            messagebox.showerror("오류", f"백업 폴더 생성 실패:\n{e}")
            return
            
        # 진행률 초기화
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        
        threading.Thread(target=self._backup_task, daemon=True).start()

    def _backup_task(self):
        """백업 작업 수행"""
        try:
            self.is_working = True
            self.root.after(0, self._backup_ui_start)
            self.queue_log("🚀 백업 작업 시작")
            
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            # 1단계: sync (동기화)
            self.sync_phase = "동기화"
            self.root.after(0, lambda: self.set_status("노트 동기화 중...", "warning"))
            self.root.after(0, lambda: self.set_progress_detail("에버노트 서버에서 노트 목록을 가져오는 중..."))
            
            cmd_sync = [
                sys.executable, "-m", "evernote_backup", "sync",
                "--database", self.database_path
            ]
            
            process_sync = subprocess.Popen(
                cmd_sync, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                env=env, 
                bufsize=1, 
                universal_newlines=True
            )
            
            failed_notes = []
            rate_limit_detected = False
            wait_time = None
            
            while True:
                output = process_sync.stdout.readline()
                if output == '' and process_sync.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    
                    # Rate Limit 감지
                    if "Rate limit reached" in line:
                        rate_limit_detected = True
                        time_match = re.search(r'Restart program in (\d+):(\d+)', line)
                        if time_match:
                            minutes = int(time_match.group(1))
                            seconds = int(time_match.group(2))
                            wait_time = minutes * 60 + seconds
                        self.queue_log(f"[SYNC-LIMIT] {line}")
                    # 전체 노트 수 감지
                    elif "note(s) to download" in line:
                        match = re.search(r'(\d+)\s+note\(s\)\s+to\s+download', line)
                        if match:
                            self.total_notes = int(match.group(1))
                            self.root.after(0, lambda: self._update_progress_info())
                        self.queue_log(f"[SYNC] {line}")
                    # 노트 다운로드 진행률 감지
                    elif "Downloading" in line and "note(s)" in line:
                        self.queue_log(f"[SYNC] {line}")
                        self.root.after(0, lambda: self.set_progress_detail("노트 다운로드 시작..."))
                    elif self._is_ignorable_error(line):
                        self.queue_log(f"[SYNC-SKIP] {line}")
                        failed_notes.append(self._extract_note_info(line))
                    else:
                        self.queue_log(f"[SYNC] {line}")
                        
                        # 개별 노트 처리 감지 및 진행률 업데이트
                        if "notebook" in line.lower() and "error" not in line.lower():
                            self.root.after(0, lambda l=line: self.set_progress_detail(f"노트북: {l[:50]}..."))
                        elif ("note" in line.lower() or "downloading" in line.lower()) and "error" not in line.lower():
                            if self.total_notes > 0:
                                self.current_note = min(self.current_note + 1, self.total_notes)
                                self.root.after(0, lambda: self._update_progress_info())
                            self.root.after(0, lambda l=line: self.set_progress_detail(f"노트: {l[:50]}..."))
            
            # Rate Limit 처리
            if rate_limit_detected:
                self._handle_rate_limit(wait_time)
                return
            
            if process_sync.returncode != 0:
                raise Exception("동기화에 실패했습니다")
                
            # 실패 노트 요약
            if failed_notes:
                self.queue_log(f"⚠️ 접근 불가능한 노트 {len(failed_notes)}개 스킵됨")
                
            self.queue_log("✅ 동기화 완료")
            
            # 2단계: export (내보내기)
            self.sync_phase = "내보내기"
            self.current_note = 0
            self.root.after(0, lambda: self.set_status("ENEX 파일 생성 중...", "warning"))
            self.root.after(0, lambda: self.set_progress_detail("노트를 ENEX 형식으로 변환하는 중..."))
            
            cmd_export = [
                sys.executable, "-m", "evernote_backup", "export",
                "--database", self.database_path,
                self.output_path.get()
            ]
            
            process_export = subprocess.Popen(
                cmd_export, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                env=env, 
                bufsize=1, 
                universal_newlines=True
            )
            
            while True:
                output = process_export.stdout.readline()
                if output == '' and process_export.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    self.queue_log(f"[EXPORT] {line}")
                    
                    # 내보내기 진행률 업데이트
                    if "export" in line.lower() or "file" in line.lower():
                        if self.total_notes > 0:
                            self.current_note = min(self.current_note + 1, self.total_notes)
                            self.root.after(0, lambda: self._update_progress_info())
                        self.root.after(0, lambda l=line: self.set_progress_detail(f"파일: {l[:50]}..."))
            
            if process_export.returncode != 0:
                raise Exception("내보내기에 실패했습니다")
                
            self.sync_phase = "완료"
            self.root.after(0, self._backup_ui_success)
            
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda msg=error_message: self._backup_ui_error(msg))
        finally:
            self.root.after(0, self._backup_ui_finish)

    def _update_progress_info(self):
        """진행률 정보 업데이트"""
        if self.total_notes > 0:
            progress_percent = min((self.current_note / self.total_notes) * 100, 100)
            self.progress['value'] = progress_percent
            
            # 진행률 텍스트 업데이트
            self.progress_numbers.config(
                text=f"📊 {self.sync_phase}: {self.current_note}/{self.total_notes} ({progress_percent:.1f}%)"
            )
        else:
            self.progress['mode'] = 'indeterminate'
            self.progress_numbers.config(text=f"📊 {self.sync_phase}: 진행 중...")

    def _handle_rate_limit(self, wait_seconds):
        """Rate Limit 처리"""
        self.root.after(0, self._backup_ui_rate_limit)
        
        if wait_seconds:
            minutes = wait_seconds // 60
            seconds = wait_seconds % 60
            
            choice = messagebox.askyesnocancel(
                "Rate Limit 도달", 
                f"에버노트 API 속도 제한에 도달했습니다.\n\n"
                f"⏰ 대기 시간: {minutes}분 {seconds}초\n\n"
                f"🤔 어떻게 하시겠습니까?\n\n"
                f"• '예': 자동 대기 후 재시도\n"
                f"• '아니오': 지금 중단\n"
                f"• '취소': 나중에 수동 재시도"
            )
            
            if choice is True:  # 예 - 자동 대기
                self._auto_wait_and_retry(wait_seconds)
            elif choice is False:  # 아니오 - 중단
                self.queue_log("❌ 사용자가 백업을 중단했습니다")
                self.root.after(0, self._backup_ui_finish)
            else:  # 취소 - 나중에 수동
                self.queue_log(f"⏸️ 백업 일시중단. {minutes}분 {seconds}초 후 수동 재시도 바랍니다.")
                self.root.after(0, self._backup_ui_finish)
        else:
            messagebox.showwarning("Rate Limit", 
                                 "에버노트 API 속도 제한에 도달했습니다.\n"
                                 "잠시 후 다시 시도해주세요.")
            self.root.after(0, self._backup_ui_finish)

    def _auto_wait_and_retry(self, wait_seconds):
        """자동 대기 후 재시도"""
        self.queue_log(f"⏰ Rate Limit 자동 대기 시작: {wait_seconds}초")
        self.root.after(0, lambda: self.set_status("Rate Limit 대기 중...", "warning"))
        
        # 진행률 바를 indeterminate 모드로 변경
        self.progress['mode'] = 'indeterminate'
        self.progress.start()
        
        original_wait_seconds = wait_seconds
        
        def countdown_update():
            nonlocal wait_seconds
            if wait_seconds > 0:
                minutes = wait_seconds // 60
                seconds = wait_seconds % 60
                elapsed = original_wait_seconds - wait_seconds
                elapsed_minutes = elapsed // 60
                elapsed_seconds = elapsed % 60
                
                self.root.after(0, lambda m=minutes, s=seconds: self.set_progress_detail(f"⏰ 대기 중: {m:02d}:{s:02d}"))
                self.root.after(0, lambda em=elapsed_minutes, es=elapsed_seconds: self.progress_numbers.config(
                    text=f"⏰ 경과시간: {em:02d}:{es:02d}"
                ))
                wait_seconds -= 1
                # 1초 후 다시 업데이트
                self.rate_limit_timer = threading.Timer(1.0, countdown_update)
                self.rate_limit_timer.start()
            else:
                # 대기 완료 - 자동 재시도
                self.queue_log("✅ Rate Limit 대기 완료. 백업을 재시작합니다.")
                self.root.after(0, lambda: self.set_status("Rate Limit 대기 완료 - 재시작 중...", "success"))
                self.root.after(0, lambda: self.progress_numbers.config(text="🔄 재시작 중..."))
                
                time.sleep(2)  # 안전을 위해 2초 추가 대기
                
                # 진행률 초기화하고 재시작
                self.total_notes = 0
                self.current_note = 0
                self.sync_phase = "재시작"
                self.progress.stop()
                self.progress['mode'] = 'determinate'
                self.progress['value'] = 0
                
                threading.Thread(target=self._backup_task, daemon=True).start()
        
        # 카운트다운 시작
        countdown_update()

    def _backup_ui_start(self):
        self.btn_backup.config(state=tk.DISABLED, text="⏳ 백업 중...")
        # 진행률 바를 determinate 모드로 설정
        self.progress['mode'] = 'determinate'
        self.progress['value'] = 0

    def _backup_ui_rate_limit(self):
        """Rate Limit UI 상태"""
        self.btn_backup.config(text="⏰ Rate Limit 대기 중...")
        self.set_status("에버노트 API 속도 제한 도달", "warning")

    def _backup_ui_success(self):
        self.log_message("🎉 백업 완료!")
        self.set_status("백업 완료", "success")
        self.set_progress_detail("접근 가능한 모든 노트가 성공적으로 백업되었습니다.")
        
        # 진행률 100% 표시
        self.progress['value'] = 100
        self.progress_numbers.config(text=f"✅ 완료: {self.total_notes}/{self.total_notes} (100%)")
        
        # 완료 메시지
        completion_msg = "🎉 백업이 완료되었습니다!\n\n"
        if self.total_notes > 0:
            completion_msg += f"📊 처리된 노트: {self.total_notes}개\n\n"
        completion_msg += "📋 참고: 일부 노트가 스킵될 수 있습니다:\n"
        completion_msg += "• 공유받은 노트북 (권한 없음)\n"
        completion_msg += "• 이미 삭제된 노트의 잔재\n"
        completion_msg += "• 비즈니스 계정의 제한된 노트\n\n"
        completion_msg += "백업 폴더를 여시겠습니까?"
        
        if messagebox.askyesno("완료", completion_msg):
            try:
                target = self.output_path.get()
                if platform.system() == "Windows":
                    os.startfile(target)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", target])
                else:
                    subprocess.Popen(["xdg-open", target])
            except Exception as e:
                self.log_message(f"❌ 폴더 열기 실패: {e}")

    def _backup_ui_error(self, msg):
        self.log_message(f"❌ 백업 실패: {msg}")
        self.set_status("백업 실패", "error")
        self.set_progress_detail("백업 중 오류가 발생했습니다.")
        messagebox.showerror("백업 실패", f"백업 중 오류가 발생했습니다:\n{msg}")

    def _backup_ui_finish(self):
        # Rate Limit 타이머 정리
        if self.rate_limit_timer:
            self.rate_limit_timer.cancel()
            self.rate_limit_timer = None
            
        self.progress.stop()
        self.progress['mode'] = 'determinate'
        self.progress['value'] = 0
        self.is_working = False
        self.btn_backup.config(state=tk.NORMAL, text="📤 백업 시작")
        self.set_progress_detail("")
        self.progress_numbers.config(text="")

    def _is_ignorable_error(self, line):
        """무시할 수 있는 오류인지 확인"""
        ignorable_patterns = [
            "Failed to download note",
            "Note.*will be skipped",
            "LinkedNotebook.*is not accessible", 
            "RemoteServer returned system error",
            "PERMISSION_DENIED", 
            "NOT_FOUND",
            "Authentication failed",
            "Shared notebook.*not found",
            "Business notebook.*expired"
        ]
        
        line_lower = line.lower()
        
        # Rate Limit는 별도 처리하므로 무시하지 않음
        if "rate limit" in line_lower:
            return False
            
        return any(pattern.lower() in line_lower for pattern in ignorable_patterns)

    def _extract_note_info(self, line):
        """오류 라인에서 노트 정보 추출"""
        patterns = [
            r'note[:\s]+"?([^"]+)"?',
            r'Note\s+([^\s]+)',
            r'title[:\s]+"?([^"]+)"?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "Unknown"

    # ========== 프로그램 정보 다이얼로그 ==========
    
    def show_program_info(self):
        info_dialog = tk.Toplevel(self.root)
        info_dialog.title("사용법 안내")
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

        # Bulk Backup 설명 수정 + 윈도우 전용
        info_text = """📋 에버노트 백업 도구 사용법

🔹 개요
이 프로그램은 에버노트(Evernote) 계정의 모든 노트를 안전하게 백업하는 도구입니다.
에버노트의 공식 OAuth 인증을 통해 안전하게 로그인하고, 모든 노트를 ENEX 파일로 내보내기할 수 있습니다.

🔹 사용법 (4단계로 간단하게!)

1️⃣ 터미널 열기
   • "1️⃣ 터미널" 버튼을 클릭하면 자동으로 터미널이 열립니다
   • 터미널에서 OAuth 인증 URL이 생성될 때까지 기다려주세요

2️⃣ URL 복사
   • 터미널에 OAuth URL이 표시되면 복사합니다
   • "2️⃣ URL복사" 버튼을 클릭하여 URL을 붙여넣습니다
   • 클립보드에 URL이 있으면 자동으로 감지됩니다

3️⃣ 브라우저 로그인  
   • "3️⃣ 브라우저" 버튼을 클릭하면 자동으로 브라우저가 열립니다
   • 에버노트 로그인 페이지가 나타나면 계정으로 로그인하세요
   
   ⚠️ 중요: "Bulk Backup" 인증 화면 안내
   • 로그인 후 "Bulk Backup 권한 허용" 화면이 나타날 수 있습니다
   • 이것은 정상적인 과정이니 당황하지 마세요!
   • "Bulk Backup"은 대용량 백업을 위한 도구입니다
   • "허용" 또는 "Allow" 버튼을 클릭하면 됩니다
   • 이 권한이 있어야 모든 노트를 백업할 수 있습니다

4️⃣ 완료
   • 브라우저에서 권한 허용이 완료되면 "4️⃣ 완료" 버튼을 클릭합니다
   • 로그인이 성공하면 백업 버튼이 활성화됩니다

🔹 백업 진행
• 동기화(Sync): 에버노트 서버에서 모든 노트 정보를 다운로드합니다
• 내보내기(Export): 다운로드한 노트들을 ENEX 파일로 변환합니다
• 진행률: 전체 노트 수와 현재 진행률을 실시간으로 확인할 수 있습니다

🔹 특별 기능

⏰ Rate Limit 자동 처리
• 에버노트 API 제한 시 자동으로 감지하고 대기합니다
• 자동 대기/수동 중단/나중에 재시도 중 선택할 수 있습니다
• 대기 시간을 실시간으로 확인할 수 있습니다

📊 실시간 진행률 표시  
• 백업할 전체 노트 개수와 현재 처리 중인 노트 번호를 표시합니다
• 동기화/내보내기 단계를 구분하여 보여줍니다
• 백분율로 진행률을 시각적으로 확인할 수 있습니다

🔹 출력 파일
• ENEX 파일: 에버노트 표준 내보내기 형식입니다
• 다른 노트 앱으로 가져오기가 가능합니다 (OneNote, Notion, Obsidian 등)
• 백업 완료 후 자동으로 폴더를 열어 확인할 수 있습니다

🔹 시스템 요구사항
• Windows 10/11 (64비트 권장)
• 안정적인 인터넷 연결
• 에버노트 계정 (무료/프리미엄 모두 지원)

🔹 주의사항
• 네트워크: 안정적인 인터넷 연결 상태에서 사용해주세요
• 시간: 노트 수량에 따라 백업 시간이 오래 걸릴 수 있습니다
• OAuth 권한: "Bulk Backup" 권한은 대용량 백업을 위해 반드시 필요합니다
• 스킵되는 노트: 다음과 같은 노트들은 정상적으로 스킵됩니다
  - 공유받은 노트북 (권한 없음)
  - 이미 삭제된 노트의 잔재  
  - 비즈니스 계정의 제한된 노트
• Rate Limit: 에버노트 API 속도 제한으로 대기가 필요할 수 있습니다

🔹 문제 해결
• OAuth 로그인 실패: 브라우저에서 정확히 로그인하고 권한을 허용했는지 확인하세요
• "Bulk Backup" 권한 거부: 권한을 허용해야만 전체 백업이 가능합니다
• 백업 실패: 네트워크 연결을 확인하고 잠시 후 다시 시도하세요  
• Rate Limit: 자동 대기 기능을 사용하거나 시간을 두고 다시 시도하세요

🔹 보안 및 개인정보
• 모든 인증은 에버노트 공식 OAuth 시스템을 사용합니다
• 백업 데이터는 사용자의 컴퓨터에만 저장됩니다
• 제3자 서버로 데이터가 전송되지 않습니다
"""

        text_widget.insert(tk.END, info_text)
        text_widget.config(state=tk.DISABLED)

        btn_frame = tk.Frame(info_dialog)
        btn_frame.pack(pady=(10, 20))
        # 통일된 버튼 색상
        tk.Button(btn_frame, text="닫기", command=info_dialog.destroy,
                  font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=30, pady=8).pack()

    def show_source_info(self):
        source_dialog = tk.Toplevel(self.root)
        source_dialog.title("프로그램 정보")
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

        # 문서 링크 제거, 메인 링크만 유지
        source_text = """💻 프로그램 정보

🔹 핵심 라이브러리: evernote-backup v1.13.1
개발자: vzhd1701
라이선스: MIT License

이 GUI 도구는 vzhd1701님이 개발한 evernote-backup 라이브러리를 기반으로 
제작된 사용자 친화적인 인터페이스입니다.

🔹 주요 구성요소

1. evernote-backup 라이브러리 (v1.13.1)
   - 에버노트 OAuth 인증 처리
   - 노트 동기화 및 다운로드  
   - ENEX 파일 생성 및 내보내기
   - Rate Limit 처리

2. GUI 인터페이스 (이 프로그램)
   - 사용자 친화적인 단계별 인터페이스
   - 실시간 진행상황 및 Rate Limit 처리
   - 자동 경로 관리 및 안전성 검증
   - 직관적인 4단계 OAuth 로그인

🔹 특징
• 단계별 안내: 복잡한 OAuth 과정을 4단계로 단순화
• 실시간 피드백: 진행률과 상태를 실시간으로 표시
• 자동 처리: Rate Limit 감지 및 자동 대기 기능
• 안전성: 데이터베이스 경로 검증 및 오류 처리
• Windows 최적화: Windows 환경에 특화된 디자인

🔹 원본 라이브러리
GitHub: https://github.com/vzhd1701/evernote-backup

🔹 기술적 배경  
evernote-backup은 에버노트의 공식 API를 사용하여 안전하고 완전한 백업을 제공합니다.
이 GUI 도구는 명령줄 사용이 어려운 사용자들을 위해 시각적 인터페이스를 제공합니다.

🔹 버전 정보
GUI 도구: evernote-backup v1.13.1 기반
Windows 전용 버전
최종 업데이트: 2025년 9월

🔹 라이선스 및 사용 조건
• MIT License: 자유롭게 사용, 수정, 배포 가능
• 원본 라이브러리의 라이선스를 준수합니다
• 상업적 사용 가능

🔹 지원 및 문의
• 원본 라이브러리 관련: GitHub 페이지 이용
• 사용법 문의: 프로그램 내 사용법 안내 참조
"""

        text_widget.insert(tk.END, source_text)
        text_widget.config(state=tk.DISABLED)

        # 메인 GitHub 링크만 클릭 가능하게 만들기
        def make_link_clickable(text_widget, url_text, url_link):
            """텍스트 위젯에서 특정 텍스트를 클릭 가능한 링크로 만들기"""
            content = text_widget.get("1.0", tk.END)
            start_pos = content.find(url_text)
            if start_pos != -1:
                lines_before = content[:start_pos].count('\n')
                char_pos = start_pos - content[:start_pos].rfind('\n') - 1
                if char_pos < 0:
                    char_pos = start_pos
                
                start_index = f"{lines_before + 1}.{char_pos}"
                end_index = f"{lines_before + 1}.{char_pos + len(url_text)}"
                
                # 링크 스타일 적용
                text_widget.tag_add("link", start_index, end_index)
                text_widget.tag_config("link", foreground="blue", underline=True)
                
                # 클릭 이벤트 바인딩
                def open_link(event):
                    webbrowser.open(url_link)
                
                text_widget.tag_bind("link", "<Button-1>", open_link)
                text_widget.tag_bind("link", "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                text_widget.tag_bind("link", "<Leave>", lambda e: text_widget.config(cursor=""))

        # 메인 GitHub 링크만 클릭 가능하게 만들기
        make_link_clickable(text_widget, 
                          "https://github.com/vzhd1701/evernote-backup",
                          "https://github.com/vzhd1701/evernote-backup")

        btn_frame = tk.Frame(source_dialog)
        btn_frame.pack(pady=(10, 20))
        
        # 통일된 버튼 색상
        tk.Button(btn_frame, text="🔗 GitHub 방문", 
                  command=lambda: webbrowser.open("https://github.com/vzhd1701/evernote-backup"),
                  font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(btn_frame, text="닫기", command=source_dialog.destroy,
                  font=('맑은 고딕', 11), bg=self.colors['button_bg'], fg=self.colors['button_text'],
                  padx=30, pady=8).pack(side=tk.LEFT)

    # ========== 로그 및 상태 관리 ==========
    
    def check_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.check_log_queue)

    def queue_log(self, msg):
        self.log_queue.put(msg)

    def log_message(self, msg):
        self.text_log.config(state=tk.NORMAL)
        self.text_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)

    def set_status(self, msg, level='info'):
        color = {
            'info': self.colors['text'],
            'success': self.colors['success'],
            'warning': self.colors['warning'],
            'error': self.colors['error']
        }.get(level, self.colors['text'])
        icon = {'info': 'ℹ️', 'success': '✅', 'warning': '⚠️', 'error': '❌'}.get(level, '')
        self.status_label.config(text=f"{icon} {msg}", fg=color)

    def set_progress_detail(self, msg):
        self.progress_detail.config(text=msg)

    # ========== DB 연결 관리 ==========
    
    def close_db_connection(self):
        if self._db_connection:
            try:
                self._db_connection.close()
                self._db_connection = None
                self.log_message("💾 DB 연결 닫음")
                time.sleep(0.5)
            except Exception as e:
                self.log_message(f"❌ DB 연결 닫기 오류: {e}")

    def get_db_connection(self):
        if not self._db_connection:
            self._db_connection = sqlite3.connect(self.database_path)
        return self._db_connection

    # ========== 설정 관리 ==========
    
    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)

    def change_db_path(self):
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
        try:
            is_valid, error_msg = test_database_path(self.database_path)
            if not is_valid:
                self.db_status.config(text=f"❌ DB 오류: {error_msg}", fg=self.colors['error'])
                self.log_message(f"❌ 데이터베이스 경로 오류: {error_msg}")
                temp_path = os.path.join(tempfile.gettempdir(), "evernote_backup.db")
                is_temp_valid, _ = test_database_path(temp_path)
                if is_temp_valid:
                    self.database_path = temp_path
                    self.db_path_var.set(temp_path)
                    self.log_message(f"🔄 임시 위치 사용: {temp_path}")
                else:
                    messagebox.showerror("심각한 오류",
                        "데이터베이스를 생성할 수 있는 위치를 찾을 수 없습니다.\n"
                        "관리자 권한으로 실행하거나 다른 위치를 선택해 주세요.")
                    return
            
            self.db_status.config(text="✅ DB 정상", fg=self.colors['success'])
            self.log_message("💾 데이터베이스 경로 확인 완료")
            
        except Exception as e:
            self.db_status.config(text=f"❌ DB 초기화 실패: {e}", fg=self.colors['error'])
            self.log_message(f"❌ DB 초기화 오류: {e}")
            messagebox.showerror("데이터베이스 오류", f"데이터베이스 초기화에 실패했습니다:\n{e}")


def main():
    root = tk.Tk()
    app = EvernoteBackupApp(root)

    def on_close():
        # Rate Limit 타이머 정리
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
