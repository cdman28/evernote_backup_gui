import sys
import os
from cx_Freeze import setup, Executable

# 현재 스크립트와 같은 디렉토리에서 실행
script_dir = os.path.dirname(os.path.abspath(__file__))

# 사이트 패키지 경로
site_packages = r"C:\Users\YEDAM000\AppData\Local\Programs\Python\Python313\Lib\site-packages"

# cx_Freeze 호환 설정
build_exe_options = {
    "packages": [
        "tkinter", 
        "evernote_backup",
        "thrift", 
        "click", 
        "requests", 
        "urllib3", 
        "certifi", 
        "sqlite3",
        "json", "queue", "threading", "subprocess", 
        "webbrowser", "platform", "tempfile", "time", "re", "os", "sys"
    ],
    
    "include_files": [
        (os.path.join(site_packages, "evernote_backup"), "lib/evernote_backup"),
        (os.path.join(site_packages, "thrift"), "lib/thrift"),
        (os.path.join(site_packages, "click"), "lib/click"),
        (os.path.join(site_packages, "requests"), "lib/requests"),
        (os.path.join(site_packages, "urllib3"), "lib/urllib3"),
        (os.path.join(site_packages, "certifi"), "lib/certifi"),
    ],
    
    "excludes": ["matplotlib", "numpy", "scipy", "pandas", "PIL"],
    
    # 다음 옵션들 제거 (cx_Freeze가 지원하지 않음)
    # "zip_include_packages": [],
    # "zip_exclude_packages": ["*"],
    # "include_msvcrt": True,  # <- 이 옵션 제거
    # "optimize": 2,
}

# 존재하는 파일만 포함
include_files = []
for src, dst in build_exe_options["include_files"]:
    if os.path.exists(src):
        include_files.append((src, dst))
        print(f"✅ 포함: {src} -> {dst}")
    else:
        print(f"❌ 없음: {src}")
build_exe_options["include_files"] = include_files

# 아이콘 파일 추가
if os.path.exists("evernotebackup.ico"):
    build_exe_options["include_files"].append(("evernotebackup.ico", "evernotebackup.ico"))

# Windows GUI 애플리케이션
base = "Win32GUI" if sys.platform == "win32" else None

# 실행 파일
executables = [
    Executable(
        "evernote_backup_gui.py",
        base=base,
        icon="evernotebackup.ico" if os.path.exists("evernotebackup.ico") else None,
        target_name="에버노트백업도구_완전내장형_v1.13.1.exe"
    )
]

# cx_Freeze setup
if __name__ == "__main__":
    setup(
        name="EvernoteBackupTool",
        version="1.13.1",
        description="Standalone Evernote Backup Tool",
        options={"build_exe": build_exe_options},
        executables=executables
    )
