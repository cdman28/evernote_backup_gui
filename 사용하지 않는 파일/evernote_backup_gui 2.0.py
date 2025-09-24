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
        self.root.title("에버노트 백업 도구 v2.0")
        # 🔥 창 크기 최적화 (로그 공간 확보)
        self.root.geometry("900x750")
        self.root.minsize(750, 650)

        self.is_working = False
        self.is_logged_in = False
        self.database_path = get_database_path()
        self.export_dir = get_export_dir()
        self.oauth_url = None
        self.oauth_process = None
        self._db_connection = None
        
        # 🔥 진행률 추적 변수들
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"  # 준비 중, 동기화, 내보내기, 완료
        
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

        self.log_message("🚀 에버노트 백업 도구 v2.0 시작")
        self.log_message(f"🖥️ OS: {platform.system()}")
        self.log_message(f"💾 DB 경로: {self.database_path}")
        self.log_message(f"📁 내보내기 폴더: {self.export_dir}")

    def setup_variables(self):
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar(value=self.export_dir)

    def setup_styles(self):
        # 🔥 색상 시스템 개선 - 진한 배경에는 흰색 글씨 보장
        self.colors = {
            'evernote_green': '#00A82D',
            'evernote_dark': '#1B7A2A',
            'evernote_light': '#4CAF50',
            'background': '#F8F9FA',
            'text': '#333333',
            'light_text': '#666666',
            'success': '#00A82D',
            'warning': '#FF6F00',
            'error': '#D32F2F',
            'primary': '#1976D2',
            'secondary': '#7B1FA2',
            'button_bg': '#E0E0E0',  # 밝은 버튼 배경
            'border': '#CCCCCC'
        }

    def setup_fonts(self):
        # 🔥 폰트 크기 조정 (공간 절약)
        self.fonts = {
            'title': ('맑은 고딕', 22, 'bold'),
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

        # 🔥 Header - 공간 절약
        header = tk.Frame(container, bg=self.colors['background'])
        header.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(header, text="🗂️ 에버노트 백업 도구 v2.0",
                              font=self.fonts['title'], fg=self.colors['evernote_green'],
                              bg=self.colors['background'])
        title_label.pack()
        
        subtitle_label = tk.Label(header, text="Rate Limit 처리 + 진행률 표시",
                                 font=self.fonts['subtitle'], fg=self.colors['text'],
                                 bg=self.colors['background'])
        subtitle_label.pack()

        # 🔥 Info buttons - 한줄로 컴팩트하게
        info_frame = tk.Frame(container, bg=self.colors['background'])
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_buttons = tk.Frame(info_frame, bg=self.colors['background'])
        info_buttons.pack()
        
        tk.Button(info_buttons, text="📖 정보", command=self.show_program_info,
                  font=self.fonts['button_small'], bg=self.colors['success'], fg='white',
                  padx=12, pady=3).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Button(info_buttons, text="💻 코드", command=self.show_source_info,
                  font=self.fonts['button_small'], bg=self.colors['primary'], fg='white',
                  padx=12, pady=3).pack(side=tk.LEFT)

        # 🔥 Main content area - 좌우 분할로 공간 효율성 증대
        main_frame = tk.Frame(container, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column (settings)
        left_column = tk.Frame(main_frame, bg=self.colors['background'])
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Right column (log)
        right_column = tk.Frame(main_frame, bg=self.colors['background'])
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # === LEFT COLUMN CONTENT ===

        # 🔥 Database path - 컴팩트하게
        db_frame = tk.LabelFrame(left_column, text="🗄️ DB 설정",
                                font=self.fonts['section_title'],
                                fg=self.colors['evernote_green'],
                                padx=10, pady=8)
        db_frame.pack(fill=tk.X, pady=(0, 10))

        self.db_status = tk.Label(db_frame, text="확인 중...", font=self.fonts['small_text'])
        self.db_status.pack(anchor=tk.W, pady=(0, 3))

        # DB 경로 - 세로 배치로 공간 절약
        tk.Label(db_frame, text="경로:", font=self.fonts['label']).pack(anchor=tk.W)
        
        db_path_frame = tk.Frame(db_frame)
        db_path_frame.pack(fill=tk.X, pady=2)

        self.db_path_var = tk.StringVar(value=self.database_path)
        self.entry_db_path = tk.Entry(db_path_frame, textvariable=self.db_path_var,
                                     font=self.fonts['text'], state='readonly', width=35)
        self.entry_db_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(db_path_frame, text="변경", command=self.change_db_path,
                  font=self.fonts['button_small'],
                  bg=self.colors['button_bg'], padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # 🔥 OAuth 섹션 - 세로 배치로 공간 절약
        oauth_frame = tk.LabelFrame(left_column, text="🔐 OAuth 로그인",
                                    font=self.fonts['section_title'],
                                    fg=self.colors['evernote_green'],
                                    padx=10, pady=10)
        oauth_frame.pack(fill=tk.X, pady=(0, 10))

        self.oauth_status = tk.Label(oauth_frame, text="🔑 로그인 필요", 
                                    font=self.fonts['small_text'], fg=self.colors['warning'])
        self.oauth_status.pack(anchor=tk.W, pady=(0, 8))

        # OAuth 버튼들 - 2x2 그리드로 배치
        oauth_grid = tk.Frame(oauth_frame, bg=self.colors['background'])
        oauth_grid.pack(fill=tk.X)

        # 첫 번째 줄
        row1 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row1.pack(fill=tk.X, pady=2)

        self.btn_terminal = tk.Button(row1, text="1️⃣ 터미널",
                                      font=self.fonts['button_small'],
                                      bg=self.colors['evernote_green'], fg='white',
                                      command=self.start_oauth_terminal,
                                      padx=8, pady=4, width=12)
        self.btn_terminal.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_copy = tk.Button(row1, text="2️⃣ URL복사",
                                  font=self.fonts['button_small'],
                                  bg=self.colors['evernote_light'], fg='white',
                                  command=self.copy_oauth_url, state='disabled',
                                  padx=8, pady=4, width=12)
        self.btn_copy.pack(side=tk.LEFT)

        # 두 번째 줄
        row2 = tk.Frame(oauth_grid, bg=self.colors['background'])
        row2.pack(fill=tk.X, pady=2)

        self.btn_browser = tk.Button(row2, text="3️⃣ 브라우저",
                                     font=self.fonts['button_small'],
                                     bg=self.colors['evernote_dark'], fg='white',
                                     command=self.open_browser, state='disabled',
                                     padx=8, pady=4, width=12)
        self.btn_browser.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_complete = tk.Button(row2, text="4️⃣ 완료",
                                      font=self.fonts['button_small'],
                                      bg=self.colors['success'], fg='white',
                                      command=self.check_oauth_token, state='disabled',
                                      padx=8, pady=4, width=12)
        self.btn_complete.pack(side=tk.LEFT)

        # 🔥 Settings - 세로로 컴팩트
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

        tk.Button(folder_frame, text="변경", command=self.browse_output,
                  font=self.fonts['button_small'],
                  bg=self.colors['button_bg'], padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))

        # 백업 버튼
        self.btn_backup = tk.Button(settings, text="📤 백업 시작",
                                   font=self.fonts['button_large'],
                                   bg=self.colors['primary'], fg='white',
                                   command=self.start_backup, state='disabled',
                                   padx=20, pady=8)
        self.btn_backup.pack(pady=(10, 0))

        # 🔥 Status - 컴팩트하지만 진행률 정보 추가
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

        # 🔥 진행률 상세 정보
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

        # 🔥 Log - 큰 공간 확보
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
                
            # 🔥 버튼 상태 변경 - 성공 색상으로
            self.btn_terminal.config(state=tk.DISABLED, text="✅ 실행됨", bg=self.colors['success'])
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
            
            # 🔥 버튼 상태 변경
            self.btn_copy.config(state=tk.DISABLED, text="✅ 수신됨", bg=self.colors['success'])
            self.btn_browser.config(state=tk.NORMAL)
            self.set_status("URL 복사 완료. 이제 브라우저에서 로그인하세요.", "success")
            self.log_message("📋 OAuth URL 수신 완료")

        def on_cancel():
            dialog.destroy()

        btns = tk.Frame(frame)
        btns.pack(pady=(10, 0))
        
        tk.Button(btns, text="✅ 확인", command=on_confirm,
                  bg=self.colors['evernote_green'], fg="white", 
                  font=('맑은 고딕', 11, 'bold'),
                  padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(btns, text="❌ 취소", command=on_cancel, 
                  font=('맑은 고딕', 11),
                  bg=self.colors['button_bg'],
                  padx=20, pady=8).pack(side=tk.LEFT)

    def open_browser(self):
        """3️⃣ 브라우저 로그인"""
        if not self.oauth_url:
            messagebox.showwarning("알림", "먼저 OAuth URL을 입력해 주세요.")
            return
        
        try:
            webbrowser.open(self.oauth_url)
            
            # 🔥 버튼 상태 변경
            self.btn_browser.config(state=tk.DISABLED, text="✅ 열림", bg=self.colors['success'])
            self.btn_complete.config(state=tk.NORMAL)
            self.set_status("브라우저에서 로그인 완료 후 '4️⃣ 완료' 버튼을 클릭하세요.", "info")
            self.log_message("🌐 브라우저 열기 완료")
            
            # 안내 메시지
            messagebox.showinfo("브라우저 로그인", 
                               "브라우저가 열렸습니다!\n\n"
                               "1. 에버노트 계정으로 로그인하세요\n"
                               "2. 앱 권한을 허용하세요\n"
                               "3. 완료되면 '4️⃣ 완료' 버튼을 클릭하세요")
            
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
                self.btn_complete.config(state=tk.DISABLED, text="✅ 완료", bg=self.colors['success'])
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
            
        # 🔥 진행률 초기화
        self.total_notes = 0
        self.current_note = 0
        self.sync_phase = "준비 중"
        
        threading.Thread(target=self._backup_task, daemon=True).start()

    def _backup_task(self):
        """🔥 개선된 백업 작업 - Rate Limit + 진행률 처리"""
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
                    
                    # 🔥 Rate Limit 감지
                    if "Rate limit reached" in line:
                        rate_limit_detected = True
                        # 시간 추출 (예: "Restart program in 24:55")
                        time_match = re.search(r'Restart program in (\d+):(\d+)', line)
                        if time_match:
                            minutes = int(time_match.group(1))
                            seconds = int(time_match.group(2))
                            wait_time = minutes * 60 + seconds
                        self.queue_log(f"[SYNC-LIMIT] {line}")
                    # 🔥 전체 노트 수 감지
                    elif "note(s) to download" in line:
                        # "381 note(s) to download..." 패턴에서 숫자 추출
                        match = re.search(r'(\d+)\s+note\(s\)\s+to\s+download', line)
                        if match:
                            self.total_notes = int(match.group(1))
                            self.root.after(0, lambda: self._update_progress_info())
                        self.queue_log(f"[SYNC] {line}")
                    # 🔥 노트 다운로드 진행률 감지
                    elif "Downloading" in line and "note(s)" in line:
                        # "Downloading 381 note(s)..." 패턴 감지
                        self.queue_log(f"[SYNC] {line}")
                        self.root.after(0, lambda: self.set_progress_detail("노트 다운로드 시작..."))
                    elif self._is_ignorable_error(line):
                        self.queue_log(f"[SYNC-SKIP] {line}")
                        failed_notes.append(self._extract_note_info(line))
                    else:
                        self.queue_log(f"[SYNC] {line}")
                        
                        # 🔥 개별 노트 처리 감지 및 진행률 업데이트
                        if "notebook" in line.lower() and "error" not in line.lower():
                            self.root.after(0, lambda l=line: self.set_progress_detail(f"노트북: {l[:50]}..."))
                        elif ("note" in line.lower() or "downloading" in line.lower()) and "error" not in line.lower():
                            # 노트 처리 시 카운터 증가 (추정)
                            if self.total_notes > 0:
                                self.current_note = min(self.current_note + 1, self.total_notes)
                                self.root.after(0, lambda: self._update_progress_info())
                            self.root.after(0, lambda l=line: self.set_progress_detail(f"노트: {l[:50]}..."))
            
            # 🔥 Rate Limit 처리
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
            self.current_note = 0  # 내보내기용 카운터 리셋
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
                    
                    # 🔥 내보내기 진행률 업데이트
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
        """🔥 진행률 정보 업데이트"""
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
        """🔥 Rate Limit 처리"""
        self.root.after(0, self._backup_ui_rate_limit)
        
        if wait_seconds:
            minutes = wait_seconds // 60
            seconds = wait_seconds % 60
            wait_msg = f"⏰ Rate Limit: {minutes}분 {seconds}초 후 재시도 가능"
            
            # 사용자에게 선택권 제공
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
        
        # 🔥 진행률 100% 표시
        self.progress['value'] = 100
        self.progress_numbers.config(text=f"✅ 완료: {self.total_notes}/{self.total_notes} (100%)")
        
        # 🔥 완료 메시지 개선
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
        info_dialog.title("프로그램 정보")
        info_dialog.geometry("650x600")
        info_dialog.grab_set()
        info_dialog.resizable(False, False)

        frame = tk.Frame(info_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text_widget = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=('맑은 고딕', 10),
            bg='#f8f9fa', fg='#333333'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        info_text = """📋 에버노트 백업 도구 v2.0

🆕 v2.0 새로운 기능
• ⏰ Rate Limit 자동 처리: API 제한 시 자동 대기 후 재시도
• 📊 실시간 진행률 표시: 전체/현재 노트 수 및 백분율 표시
• 🔄 자동 재시도 기능: Rate Limit 대기 후 자동으로 백업 재개
• 📈 상세 진행 정보: 동기화/내보내기 단계별 진행상황

🔹 개요
이 프로그램은 에버노트(Evernote) 계정의 모든 노트를 안전하게 백업하는 GUI 도구입니다.
에버노트의 공식 OAuth 인증을 통해 안전하게 로그인하고, 모든 노트를 ENEX 파일로 내보내기할 수 있습니다.

🔹 사용법 (4단계)
1️⃣ 터미널 열기: OAuth 인증을 위한 터미널을 엽니다
2️⃣ URL 복사: 터미널에 표시된 OAuth URL을 복사하여 입력합니다
3️⃣ 브라우저 로그인: 자동으로 브라우저가 열려 에버노트 로그인을 진행합니다
4️⃣ 완료: 로그인이 완료되면 백업을 시작할 수 있습니다

🔹 백업 과정
- 동기화(Sync): 에버노트 서버에서 모든 노트 정보를 로컬 DB로 다운로드
- 내보내기(Export): 로컬 DB의 노트들을 ENEX 파일로 변환하여 저장

🔹 Rate Limit 처리
• 자동 감지: API 제한 시 자동으로 감지하고 대기시간 표시
• 선택 옵션: 자동 대기/수동 중단/나중에 재시도 중 선택 가능
• 실시간 카운트다운: 남은 대기시간을 실시간으로 표시

🔹 진행률 표시
• 전체 노트 수: 백업할 총 노트 개수 표시
• 현재 진행률: 현재 처리 중인 노트 번호 및 백분율
• 단계별 표시: 동기화/내보내기 단계별 구분 표시

🔹 기술 스택
• Python + Tkinter (GUI)
• evernote-backup 라이브러리 (백엔드)
• SQLite (토큰 및 노트 데이터 저장)
• OAuth 1.0a 인증 프로토콜

🔹 시스템 요구사항
• Python 3.7 이상
• 인터넷 연결
• 에버노트 계정 (무료/프리미엄 모두 지원)

🔹 주의사항
• Rate Limit: 에버노트 API는 속도 제한이 있어 대기가 필요할 수 있습니다
• 공유/삭제된 노트: 일부 노트는 권한 문제로 스킵될 수 있습니다 (정상 동작)
• 네트워크: 안정적인 인터넷 연결 상태에서 사용해주세요

🔹 라이선스
MIT License - 자유롭게 사용, 수정, 배포 가능
"""

        text_widget.insert(tk.END, info_text)
        text_widget.config(state=tk.DISABLED)

        btn_frame = tk.Frame(info_dialog)
        btn_frame.pack(pady=(10, 20))
        tk.Button(btn_frame, text="닫기", command=info_dialog.destroy,
                  font=('맑은 고딕', 11), bg=self.colors['success'], fg='white',
                  padx=30, pady=8).pack()

    def show_source_info(self):
        source_dialog = tk.Toplevel(self.root)
        source_dialog.title("소스코드 정보")
        source_dialog.geometry("650x400")
        source_dialog.grab_set()
        source_dialog.resizable(False, False)

        frame = tk.Frame(source_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text_widget = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=('맑은 고딕', 10),
            bg='#f8f9fa', fg='#333333'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        source_text = """💻 소스코드 및 라이브러리 정보

🔹 핵심 라이브러리: evernote-backup
개발자: vzhd1701
GitHub: https://github.com/vzhd1701/evernote-backup
라이선스: MIT License

이 도구는 vzhd1701님이 개발한 evernote-backup 파이썬 라이브러리를 기반으로 
제작된 GUI 래퍼(wrapper) 프로그램입니다.

🔹 주요 구성요소

1. evernote-backup 라이브러리
   - 에버노트 OAuth 인증 처리
   - 노트 동기화 및 다운로드
   - ENEX 파일 생성 및 내보내기
   - Rate Limit 처리

2. GUI 인터페이스 (이 프로그램)
   - Python Tkinter 기반
   - 사용자 친화적인 단계별 인터페이스
   - 실시간 진행상황 및 Rate Limit 처리
   - 자동 경로 관리 및 안전성 검증

🔹 v2.0 개선사항
   - Rate Limit 자동 감지 및 처리
   - 실시간 진행률 표시 (노트 개수/백분율)
   - 자동 대기 및 재시도 기능
   - 향상된 오류 처리 및 사용자 안내

🔹 설치된 패키지 버전 확인
터미널에서 다음 명령어로 확인 가능:
pip show evernote-backup

🔹 라이브러리 설치 방법
pip install evernote-backup

🔹 커뮤니티 및 지원
- GitHub Issues: https://github.com/vzhd1701/evernote-backup/issues
- 문서: https://github.com/vzhd1701/evernote-backup/blob/main/README.md
"""

        text_widget.insert(tk.END, source_text)
        text_widget.config(state=tk.DISABLED)

        btn_frame = tk.Frame(source_dialog)
        btn_frame.pack(pady=(10, 20))
        
        tk.Button(btn_frame, text="🔗 GitHub 열기", 
                  command=lambda: webbrowser.open("https://github.com/vzhd1701/evernote-backup"),
                  font=('맑은 고딕', 11), bg=self.colors['primary'], fg='white',
                  padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(btn_frame, text="닫기", command=source_dialog.destroy,
                  font=('맑은 고딕', 11), bg=self.colors['success'], fg='white',
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
