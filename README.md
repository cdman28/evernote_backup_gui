# 📋 에버노트 백업 도구 GUI
### Evernote Backup GUI — Windows Desktop App

> [evernote-backup](https://github.com/vzhd1701/evernote-backup) v1.13.1 CLI를 감싼 **Windows 전용 GUI 백업 도구**입니다.  
> 터미널 없이 버튼 클릭만으로 에버노트 전체 노트를 로컬에 ENEX 형식으로 백업합니다.

---

## ✨ 주요 기능 (Features)

| 기능 | 설명 |
|------|------|
| 🔐 **OAuth 인증** | 브라우저 기반 1회 인증 — 이후 토큰 자동 재사용 |
| 🔍 **클립보드 자동 감지** | OAuth URL 복사 시 GUI가 자동으로 브라우저를 열어줌 |
| 🚀 **원클릭 백업** | 동기화(sync) → ENEX 내보내기(export) 자동 순차 실행 |
| ⏹ **백업 중지** | 진행 중 언제든지 안전하게 취소 가능 |
| 📊 **실시간 로그** | 진행률 및 로그를 GUI에서 실시간 확인 |
| 💾 **DB 상태 표시** | 저장된 노트 수・마지막 동기화 시각・토큰 만료일 자동 표시 |
| 📁 **폴더 열기** | 백업 완료 후 내보내기 폴더 바로 열기 |
| 📝 **로그 저장** | 작업 로그를 `.txt` 파일로 저장 |
| 🔄 **자동 Rate-Limit 처리** | API 한도 초과 시 자동 대기 후 재시도 |
| 🔁 **토큰 만료 재인증** | 만료된 토큰을 버튼 하나로 갱신 |

---

## 📸 화면 미리보기 (Screenshot)

> GUI는 왼쪽(설정 패널) + 오른쪽(실시간 로그)으로 구성됩니다.

```
┌─────────────────────────────────────┬─────────────────────────────┐
│  📋 에버노트 백업 도구              │  📄 작업 로그               │
│  GUI for evernote-backup 1.13.1     │                             │
├─────────────────────────────────────┤  ✅ OAuth 인증 완료         │
│  💾 DB 설정                         │  🔄 동기화 시작...          │
│  경로: C:\EvernoteDB\...            │  [####     ]  1240/6763     │
├─────────────────────────────────────┤  📦 ENEX 내보내기 중...     │
│  🔐 OAuth 로그인                    │  ✅ 백업 완료!              │
│  [ 🔐 OAuth 인증 시작 ]             │                             │
├─────────────────────────────────────┤                             │
│  💾 백업 설정                       │                             │
│  내보내기 폴더: D:\EvernoteBackup   │  [로그 저장] [로그 지우기]  │
│  [ 🚀 백업 시작 ]  [ ⏹ 중지 ]      │                             │
└─────────────────────────────────────┴─────────────────────────────┘
```

---

## 🚀 시작하기 (Getting Started)

### 요구사항

- **Windows 10 / 11** (64비트)
- **evernote-backup.exe** — 이 GUI와 동일한 폴더에 배치 필요
- 에버노트 계정 (Evernote 또는 Yinxiang 印象笔记)

### evernote-backup.exe 다운로드

👉 [**최신 릴리즈 다운로드**](https://github.com/vzhd1701/evernote-backup/releases/latest)에서  
`bin_evernote_backup_1.13.1_win_x64.zip` 파일을 내려받아 압축을 풀면  
`evernote-backup.exe`가 나옵니다. 이 파일을 GUI와 **같은 폴더에 놓아주세요**.

### GUI 실행 방법

**방법 1 — Python으로 직접 실행 (개발용)**

```bash
# Python 3.9+ 필요
pip install pyperclip  # 선택적: 클립보드 자동 감지 기능
python main_gui.py
```

**방법 2 — EXE 빌드 후 실행 (배포용)**

```bash
pip install pyinstaller
pyinstaller 에버노트백업도구_v1.13.1.spec
# dist/ 폴더에 에버노트백업도구_v1.13.1.exe 생성됨
```

**폴더 구조 (실행 전 확인)**

```
📁 실행 폴더/
├── 에버노트백업도구_v1.13.1.exe   ← 이 GUI
└── evernote-backup.exe            ← 원본 CLI (필수!)
```

---

## 📖 사용법 (Usage)

### 1단계 — OAuth 인증

1. **"OAuth 인증 시작"** 버튼 클릭
2. 검은 콘솔 창이 열리고, 브라우저가 자동으로 에버노트 로그인 페이지를 열음
3. 에버노트에 로그인 → **"일괄 백업 허용 (Allow Bulk Backup)"** 클릭
4. 콘솔 창이 자동으로 닫히고 GUI에 **"✅ 인증 완료!"** 표시

> **💡 브라우저가 자동으로 안 열릴 경우**
>
> 콘솔 창에 표시된 `https://...` URL을 다음 방법으로 복사하세요:
> - 마우스로 URL 드래그 → **우클릭** 또는 **Enter 키** 로 복사
> - GUI의 URL 입력란에 **붙여넣기** → **"🌐 열기"** 버튼 클릭
> - 또는 복사만 해도 GUI가 클립보드를 자동 감지하여 브라우저를 열어줌

### 2단계 — 백업 실행

1. **내보내기 폴더** 선택 (기본값: `D:\EvernoteBackup`)
2. **"🚀 백업 시작"** 버튼 클릭
3. 동기화 → ENEX 내보내기 순서로 자동 진행
4. 완료 후 **"📁 폴더 열기"** 버튼으로 결과 확인

### 3단계 — 정기 백업

- 이후 백업은 **"🚀 백업 시작"** 버튼만 클릭하면 됨
- 인증 토큰은 DB에 저장되어 자동 재사용
- 변경된 노트만 다운로드하므로 이후 백업은 빠름

---

## 📦 백업 결과물 (Output)

백업 결과는 `*.enex` 형식으로 저장됩니다.

```
📁 내보내기 폴더/
├── 📓 개인 노트북.enex
├── 📓 업무 자료.enex
├── 📓 스크랩.enex
└── ...
```

ENEX 파일은 다음 앱에서 가져오기(Import) 할 수 있습니다:
- **Evernote** (동일 계정 또는 다른 계정 복원)
- **Notion** (ENEX 가져오기 지원)
- **Obsidian** (플러그인 사용)
- **Joplin**, **Bear**, **Logseq** 등 다수

---

## ⚙️ 고급 설정 (Advanced)

| 설정 | 기본값 | 설명 |
|------|--------|------|
| DB 경로 | `C:\EvernoteDB\evernote_backup.db` | 노트 캐시 SQLite DB |
| 내보내기 폴더 | `D:\EvernoteBackup` | ENEX 파일 저장 위치 |
| 백엔드 | `evernote` | `evernote` 또는 `china` (Yinxiang) |

### 토큰 만료 재인증

인증 토큰은 약 1년 후 만료됩니다. 만료 시:
1. **"OAuth 인증 시작"** 을 다시 클릭하여 재인증
2. 또는 DB 상태 표시에서 만료일 사전 확인 가능

---

## 🔧 기술 스택 (Tech Stack)

| 항목 | 내용 |
|------|------|
| Language | Python 3.9+ |
| GUI Framework | tkinter (내장 라이브러리) |
| Backend | [evernote-backup](https://github.com/vzhd1701/evernote-backup) v1.13.1 |
| Packaging | PyInstaller |
| OAuth | Evernote OAuth 1.0a (브라우저 기반) |
| Storage | SQLite (노트 캐시), ENEX (내보내기) |
| Optional | pyperclip (클립보드 자동 감지) |

---

## 📁 프로젝트 구조 (Project Structure)

```
evernote_backup_gui/
├── main_gui.py                    # 진입점 (Entry point)
├── evernote_backup_gui.py         # 메인 GUI 애플리케이션 (~1700 lines)
├── requirements.txt               # Python 의존성
├── 에버노트백업도구_v1.13.1.spec  # PyInstaller 빌드 설정
├── evernotebackup.ico             # 앱 아이콘
└── build/
    └── 사용하지 않는 파일/
        └── evernote_backup/       # evernote-backup 소스코드 (참조용)
```

---

## 🐛 알려진 이슈 / FAQ

**Q. "evernote-backup.exe를 찾을 수 없습니다" 오류가 납니다.**  
A. `evernote-backup.exe`를 GUI와 같은 폴더에 놓아주세요. [다운로드 링크](https://github.com/vzhd1701/evernote-backup/releases/latest)

**Q. 브라우저가 자동으로 안 열립니다.**  
A. 콘솔 창의 URL을 복사하여 GUI의 URL 입력란에 붙여넣기 하거나, 복사만 하면 자동 감지됩니다.

**Q. `Rate Limit exceeded` 오류가 납니다.**  
A. Evernote API 제한입니다. 자동으로 대기 후 재시도합니다. 기다려 주세요.

**Q. 백업 중 프로그램을 닫아도 되나요?**  
A. "중지" 버튼으로 안전하게 멈춘 뒤 닫는 것을 권장합니다. 다음 실행 시 중단된 지점부터 이어서 동기화됩니다.

**Q. Yinxiang (印象笔记, 중국판) 계정도 됩니까?**  
A. 원본 evernote-backup CLI는 Yinxiang을 지원합니다. GUI에서 백엔드를 `china`로 변경하려면 소스코드 수정이 필요합니다.

---

## 📄 라이선스 (License)

이 프로젝트는 **MIT License** 를 따릅니다.  
원본 백엔드 [evernote-backup](https://github.com/vzhd1701/evernote-backup) by [vzhd1701](https://github.com/vzhd1701) — MIT License.

---

## 🙏 감사 (Acknowledgements)

- [vzhd1701/evernote-backup](https://github.com/vzhd1701/evernote-backup) — 핵심 백엔드 CLI 제작자

---

*📅 최종 수정: 2026-02-28*
