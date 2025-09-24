# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for evernote-backup-gui (exe wrapper version)
# 이 GUI는 원저작자의 evernote-backup.exe를 subprocess로 호출하므로
# evernote_backup 모듈을 임포트하지 않습니다.

from PyInstaller.utils.hooks import collect_submodules

# 기본 GUI 모듈들만 포함
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.scrolledtext',
    'subprocess',
    'threading',
    'queue',
    'sqlite3',
    'platform',
    'tempfile',
    'webbrowser',
    'shutil',
    're',
    'json',
    'time',
    'os',
    'sys'
]

# pyperclip이 있으면 포함 (선택적 의존성)
try:
    import pyperclip
    hiddenimports.append('pyperclip')
except ImportError:
    pass

a = Analysis(
    ['evernote_backup_gui.py'],  # 새로운 파일명
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 모듈들 제외하여 파일 크기 최적화
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        'jupyter',
        'IPython'
    ],
    noarchive=False,
    optimize=0,
)

# 중복 제거 및 최적화
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='evernote-backup-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 모드
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 필요시 아이콘 파일 경로 추가
)

# 빌드 후 정리 (선택적)
import shutil
import os

def post_build_cleanup():
    """빌드 완료 후 정리 작업"""
    print("\n🎯 빌드 완료 후 정리 작업...")

    # build 폴더 정리
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
            print("✅ build 폴더 정리 완료")
        except Exception as e:
            print(f"⚠️ build 폴더 정리 실패: {e}")

    # __pycache__ 폴더들 정리
    for root, dirs, files in os.walk("."):
        for dir_name in dirs[:]:  # 복사본으로 반복
            if dir_name == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, dir_name))
                    dirs.remove(dir_name)  # 원본 리스트에서 제거
                    print(f"✅ {os.path.join(root, dir_name)} 정리 완료")
                except Exception as e:
                    print(f"⚠️ {os.path.join(root, dir_name)} 정리 실패: {e}")

# 빌드 완료 후 자동 정리 (주석 해제하여 사용)
# post_build_cleanup()
