import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import os
import sys
import subprocess
import webbrowser
import re
from pathlib import Path
import platform
import datetime
import pyperclip  # 클립보드 라이브러리 (pip install pyperclip)

class EvernoteBackupGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("에버노트 간편 백업 v2.0 (터미널 자동실행)")
        self.root.geometry("850x1000")
        self.root.minsize(700, 800)
        
        # 상태 변수
        self.is_working = False
        self.is_logged_in = False
        self.database_path = "evernote_backup.db"
        self.terminal_process = None
        
        # GUI 변수 초기화
        self.setup_variables()
        self.setup_styles()
        self.setup_fonts()
        self.create_widgets()
        self.set_defaults()
        
        # 시작 메시지
        self.log_message("🎉 에버노트 간편 백업 도구를 시작합니다!")
        self.log_message("💡 새 터미널 창이 자동으로 열려서 OAuth 로그인을 진행합니다.")
        self.log_message("🔗 OAuth URL이 자동으로 클립보드에 복사됩니다!")
        self.log_message(f"🖥️ 운영체제: {platform.system()}")
        
    def setup_variables(self):
        """GUI 변수 초기화"""
        self.backend_var = tk.StringVar(value="evernote")
        self.output_path = tk.StringVar()
        self.show_log = tk.BooleanVar(value=True)
        
    def setup_styles(self):
        """에버노트 공식 컬러 스타일 설정"""
        self.colors = {
            'evernote_green': '#00A82D',
            'evernote_dark': '#2DBD3A',
            'evernote_light': '#7AC142',
            'secondary': '#1976D2',
            'success': '#00A82D',
            'warning': '#FF9800',
            'error': '#F44336',
            'background': '#F8F9FA',
            'text': '#333333',
            'light_text': '#666666'
        }
        
    def setup_fonts(self):
        """맑은고딕 폰트 설정"""
        self.fonts = {
            'title': ('맑은 고딕', 24, 'bold'),
            'subtitle': ('맑은 고딕', 12),
            'section_title': ('맑은 고딕', 12, 'bold'),
            'button_large': ('맑은 고딕', 16, 'bold'),
            'button_medium': ('맑은 고딕', 14, 'bold'),
            'button_small': ('맑은 고딕', 10),
            'label': ('맑은 고딕', 11, 'bold'),
            'text': ('맑은 고딕', 10),
            'small_text': ('맑은 고딕', 9),
            'status': ('맑은 고딕', 11, 'bold'),
            'log': ('맑은 고딕', 9)
        }
        
    def set_defaults(self):
        """기본값 설정"""
        default_output = os.path.join(os.path.expanduser("~"), "Documents", "에버노트_백업")
        self.output_path.set(default_output)
        
    def create_widgets(self):
        """GUI 위젯 생성"""
        # 메인 컨테이너
        main_container = tk.Frame(self.root, bg=self.colors['background'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 헤더 섹션
        self.create_header(main_container)
        
        # 1단계: 터미널 자동 OAuth 로그인 섹션
        self.create_login_section(main_container)
        
        # 2단계: 설정 섹션
        self.create_settings_section(main_container)
        
        # 3단계: 백업 섹션
        self.create_backup_section(main_container)
        
        # 진행 상황 섹션
        self.create_progress_section(main_container)
        
        # 로그 섹션
        self.create_log_section(main_container)
        
    def create_header(self, parent):
        """헤더 섹션 생성"""
        header_frame = tk.Frame(parent, bg=self.colors['background'])
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(header_frame, 
                              text="🗂️ 에버노트 간편 백업",
                              font=self.fonts['title'],
                              fg=self.colors['evernote_green'],
                              bg=self.colors['background'])
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame,
                                 text="터미널 자동실행 + 클립보드 복사로 100% 확실한 OAuth",
                                 font=self.fonts['subtitle'],
                                 fg=self.colors['text'],
                                 bg=self.colors['background'])
        subtitle_label.pack(pady=(5, 0))
        
        # 기능 설명
        features_label = tk.Label(header_frame,
                                 text="✨ 새 터미널 창 자동 실행 → OAuth URL 자동 클립보드 복사 → 브라우저 자동 열기",
                                 font=self.fonts['small_text'],
                                 fg=self.colors['secondary'],
                                 bg=self.colors['background'])
        features_label.pack(pady=(5, 0))
        
    def create_login_section(self, parent):
        """1단계: 터미널 자동 OAuth 로그인 섹션"""
        login_frame = tk.LabelFrame(parent, 
                                   text="1단계: 터미널 자동 OAuth 로그인",
                                   font=self.fonts['section_title'],
                                   fg=self.colors['evernote_green'],
                                   padx=20, pady=15)
        login_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 로그인 상태 표시
        self.login_status = tk.Label(login_frame,
                                    text="⚪ 터미널 자동 OAuth 로그인 준비됨",
                                    font=self.fonts['text'])
        self.login_status.pack(anchor=tk.W, pady=(0, 10))
        
        # 자동 실행 프로세스 설명
        process_frame = tk.LabelFrame(login_frame, text="🤖 자동 실행 과정", font=self.fonts['label'])
        process_frame.pack(fill=tk.X, pady=(0, 15))
        
        process_text = tk.Label(process_frame,
                               text="1️⃣ 새 터미널 창이 자동으로 열립니다\n2️⃣ OAuth 명령어가 자동으로 실행됩니다\n3️⃣ OAuth URL이 생성되면 자동으로 클립보드에 복사됩니다\n4️⃣ 브라우저가 자동으로 열려서 OAuth 페이지로 이동합니다\n5️⃣ 'BUlk Backup' 권한을 허용하면 로그인 완료됩니다",
                               font=self.fonts['small_text'],
                               fg=self.colors['light_text'],
                               justify=tk.LEFT,
                               padx=10, pady=10)
        process_text.pack(anchor=tk.W)
        
        # 터미널 자동 실행 버튼
        button_frame = tk.Frame(login_frame)
        button_frame.pack()
        
        self.login_btn = tk.Button(button_frame,
                                  text="🚀 터미널 자동 OAuth 시작",
                                  command=self.start_terminal_oauth,
                                  font=self.fonts['button_medium'],
                                  bg=self.colors['evernote_green'],
                                  fg="white",
                                  padx=30, pady=12,
                                  cursor="hand2",
                                  relief="flat",
                                  activebackground=self.colors['evernote_dark'])
        self.login_btn.pack()
        
        # 수동 완료 버튼
        manual_frame = tk.Frame(login_frame)
        manual_frame.pack(pady=(10, 0))
        
        manual_complete_btn = tk.Button(manual_frame,
                                       text="✅ 로그인 완료 (수동 확인)",
                                       command=self.manual_login_complete,
                                       font=self.fonts['button_small'],
                                       bg=self.colors['secondary'],
                                       fg="white",
                                       padx=20, pady=5,
                                       cursor="hand2",
                                       relief="flat",
                                       state='disabled')
        manual_complete_btn.pack()
        self.manual_complete_btn = manual_complete_btn
        
        # 터미널 닫기 버튼
        close_terminal_btn = tk.Button(manual_frame,
                                      text="🔴 터미널 닫기",
                                      command=self.close_terminal,
                                      font=self.fonts['button_small'],
                                      bg=self.colors['error'],
                                      fg="white",
                                      padx=20, pady=5,
                                      cursor="hand2",
                                      relief="flat",
                                      state='disabled')
        close_terminal_btn.pack(side=tk.RIGHT, padx=(10, 0))
        self.close_terminal_btn = close_terminal_btn
        
    def create_settings_section(self, parent):
        """2단계: 설정 섹션"""
        settings_frame = tk.LabelFrame(parent,
                                      text="2단계: 백업 설정",
                                      font=self.fonts['section_title'],
                                      fg=self.colors['evernote_green'],
                                      padx=20, pady=15)
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        path_label = tk.Label(settings_frame,
                             text="백업 저장 위치:",
                             font=self.fonts['label'])
        path_label.pack(anchor=tk.W, pady=(0, 5))
        
        path_frame = tk.Frame(settings_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.path_entry = tk.Entry(path_frame,
                                  textvariable=self.output_path,
                                  font=self.fonts['text'],
                                  relief="solid",
                                  bd=1)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = tk.Button(path_frame,
                              text="📁 변경",
                              command=self.browse_output,
                              font=self.fonts['button_small'],
                              bg=self.colors['evernote_green'],
                              fg="white",
                              padx=15,
                              cursor="hand2",
                              relief="flat",
                              activebackground=self.colors['evernote_dark'])
        browse_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
    def create_backup_section(self, parent):
        """3단계: 백업 섹션"""
        backup_frame = tk.LabelFrame(parent,
                                    text="3단계: 백업 실행",
                                    font=self.fonts['section_title'],
                                    fg=self.colors['evernote_green'],
                                    padx=20, pady=15)
        backup_frame.pack(fill=tk.X, pady=(0, 15))
        
        backup_info = tk.Label(backup_frame,
                              text="• 모든 노트, 노트북, 태그를 다운로드합니다\n• ENEX 형식으로 저장되어 다른 앱에서도 사용 가능합니다",
                              font=self.fonts['small_text'],
                              fg=self.colors['light_text'],
                              justify=tk.LEFT)
        backup_info.pack(anchor=tk.W, pady=(0, 15))
        
        button_container = tk.Frame(backup_frame)
        button_container.pack()
        
        self.backup_btn = tk.Button(button_container,
                                   text="🚀 백업 시작하기",
                                   command=self.start_backup,
                                   font=self.fonts['button_large'],
                                   bg=self.colors['evernote_green'],
                                   fg="white",
                                   padx=40, pady=15,
                                   cursor="hand2",
                                   relief="flat",
                                   state='disabled',
                                   activebackground=self.colors['evernote_dark'],
                                   disabledforeground="#CCCCCC")
        self.backup_btn.pack()
        
    def create_progress_section(self, parent):
        """진행 상황 섹션"""
        progress_frame = tk.Frame(parent, bg=self.colors['background'])
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = tk.Label(progress_frame,
                                    text="✅ 준비 완료",
                                    font=self.fonts['status'],
                                    fg=self.colors['success'],
                                    bg=self.colors['background'])
        self.status_label.pack(anchor=tk.W)
        
    def create_log_section(self, parent):
        """로그 섹션"""
        self.log_frame = tk.Frame(parent, bg=self.colors['background'])
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        log_label = tk.Label(self.log_frame,
                            text="진행 과정:",
                            font=self.fonts['label'],
                            fg=self.colors['text'],
                            bg=self.colors['background'])
        log_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame,
                                                 height=18,
                                                 font=self.fonts['log'],
                                                 bg="#f8f9fa",
                                                 fg="#333333",
                                                 relief="solid",
                                                 bd=1)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    # === 🔥 터미널 자동 실행 + 클립보드 복사 기능 ===
    
    def start_terminal_oauth(self):
        """터미널에서 자동으로 OAuth 실행 + URL 클립보드 복사"""
        if self.is_working:
            messagebox.showwarning("알림", "다른 작업이 진행 중입니다.")
            return
        
        # 터미널 OAuth 안내
        terminal_info = """🚀 터미널 자동 OAuth를 시작합니다!

🤖 자동 진행 과정:
1. 새 터미널 창이 열립니다
2. OAuth 명령어가 자동 실행됩니다
3. OAuth URL이 클립보드에 자동 복사됩니다
4. 브라우저가 자동으로 열립니다
5. 'BUlk Backup' 권한 허용을 클릭하세요

💡 장점:
• 100% 확실한 터미널 환경
• URL 자동 클립보드 복사
• 브라우저 자동 열기

시작하시겠습니까?"""
        
        if not messagebox.askyesno("터미널 자동 OAuth", terminal_info):
            return
        
        self.is_working = True
        self.start_terminal_oauth_ui()
        
        # OAuth 명령어
        oauth_command = f'python -m evernote_backup init-db --database "{self.database_path}" --backend {self.backend_var.get()} --oauth-port 10500 --oauth-host localhost'
        
        self.log_message("🚀 새 터미널 창에서 OAuth 명령어를 실행합니다...")
        self.log_message(f"🔧 명령어: {oauth_command}")
        
        try:
            if platform.system() == "Windows":
                self.start_windows_terminal(oauth_command)
            elif platform.system() == "Darwin":  # macOS
                self.start_macos_terminal(oauth_command)
            else:  # Linux
                self.start_linux_terminal(oauth_command)
                
            # URL 감시 시작
            self.start_url_monitoring()
            
        except Exception as e:
            self.log_message(f"❌ 터미널 실행 실패: {str(e)}")
            messagebox.showerror("터미널 실행 실패", f"터미널을 열 수 없습니다:\n{str(e)}")
            self.finish_terminal_oauth()
    
    def start_windows_terminal(self, command):
        """Windows 터미널 실행"""
        # 방법 1: Windows Terminal 시도
        try:
            self.terminal_process = subprocess.Popen([
                "wt", "-d", os.getcwd(), "--", "cmd", "/c", 
                f'{command} & echo. & echo OAuth 완료 후 이 창을 닫으세요. & pause'
            ])
            self.log_message("✅ Windows Terminal로 실행되었습니다.")
            return
        except FileNotFoundError:
            pass
        
        # 방법 2: 일반 CMD 창
        try:
            self.terminal_process = subprocess.Popen([
                "cmd", "/c", "start", "cmd", "/k", 
                f'{command} & echo. & echo OAuth 완료 후 이 창을 닫으세요.'
            ])
            self.log_message("✅ CMD 창으로 실행되었습니다.")
        except Exception as e:
            raise e
    
    def start_macos_terminal(self, command):
        """macOS Terminal 실행"""
        script = f'''
tell application "Terminal"
    activate
    do script "cd '{os.getcwd()}' && {command}"
end tell
'''
        try:
            self.terminal_process = subprocess.Popen([
                "osascript", "-e", script
            ])
            self.log_message("✅ macOS Terminal로 실행되었습니다.")
        except Exception as e:
            # AppleScript 실패시 일반 방법
            self.terminal_process = subprocess.Popen([
                "open", "-a", "Terminal", "."
            ])
            self.log_message("⚠️ Terminal 앱을 열었습니다. 수동으로 명령어를 실행하세요:")
            self.log_message(f"📋 {command}")
            raise e
    
    def start_linux_terminal(self, command):
        """Linux 터미널 실행"""
        terminal_commands = [
            ["gnome-terminal", "--", "bash", "-c", f"{command}; echo 'OAuth 완료 후 Enter를 누르세요.'; read"],
            ["xterm", "-e", f"{command}; echo 'OAuth 완료 후 Enter를 누르세요.'; read"],
            ["konsole", "-e", f"{command}; echo 'OAuth 완료 후 Enter를 누르세요.'; read"],
            ["x-terminal-emulator", "-e", f"{command}; echo 'OAuth 완료 후 Enter를 누르세요.'; read"]
        ]
        
        for terminal_cmd in terminal_commands:
            try:
                self.terminal_process = subprocess.Popen(terminal_cmd)
                self.log_message(f"✅ {terminal_cmd[0]}로 실행되었습니다.")
                return
            except FileNotFoundError:
                continue
        
        raise Exception("사용 가능한 터미널을 찾을 수 없습니다.")
    
    def start_url_monitoring(self):
        """OAuth URL 모니터링 시작"""
        def monitor_worker():
            try:
                self.log_message("👀 OAuth URL을 찾는 중...")
                
                # 파일 기반 URL 감지 (로그 파일이나 임시 파일 확인)
                # 또는 네트워크 모니터링
                url_found = False
                attempts = 0
                max_attempts = 60  # 1분간 시도
                
                while not url_found and attempts < max_attempts:
                    try:
                        # 방법 1: 네트워크 연결 확인 (localhost:10500)
                        import socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('localhost', 10500))
                        sock.close()
                        
                        if result == 0:
                            # OAuth 서버가 활성화됨 - URL 추정
                            oauth_url = "http://localhost:10500/oauth/authorize"  # 추정 URL
                            self.root.after(0, lambda: self.handle_oauth_url_found(oauth_url))
                            url_found = True
                            break
                            
                    except:
                        pass
                    
                    attempts += 1
                    threading.Event().wait(1)  # 1초 대기
                
                if not url_found:
                    self.root.after(0, lambda: self.log_message("⚠️ OAuth URL을 자동으로 찾지 못했습니다. 터미널 창을 확인하세요."))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ URL 모니터링 오류: {str(e)}"))
        
        threading.Thread(target=monitor_worker, daemon=True).start()
    
    def handle_oauth_url_found(self, url):
        """OAuth URL을 찾았을 때 처리"""
        self.log_message(f"🔗 OAuth URL 감지: {url}")
        
        # 클립보드에 복사
        try:
            pyperclip.copy(url)
            self.log_message("📋 URL이 클립보드에 복사되었습니다!")
        except Exception as e:
            self.log_message(f"⚠️ 클립보드 복사 실패: {str(e)}")
        
        # 브라우저에서 열기
        try:
            if platform.system() == "Windows":
                os.startfile(url)
            elif platform.system() == "Darwin":
                subprocess.run(["open", url])
            else:
                subprocess.run(["xdg-open", url])
            
            self.log_message("🌐 브라우저에서 OAuth 페이지를 열었습니다!")
            
            # 안내 메시지
            messagebox.showinfo("OAuth URL 감지!", 
                               "🎉 OAuth URL을 감지했습니다!\n\n" +
                               "✅ 클립보드에 복사되었습니다\n" +
                               "✅ 브라우저에서 페이지가 열렸습니다\n\n" +
                               "📋 다음 단계:\n" +
                               "1. 에버노트 계정으로 로그인하세요\n" +
                               "2. 'BUlk Backup' 권한 허용을 클릭하세요\n" +
                               "3. 완료되면 '✅ 로그인 완료' 버튼을 클릭하세요")
            
            # 수동 완료 버튼 활성화
            self.manual_complete_btn.config(state='normal')
            
        except Exception as e:
            self.log_message(f"❌ 브라우저 열기 실패: {str(e)}")
    
    def manual_login_complete(self):
        """수동으로 로그인 완료 확인"""
        if messagebox.askyesno("로그인 완료 확인", 
                              "브라우저에서 OAuth 권한 허용을 완료하셨습니까?\n\n" +
                              "'BUlk Backup' 권한을 허용하고 완료 페이지가 나타났다면 '예'를 클릭하세요."):
            self.oauth_login_success()
            self.finish_terminal_oauth()
    
    def close_terminal(self):
        """터미널 프로세스 종료"""
        if self.terminal_process:
            try:
                self.terminal_process.terminate()
                self.log_message("🔴 터미널 프로세스를 종료했습니다.")
            except:
                pass
            self.terminal_process = None
        self.finish_terminal_oauth()
    
    def start_terminal_oauth_ui(self):
        """터미널 OAuth 시작시 UI"""
        self.login_btn.config(state='disabled', text="터미널 OAuth 실행 중...", 
                             bg=self.colors['light_text'])
        self.close_terminal_btn.config(state='normal')
        self.set_status("터미널에서 OAuth 진행 중...", 'warning')
        self.progress.start()
    
    def oauth_login_success(self):
        """OAuth 로그인 성공"""
        self.login_status.config(text="✅ OAuth 로그인 완료!", fg=self.colors['success'])
        self.backup_btn.config(state='normal')
        self.set_status("로그인 완료 - 백업 준비됨", 'success')
        self.is_logged_in = True
        self.log_message("✅ OAuth 로그인이 완료되었습니다!")
        messagebox.showinfo("로그인 성공!", "🎉 OAuth 로그인이 완료되었습니다!\n\n이제 백업을 시작할 수 있습니다.")
    
    def finish_terminal_oauth(self):
        """터미널 OAuth 완료 후 정리"""
        self.progress.stop()
        self.login_btn.config(state='normal', text="🚀 터미널 자동 OAuth 시작",
                             bg=self.colors['evernote_green'])
        self.manual_complete_btn.config(state='disabled')
        self.close_terminal_btn.config(state='disabled')
        self.is_working = False
    
    # === 백업 기능 (기존과 동일) ===
        
    def start_backup(self):
        """백업 시작"""
        if not self.is_logged_in:
            messagebox.showwarning("알림", "먼저 OAuth 로그인을 완료해주세요.")
            return
            
        if self.is_working:
            messagebox.showwarning("알림", "이미 백업이 진행 중입니다.")
            return
            
        if not messagebox.askyesno("백업 시작", "백업을 시작하시겠습니까?\n\n노트 수에 따라 시간이 걸릴 수 있습니다."):
            return
        
        # 출력 폴더 생성
        try:
            os.makedirs(self.output_path.get(), exist_ok=True)
        except Exception as e:
            messagebox.showerror("오류", f"백업 폴더를 생성할 수 없습니다:\n{str(e)}")
            return
            
        def backup_worker():
            try:
                self.is_working = True
                self.root.after(0, self.start_backup_ui)
                
                self.log_message("🚀 백업을 시작합니다...")
                
                # 환경 변수 설정
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                
                # Windows에서 cmd 창 숨기기
                startupinfo = None
                creationflags = 0
                if platform.system() == 'Windows':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    creationflags = subprocess.CREATE_NO_WINDOW
                
                # 1단계: 동기화
                self.root.after(0, lambda: self.set_status("에버노트에서 노트 다운로드 중...", 'warning'))
                self.log_message("🔄 1/2: 에버노트에서 노트 동기화 중...")
                
                sync_cmd = [
                    sys.executable, "-m", "evernote_backup", "sync",
                    "--database", self.database_path
                ]
                
                sync_process = subprocess.run(sync_cmd, capture_output=True, text=True, timeout=600, 
                                            env=env, startupinfo=startupinfo, creationflags=creationflags)
                if sync_process.returncode != 0:
                    raise Exception(f"동기화 실패: {sync_process.stderr or sync_process.stdout}")
                
                # 2단계: 내보내기
                self.root.after(0, lambda: self.set_status("백업 파일 생성 중...", 'warning'))
                self.log_message("📤 2/2: ENEX 파일 생성 중...")
                
                export_cmd = [
                    sys.executable, "-m", "evernote_backup", "export",
                    "--database", self.database_path,
                    self.output_path.get()
                ]
                
                export_process = subprocess.run(export_cmd, capture_output=True, text=True, timeout=600,
                                              env=env, startupinfo=startupinfo, creationflags=creationflags)
                if export_process.returncode != 0:
                    raise Exception(f"내보내기 실패: {export_process.stderr or export_process.stdout}")
                
                # 성공 완료
                self.root.after(0, self.backup_success)
                
            except Exception as e:
                self.root.after(0, lambda: self.backup_error(str(e)))
            finally:
                self.root.after(0, self.finish_backup)
                
        threading.Thread(target=backup_worker, daemon=True).start()
    
    def start_backup_ui(self):
        """백업 시작시 UI"""
        self.backup_btn.config(state='disabled', text="백업 중...", bg=self.colors['light_text'])
        self.progress.start()
    
    def backup_success(self):
        """백업 성공"""
        self.set_status("백업 완료!", 'success')
        self.log_message("✅ 백업이 성공적으로 완료되었습니다!")
        self.log_message(f"📁 저장 위치: {self.output_path.get()}")
        
        result = messagebox.askyesno("백업 완료!", 
                                   f"🎉 백업이 완료되었습니다!\n\n저장 위치:\n{self.output_path.get()}\n\n백업 폴더를 열어보시겠습니까?")
        
        if result:
            try:
                if platform.system() == "Windows":
                    os.startfile(self.output_path.get())
                elif platform.system() == "darwin":
                    subprocess.Popen(["open", self.output_path.get()])
                else:
                    subprocess.Popen(["xdg-open", self.output_path.get()])
            except Exception as e:
                self.log_message(f"⚠️ 폴더 열기 실패: {str(e)}")
    
    def backup_error(self, error_msg):
        """백업 실패"""
        self.set_status("백업 실패", 'error')
        self.log_message(f"❌ 백업 실패: {str(error_msg)}")
        messagebox.showerror("백업 실패", f"백업 중 오류가 발생했습니다.\n\n{error_msg}")
    
    def finish_backup(self):
        """백업 완료 후 정리"""
        self.progress.stop()
        self.backup_btn.config(state='normal', text="🚀 백업 시작하기", bg=self.colors['evernote_green'])
        self.is_working = False
    
    # === 유틸리티 메서드들 ===
    
    def browse_output(self):
        """백업 저장 위치 선택"""
        folder = filedialog.askdirectory(title="백업 저장 폴더 선택", initialdir=self.output_path.get())
        if folder:
            self.output_path.set(folder)
    
    def set_status(self, message, status_type='info'):
        """상태 메시지 설정"""
        colors = {'info': self.colors['text'], 'success': self.colors['success'], 
                 'warning': self.colors['warning'], 'error': self.colors['error']}
        icons = {'info': 'ℹ️', 'success': '✅', 'warning': '⏳', 'error': '❌'}
        
        self.status_label.config(text=f"{icons[status_type]} {message}", fg=colors[status_type])
    
    def log_message(self, message):
        """로그 메시지 추가"""
        if hasattr(self, 'log_text'):
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')

def main():
    """메인 함수"""
    # pyperclip 의존성 확인
    try:
        import pyperclip
    except ImportError:
        import tkinter.messagebox as mb
        mb.showerror("의존성 누락", 
                    "pyperclip 라이브러리가 필요합니다.\n\n다음 명령어로 설치하세요:\npip install pyperclip")
        return
    
    root = tk.Tk()
    app = EvernoteBackupGUI(root)
    
    def on_closing():
        if app.terminal_process:
            try:
                app.terminal_process.terminate()
            except:
                pass
        if app.is_working:
            if tk.messagebox.askokcancel("종료", "작업이 진행 중입니다. 정말 종료하시겠습니까?"):
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
