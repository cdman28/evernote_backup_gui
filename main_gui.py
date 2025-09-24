import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        import evernote_backup_gui
        evernote_backup_gui.main()
    except Exception as e:
        print(f"오류: {e}")
        input("Press Enter to exit...")
