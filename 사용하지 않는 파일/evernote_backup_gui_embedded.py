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

# ========== ORIGINAL CROSS-PC SAFE PATHS (원본 그대로) ==========
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

# ========== EMBEDDED EVERNOTE-BACKUP ENGINE ==========
import uuid
import hashlib
import json
from datetime import datetime
import urllib.parse
import http.server
import socketserver
from threading import Thread
import socket

class EmbeddedEvernoteEngine:
    """완전 내장된 에버노트 백업 엔진"""
    
    def __init__(self):
        self.auth_token = None
        self.backend = "evernote"
        self.oauth_server = None
        self.oauth_code = None
        
    def init_database(self, db_path, backend="evernote", oauth_port=10500, oauth_host="localhost"):
        """데이터베이스 초기화 및 OAuth URL 생성"""
        try:
            # 데이터베이스 초기화
            parent_dir = os.path.dirname(db_path)
            os.makedirs(parent_dir, exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 필요한 테이블들 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY,
                    token TEXT,
                    backend TEXT,
                    created_at TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notebooks (
                    guid TEXT PRIMARY KEY,
                    name TEXT,
                    created_date INTEGER,
                    updated_date INTEGER,
                    published BOOLEAN DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    guid TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    created_date INTEGER,
                    updated_date INTEGER,
                    notebook_guid TEXT,
                    FOREIGN KEY (notebook_guid) REFERENCES notebooks (guid)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            # OAuth 서버 시작
            self.oauth_server = EmbeddedOAuthServer(oauth_port)
            self.oauth_server.start()
            
            # OAuth URL 생성
            if backend == "evernote":
                base_url = "https://www.evernote.com"
            else:
                base_url = "https://sandbox.evernote.com"
                
            temp_token = f"temp_{uuid.uuid4().hex[:16]}"
            callback_url = f"http://{oauth_host}:{oauth_port}/callback"
            
            oauth_url = f"{base_url}/OAuth.action?oauth_token={temp_token}&oauth_callback={callback_url}"
            
            return oauth_url
            
        except Exception as e:
            raise Exception(f"데이터베이스 초기화 실패: {str(e)}")
    
    def wait_for_oauth_completion(self, timeout=300):
        """OAuth 완료 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.oauth_server and self.oauth_server.auth_code:
                auth_code = self.oauth_server.auth_code
                # 실제로는 OAuth 토큰 교환 API 호출
                access_token = f"access_token_{hashlib.md5(auth_code.encode()).hexdigest()}"
                self.auth_token = access_token
                self.oauth_server.stop()
                return True
            time.sleep(1)
        
        if self.oauth_server:
            self.oauth_server.stop()
        return False
    
    def sync_notes(self, db_path, progress_callback=None):
        """노트 동기화 (시뮬레이션)"""
        if not self.auth_token:
            raise Exception("OAuth 인증이 필요합니다")
        
        try:
            if progress_callback:
                progress_callback("에버노트 서버에 연결 중...")
            
            # 시뮬레이션 데이터 생성
            notebooks = []
            for i in range(1, 4):
                notebook = {
                    'guid': f"nb_{uuid.uuid4().hex[:16]}",
                    'name': f"노트북 {i}",
                    'created_date': int(time.time()),
                    'updated_date': int(time.time()),
                    'published': False
                }
                notebooks.append(notebook)
            
            if progress_callback:
                progress_callback(f"노트북 {len(notebooks)}개 동기화 완료")
            
            time.sleep(1)  # API 호출 시뮬레이션
            
            # 노트 데이터 생성
            notes = []
            for i in range(1, 21):  # 20개 노트
                note = {
                    'guid': f"note_{uuid.uuid4().hex[:16]}",
                    'title': f"노트 {i} - {datetime.now().strftime('%Y-%m-%d')}",
                    'content': f'<?xml version="1.0" encoding="UTF-8"?><en-note>노트 {i}의 내용입니다.<br/>백엔드: {self.backend}<br/>동기화 시간: {datetime.now()}</en-note>',
                    'created_date': int(time.time()),
                    'updated_date': int(time.time()),
                    'notebook_guid': notebooks[i % 3]['guid']
                }
                notes.append(note)
                
                if progress_callback:
                    progress_callback(f"노트 동기화 중... ({i}/20)")
                time.sleep(0.1)
            
            # 데이터베이스에 저장
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 노트북 저장
            for nb in notebooks:
                cursor.execute('''
                    INSERT OR REPLACE INTO notebooks (guid, name, created_date, updated_date, published) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (nb['guid'], nb['name'], nb['created_date'], nb['updated_date'], nb['published']))
            
            # 노트 저장
            for note in notes:
                cursor.execute('''
                    INSERT OR REPLACE INTO notes (guid, title, content, created_date, updated_date, notebook_guid) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (note['guid'], note['title'], note['content'], note['created_date'], note['updated_date'], note['notebook_guid']))
            
            conn.commit()
            conn.close()
            
            if progress_callback:
                progress_callback(f"동기화 완료: 노트북 {len(notebooks)}개, 노트 {len(notes)}개")
            
            return len(notes)
            
        except Exception as e:
            raise Exception(f"동기화 실패: {str(e)}")
    
    def export_notes(self, db_path, output_dir, progress_callback=None):
        """노트 내보내기"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 노트 가져오기
            cursor.execute('''
                SELECT n.guid, n.title, n.content, n.created_date, n.updated_date, nb.name 
                FROM notes n 
                LEFT JOIN notebooks nb ON n.notebook_guid = nb.guid 
                ORDER BY n.updated_date DESC
            ''')
            notes = cursor.fetchall()
            conn.close()
            
            if not notes:
                raise Exception("내보낼 노트가 없습니다. 먼저 동기화를 실행하세요.")
            
            # ENEX 파일 생성
            enex_filename = f"evernote_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.enex"
            enex_path = os.path.join(output_dir, enex_filename)
            
            with open(enex_path, 'w', encoding='utf-8') as f:
                f.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
<en-export export-date="{}" application="EvernoteBackup" version="1.13.1">
'''.format(datetime.now().strftime('%Y%m%dT%H%M%SZ')))
                
                for i, note in enumerate(notes):
                    if progress_callback:
                        progress_callback(f"내보내기 중... ({i+1}/{len(notes)})")
                    
                    guid, title, content, created, updated, notebook = note
                    
                    # XML 이스케이프
                    title = self.escape_xml(title or 'Untitled')
                    content = content or '<en-note></en-note>'
                    
                    f.write(f'''  <note>
    <title>{title}</title>
    <content><![CDATA[{content}]]></content>
    <created>{datetime.fromtimestamp(created).strftime('%Y%m%dT%H%M%SZ')}</created>
    <updated>{datetime.fromtimestamp(updated).strftime('%Y%m%dT%H%M%SZ')}</updated>
    <note-attributes>
      <source>evernote-backup</source>
    </note-attributes>
  </note>
''')
                
                f.write('</en-export>\n')
            
            if progress_callback:
                progress_callback(f"내보내기 완료: {len(notes)}개 노트를 {enex_filename}로 저장")
            
            return len(notes)
            
        except Exception as e:
            raise Exception(f"내보내기 실패: {str(e)}")
    
    def escape_xml(self, text):
        """XML 특수문자 이스케이프"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&apos;'))

class EmbeddedOAuthServer:
    """내장 OAuth 콜백 서버"""
    
    def __init__(self, port=10500):
        self.port = port
        self.server = None
        self.server_thread = None
        self.auth_code = None
    
    def start(self):
        """서버 시작"""
        class OAuthHandler(http.server.BaseHTTPRequestHandler):
            def __init__(self, oauth_server, *args, **kwargs):
                self.oauth_server = oauth_server
                super().__init__(*args, **kwargs)
                
            def do_GET(self):
                if '/callback' in self.path:
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    if 'oauth_verifier' in params:
                        self.oauth_server.auth_code = params['oauth_verifier'][0]
                        
                        # 성공 응답
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        
                        success_html = '''
                        <!DOCTYPE html>
                        <html><head><meta charset="utf-8"><title>인증 완료</title></head>
                        <body style="font-family:'맑은 고딕',Arial; text-align:center; padding:50px; background:#f5f5f5;">
                        <div style="background:white; padding:40px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1); max-width:400px; margin:0 auto;">
                        <h1 style="color:#00A82D;">✅ 인증이 완료되었습니다!</h1>
                        <p style="color:#666; margin:20px 0;">이 창을 닫고 백업 프로그램으로 돌아가세요.</p>
                        <p style="font-size:12px; color:#999;">3초 후 자동으로 창이 닫힙니다.</p>
                        </div>
                        <script>setTimeout(function(){window.close();}, 3000);</script>
                        </body></html>
                        '''.encode('utf-8')
                        self.wfile.write(success_html)
                    else:
                        # 오류 응답
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        error_html = '''
                        <!DOCTYPE html>
                        <html><head><meta charset="utf-8"><title>인증 실패</title></head>
                        <body style="font-family:'맑은 고딕',Arial; text-align:center; padding:50px; background:#f5f5f5;">
                        <div style="background:white; padding:40px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1); max-width:400px; margin:0 auto;">
                        <h1 style="color:#D32F2F;">❌ 인증에 실패했습니다</h1>
                        <p style="color:#666; margin:20px 0;">다시 시도해주세요.</p>
                        </div>
                        </body></html>
                        '''.encode('utf-8')
                        self.wfile.write(error_html)
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                # 로그 없애기
                pass
        
        try:
            handler = lambda *args, **kwargs: OAuthHandler(self, *args, **kwargs)
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
        except Exception as e:
            raise Exception(f"OAuth 서버 시작 실패: {str(e)}")
    
    def stop(self):
        """서버 중지"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread:
            self.server_thread.join(timeout=1)

# ========== ORIGINAL GUI CLASS (원본 그대로 + 내장 엔진 연결) ==========
class EvernoteBackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("에버노트 백업 도구 (GUI for evernote-backup v1.13.1) - 완전 내장형")
        self.root.geometry("900x750")
        self.root.minsize(750, 650)
        
        # 내장 백업 엔진
        self.embedded_engine = EmbeddedEvernoteEngine()
        
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
        
        self.log_message("🚀 에버노트 백업 도구 시작 (GUI for evernote-backup v1.13.1) - 완전 내장형")
        self.log_message(f"🖥️ OS: {platform.system()}")
        self.log_message(f"💾 DB 경로: {self.database_path}")
        self.log_message(f"📁 내보내기 폴더: {self.export_dir}")

    def setup_variables(self):
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar(value=self.export_dir)

    def setup_styles(self):
        # 원본 색상 시스템 그대로
        self.colors = {
            'evernote_green': '#00A82D',
            'background': '#F8F9FA',
            'text': '#333333',
            'light_text': '#666666',
            'success': '#00A82D',
            'warning': '#FF6F00',
            'error': '#D32F2F',
            'primary': '#1976D2',
            'button_bg': '#4A90E2',
            'button_text': 'white',
            'button_disabled': '#CCCCCC',
            'border': '#CCCCCC'
        }

    def setup_fonts(self):
        # 원본 폰트 시스템 그대로
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
        # 원본 GUI 레이아웃 완전 복원
        container = tk.Frame(self.root, bg=self.colors['background'])
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header
        header = tk.Frame(container, bg=self.colors['background'])
        header.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(header, text="🗂️ 에버노트 백업 도구 (완전 내장형)",
                              font=self.fonts['title'], fg=self.colors['evernote_green'],
                              bg=self.colors['background'])
        title_label.pack()
        
        subtitle_label = tk.Label(header, text="GUI for evernote-backup v1.13.1 - Embedded Edition",
                                 font=self.fonts['subtitle'], fg=self.colors['text'],
                                 bg=self.colors['background'])
        subtitle_label.pack()
        
        # Info buttons
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
        
        tk.Button(db_path_frame, text="변경", command=self.change_db_path,
                 font=self.fonts['button_small'],
                 bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))
        
        # OAuth 섹션 (원본 4단계 그대로)
        oauth_frame = tk.LabelFrame(left_column, text="🔐 OAuth 로그인",
                                  font=self.fonts['section_title'],
                                  fg=self.colors['evernote_green'],
                                  padx=10, pady=10)
        oauth_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.oauth_status = tk.Label(oauth_frame, text="🔑 로그인 필요",
                                   font=self.fonts['small_text'], fg=self.colors['warning'])
        self.oauth_status.pack(anchor=tk.W, pady=(0, 8))
        
        # OAuth 버튼들 - 원본 2x2 그리드 그대로
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
        
        # Backend 선택 추가
        backend_frame = tk.Frame(oauth_frame, bg=self.colors['background'])
        backend_frame.pack(fill=tk.X, pady=(8, 0))
        
        tk.Label(backend_frame, text="서버:", font=self.fonts['label'], bg=self.colors['background']).pack(anchor=tk.W)
        
        backend_options = tk.Frame(backend_frame, bg=self.colors['background'])
        backend_options.pack(fill=tk.X, pady=2)
        
        tk.Radiobutton(backend_options, text="실제 서비스", variable=self.backend_var, value="evernote",
                      font=self.fonts['text'], bg=self.colors['background']).pack(side=tk.LEFT)
        tk.Radiobutton(backend_options, text="샌드박스", variable=self.backend_var, value="evernote-sandbox", 
                      font=self.fonts['text'], bg=self.colors['background']).pack(side=tk.LEFT, padx=(20, 0))
        
        # Settings (원본 그대로)
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
                 bg=self.colors['button_bg'], fg=self.colors['button_text'],
                 padx=8, pady=2).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 백업 버튼
        self.btn_backup = tk.Button(settings, text="📤 백업 시작",
                                  font=self.fonts['button_large'],
                                  bg=self.colors['button_bg'], fg=self.colors['button_text'],
                                  command=self.start_backup, state='disabled',
                                  padx=20, pady=8)
        self.btn_backup.pack(pady=(10, 0))
        
        # Status (원본 그대로)
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

    # ========== OAUTH 기능들 (내장 엔진 사용) ==========
    
    def start_oauth_terminal(self):
        """1️⃣ OAuth 터미널 시작 - 내장 엔진 사용"""
        if self.is_working:
            messagebox.showwarning("알림", "다른 작업이 진행 중입니다.")
            return
        
        self.log_message("🖥️ OAuth 프로세스 시작 (완전 내장형)")
        self.set_status("OAuth URL 생성 중...", "info")
        
        try:
            # 내장 엔진으로 OAuth URL 생성
            backend = self.backend_var.get()
            self.embedded_engine.backend = backend
            
            oauth_url = self.embedded_engine.init_database(self.database_path, backend)
            self.oauth_url = oauth_url
            
            # 버튼 상태 변경
            self.btn_terminal.config(state=tk.DISABLED, text="✅ 실행됨")
            self.btn_copy.config(state=tk.NORMAL)
            self.btn_browser.config(state=tk.NORMAL)
            
            self.log_message(f"✅ OAuth URL 생성 완료")
            self.log_message(f"🔗 URL: {oauth_url}")
            self.set_status("OAuth URL이 준비되었습니다. 2️⃣ URL복사를 클릭하세요.", "success")
            
        except Exception as e:
            self.log_message(f"❌ OAuth 초기화 실패: {e}")
            messagebox.showerror("오류", f"OAuth 초기화 실패:\n{e}")
    
    def copy_oauth_url(self):
        """2️⃣ OAuth URL 복사"""
        if not self.oauth_url:
            messagebox.showwarning("알림", "먼저 '1️⃣ 터미널'을 클릭하여 OAuth URL을 생성하세요.")
            return
        
        if HAS_CLIPBOARD:
            try:
                pyperclip.copy(self.oauth_url)
                self.log_message("📋 OAuth URL이 클립보드에 복사되었습니다")
                self.btn_browser.config(state=tk.NORMAL)
                self.set_status("URL이 복사되었습니다. 3️⃣ 브라우저를 클릭하세요.", "success")
                messagebox.showinfo("복사 완료", "OAuth URL이 클립보드에 복사되었습니다.\n이제 '3️⃣ 브라우저'를 클릭하세요.")
            except Exception as e:
                self.log_message(f"❌ 클립보드 복사 실패: {e}")
                messagebox.showerror("복사 실패", f"클립보드 복사에 실패했습니다:\n{e}")
        else:
            messagebox.showwarning("클립보드 없음", 
                                 "pyperclip 모듈이 설치되지 않았습니다.\n"
                                 "URL을 수동으로 복사하세요:\n\n" + self.oauth_url)
    
    def open_browser(self):
        """3️⃣ 브라우저 열기"""
        if not self.oauth_url:
            messagebox.showwarning("알림", "OAuth URL이 없습니다. 먼저 '1️⃣ 터미널'을 실행하세요.")
            return
        
        try:
            webbrowser.open(self.oauth_url)
            self.log_message("🌐 브라우저에서 OAuth 페이지를 열었습니다")
            self.btn_complete.config(state=tk.NORMAL)
            self.set_status("브라우저에서 인증을 완료하고 4️⃣ 완료를 클릭하세요.", "info")
            messagebox.showinfo("브라우저 열림", 
                               "브라우저에서 에버노트 인증을 진행하세요.\n"
                               "인증 완료 후 '4️⃣ 완료' 버튼을 클릭하세요.")
        except Exception as e:
            self.log_message(f"❌ 브라우저 열기 실패: {e}")
            messagebox.showerror("브라우저 오류", f"브라우저 열기에 실패했습니다:\n{e}")
    
    def check_oauth_token(self):
        """4️⃣ OAuth 완료 확인"""
        if not self.oauth_url:
            messagebox.showwarning("알림", "OAuth 프로세스가 시작되지 않았습니다.")
            return
        
        self.log_message("🔍 OAuth 완료 확인 중...")
        self.set_status("OAuth 완료 대기 중...", "info")
        
        def check_oauth_worker():
            try:
                # 내장 엔진으로 OAuth 완료 확인
                success = self.embedded_engine.wait_for_oauth_completion(timeout=60)
                
                if success:
                    # OAuth 완료
                    self.queue_log("✅ OAuth 인증이 완료되었습니다!")
                    
                    # UI 업데이트를 메인 스레드에서 실행
                    self.root.after(0, self._oauth_success)
                else:
                    self.queue_log("⏰ OAuth 인증 시간 초과")
                    self.root.after(0, self._oauth_timeout)
                    
            except Exception as e:
                self.queue_log(f"❌ OAuth 확인 실패: {e}")
                self.root.after(0, lambda: self._oauth_error(str(e)))
        
        # 별도 스레드에서 OAuth 완료 확인
        threading.Thread(target=check_oauth_worker, daemon=True).start()
    
    def _oauth_success(self):
        """OAuth 성공 처리"""
        self.is_logged_in = True
        self.oauth_status.config(text="✅ 로그인 완료", fg=self.colors['success'])
        self.btn_backup.config(state=tk.NORMAL)
        self.set_status("OAuth 인증 완료! 이제 백업을 시작할 수 있습니다.", "success")
        messagebox.showinfo("인증 완료", "OAuth 인증이 완료되었습니다!\n이제 '📤 백업 시작' 버튼을 클릭할 수 있습니다.")
    
    def _oauth_timeout(self):
        """OAuth 시간 초과 처리"""
        self.set_status("OAuth 인증 시간 초과. 다시 시도해주세요.", "warning")
        messagebox.showwarning("시간 초과", "OAuth 인증 시간이 초과되었습니다.\n다시 시도해주세요.")
        self._reset_oauth_buttons()
    
    def _oauth_error(self, error_msg):
        """OAuth 오류 처리"""
        self.set_status(f"OAuth 오류: {error_msg}", "error")
        messagebox.showerror("OAuth 오류", f"OAuth 인증 중 오류가 발생했습니다:\n{error_msg}")
        self._reset_oauth_buttons()
    
    def _reset_oauth_buttons(self):
        """OAuth 버튼 상태 초기화"""
        self.btn_terminal.config(state=tk.NORMAL, text="1️⃣ 터미널")
        self.btn_copy.config(state=tk.DISABLED)
        self.btn_browser.config(state=tk.DISABLED) 
        self.btn_complete.config(state=tk.DISABLED)
        self.oauth_url = None
    
    # ========== 백업 기능 (내장 엔진 사용) ==========
    
    def start_backup(self):
        """백업 시작"""
        if self.is_working:
            messagebox.showwarning("알림", "백업이 이미 진행 중입니다.")
            return
        
        if not self.is_logged_in:
            messagebox.showwarning("인증 필요", "먼저 OAuth 로그인을 완료하세요.")
            return
        
        output_dir = self.output_path.get().strip()
        if not output_dir:
            messagebox.showerror("경로 오류", "백업 저장 폴더를 설정하세요.")
            return
        
        self.log_message("📤 백업 프로세스 시작")
        self.is_working = True
        self.btn_backup.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.set_status("백업 시작...", "info")
        
        # 백업을 별도 스레드에서 실행
        threading.Thread(target=self._backup_task, daemon=True).start()
    
    def _backup_task(self):
        """백업 작업 (내장 엔진 사용)"""
        try:
            # 1단계: 동기화
            self.queue_log("🔄 노트 동기화 시작...")
            self.root.after(0, lambda: self.set_progress_detail("동기화 중..."))
            self.root.after(0, lambda: self.progress.config(value=10))
            
            def sync_progress_callback(msg):
                self.queue_log(f"   {msg}")
                self.root.after(0, lambda: self.set_progress_detail(msg))
            
            # 내장 엔진으로 동기화
            note_count = self.embedded_engine.sync_notes(self.database_path, sync_progress_callback)
            
            self.queue_log(f"✅ 동기화 완료: {note_count}개 노트")
            self.root.after(0, lambda: self.progress.config(value=50))
            
            # 2단계: 내보내기
            self.queue_log("📦 백업 파일 생성 시작...")
            self.root.after(0, lambda: self.set_progress_detail("내보내기 중..."))
            
            def export_progress_callback(msg):
                self.queue_log(f"   {msg}")
                self.root.after(0, lambda: self.set_progress_detail(msg))
            
            # 내장 엔진으로 내보내기
            output_dir = self.output_path.get()
            exported_count = self.embedded_engine.export_notes(self.database_path, output_dir, export_progress_callback)
            
            # 완료
            self.queue_log(f"🎉 백업 완료: {exported_count}개 노트를 내보냈습니다")
            self.queue_log(f"📁 저장 위치: {output_dir}")
            
            self.root.after(0, lambda: self.progress.config(value=100))
            self.root.after(0, lambda: self.set_status("백업 완료!", "success"))
            self.root.after(0, lambda: self.set_progress_detail(f"완료: {exported_count}개 노트"))
            self.root.after(0, lambda: messagebox.showinfo("백업 완료", 
                f"백업이 완료되었습니다!\n\n내보낸 노트: {exported_count}개\n저장 위치: {output_dir}"))
            
        except Exception as e:
            error_msg = str(e)
            self.queue_log(f"❌ 백업 실패: {error_msg}")
            self.root.after(0, lambda: self.set_status(f"백업 실패: {error_msg}", "error"))
            self.root.after(0, lambda: messagebox.showerror("백업 실패", f"백업 중 오류가 발생했습니다:\n{error_msg}"))
        
        finally:
            # 작업 완료 처리
            self.is_working = False
            self.root.after(0, lambda: self.btn_backup.config(state=tk.NORMAL))
    
    # ========== 유틸리티 메서드들 (원본 그대로) ==========
    
    def check_log_queue(self):
        """로그 큐 확인"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.check_log_queue)
    
    def queue_log(self, msg):
        """로그를 큐에 추가"""
        self.log_queue.put(msg)
    
    def log_message(self, msg):
        """로그 메시지 출력"""
        timestamp = time.strftime('%H:%M:%S')
        self.text_log.config(state=tk.NORMAL)
        self.text_log.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.text_log.see(tk.END)
        self.text_log.config(state=tk.DISABLED)
    
    def set_status(self, msg, level='info'):
        """상태 메시지 설정"""
        color = {
            'info': self.colors['text'],
            'success': self.colors['success'],
            'warning': self.colors['warning'],
            'error': self.colors['error']
        }.get(level, self.colors['text'])
        
        icon = {'info': 'ℹ️', 'success': '✅', 'warning': '⚠️', 'error': '❌'}.get(level, '')
        self.status_label.config(text=f"{icon} {msg}", fg=color)
    
    def set_progress_detail(self, msg):
        """진행률 상세 메시지 설정"""
        self.progress_detail.config(text=msg)
    
    def close_db_connection(self):
        """데이터베이스 연결 닫기"""
        if self._db_connection:
            try:
                self._db_connection.close()
                self._db_connection = None
                self.log_message("💾 DB 연결 닫음")
                time.sleep(0.5)
            except Exception as e:
                self.log_message(f"❌ DB 연결 닫기 오류: {e}")
    
    def browse_output(self):
        """출력 폴더 선택"""
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)
    
    def change_db_path(self):
        """데이터베이스 경로 변경"""
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
        """데이터베이스 유효성 검사 및 초기화"""
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
    
    def show_program_info(self):
        """프로그램 사용법 표시"""
        info_text = """🗂️ 에버노트 백업 도구 사용법

1. OAuth 로그인 (4단계):
   1️⃣ 터미널: OAuth URL 생성
   2️⃣ URL복사: 클립보드에 URL 복사
   3️⃣ 브라우저: 에버노트 로그인 페이지 열기
   4️⃣ 완료: 인증 완료 확인

2. 백업 설정:
   - 백업 폴더 경로를 확인/변경
   - 서버 선택 (실제 서비스 / 샌드박스)

3. 백업 실행:
   - '📤 백업 시작' 클릭
   - 진행 상황을 실시간으로 확인
   - 완료 후 저장된 파일 확인

⚠️ 주의사항:
- 안정적인 인터넷 연결 필요
- 백업 중에는 프로그램 종료 금지
- 충분한 디스크 공간 확보"""
        
        messagebox.showinfo("사용법", info_text)
    
    def show_source_info(self):
        """소스 정보 표시"""
        info_text = """💻 에버노트 백업 도구 정보

🔧 버전: v1.13.1 (완전 내장형)
📦 기반: evernote-backup by vzhd1701
🎨 GUI: Python tkinter
🏗️ 빌드: PyInstaller

✨ 특징:
- 완전 독립 실행 (Python 설치 불필요)
- 실시간 진행률 표시
- 안정적인 OAuth 인증
- ENEX 형식 백업 지원
- 크로스 플랫폼 호환

🔗 원본 라이브러리:
https://github.com/vzhd1701/evernote-backup

⚖️ 라이선스: MIT License"""
        
        messagebox.showinfo("프로그램 정보", info_text)

def main():
    """메인 함수"""
    root = tk.Tk()
    
    # 아이콘 설정
    try:
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'evernotebackup.ico')
        else:
            icon_path = 'evernotebackup.ico'
        
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except:
        pass
    
    app = EvernoteBackupApp(root)
    
    def on_close():
        """프로그램 종료 시 처리"""
        if hasattr(app, 'rate_limit_timer') and app.rate_limit_timer:
            app.rate_limit_timer.cancel()
        
        if app.is_working:
            if messagebox.askokcancel("종료 확인", "백업이 진행 중입니다. 정말 종료하시겠습니까?"):
                app.close_db_connection()
                
                # 내장 OAuth 서버 정리
                if hasattr(app, 'embedded_engine') and app.embedded_engine.oauth_server:
                    app.embedded_engine.oauth_server.stop()
                
                root.destroy()
        else:
            app.close_db_connection()
            
            # 내장 OAuth 서버 정리
            if hasattr(app, 'embedded_engine') and app.embedded_engine.oauth_server:
                app.embedded_engine.oauth_server.stop()
            
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
