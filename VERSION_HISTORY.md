# 📋 Evernote Backup GUI 버전 변경 이력 (Version History)

모든 주요 변경 사항은 본 문서에 기록됩니다.

---

## [v1.14.5] - 2026-09-08

### ✨ 새로운 기능 (New Features)
- **블랙리스트 관리 (manage blacklist) 기능 GUI 추가**:
  - "🛠️ 진단 및 관리 도구" 섹션에 "🚫 블랙리스트 관리" 버튼 추가
  - 블랙리스트 관리 대화창 구현:
    - **조회**: 현재 차단된 노트 및 노트북 목록 조회
    - **추가**: 노트 ID 또는 노트북 ID를 입력하여 차단 항목 추가 (--add-note-id, --add-notebook-id)
    - **삭제**: 차단된 노트 또는 노트북을 목록에서 제거 (--del-note-id, --del-notebook-id)
    - **전체 초기화**: 차단된 모든 노트 또는 노트북 한 번에 해제 (--reset-notes, --reset-notebooks)
  - CLI의 `manage blacklist` 명령을 GUI에서 편리하게 사용 가능
  - 모든 작업 결과는 로그에 기록되며 성공/실패 메시지 표시

### 🔧 개발 개선 (Development)
- `command_builder.py`에 `BlacklistOptions` 데이터클래스 추가
- `build_manage_blacklist_command()` 함수 구현으로 blacklist 명령 조립 기능 추가
- 기존 `build_manage_command()` 함수와 일관성 있게 설계

---

## [v1.14.4] - 2026-09-08

### 🐛 버그 수정
- **PyInstaller 실행 시 evernote-backup.exe 탐색 경로 오류 수정**:
  - 기존: `script_dir = os.path.dirname(__file__)` → PyInstaller onefile 모드에서 `__file__`이 실제 exe 폴더가 아닌 임시 추출 폴더(`C:\Temp\_MEI123456\`)를 가리켜, "파일 못 찾음" 대화상자에 혼란스러운 경로가 표시됨.
  - 수정: `getattr(sys, 'frozen', False)` 체크를 추가하여, frozen 모드(exe 실행)에서는 `sys.executable`에서 폴더를 구하도록 변경. 이제 `script_dir`이 항상 GUI exe가 실제 위치한 폴더를 정확히 가리킴.
  - 후보 탐색 순서도 개선: `같은 폴더 → CWD → PATH` 순으로 최우선 탐색.
- **GUI exe 파일명 영문화**: `에버노트백업도구_v1.14.x.exe` → `EvernoteBackupGUI_v1.14.x.exe` (Windows 경로 호환성 향상)

---

## [v1.14.3] - 2026-09-08

### 🐛 버그 수정 / 기능 개선
- **동기화 실시간 진행 표시 (DB 폴링 방식)**:
  - CLI의 `click.progressbar`는 파이프 환경에서 완전히 억제되어 진행 정보를 전달할 수 없는 구조임을 확인.
  - 대안으로 동기화 중 SQLite DB를 2초마다 직접 읽어 노트 수 증가량과 파일 크기를 실시간으로 표시.
  - 진행률 바가 실제 다운로드 완료 비율(`다운로드된 노트 / 총 노트`)로 채워지며 퍼센트 표시.
  - 상태 레이블: `🔽 N / 전체개 (X%) | 파일: X.X MB` 형식으로 매 2초 갱신.
  - DB 잠금 상태에서는 해당 폴링 사이클을 안전하게 건너뜀 (timeout=0.5초).
  - 이전의 비결정 모드(좌우 애니메이션) 대신 결정 모드 진행률 바로 실제 진척도 표시.

---

## [v1.14.2] - 2026-09-08

### 🐛 버그 수정 (Bug Fixes)
- **동기화 진행률 표시 수정**:
  - `"Downloading N note(s)..."` 패턴을 감지하지 못하던 정규식 오류 수정.
  - CLI의 `click.progressbar`는 파이프 환경에서 출력이 억제되므로, 다운로드 시작 시 비결정 모드(indeterminate, 애니메이션)로 전환하여 진행 중임을 시각적으로 표시.
  - 다운로드 완료("Synchronization completed" 또는 "up to date") 감지 시 진행률 바 정상 복귀.
  - 총 노트 수 숫자 표시에 천 단위 쉼표 추가.

### 🎨 UI 개선 (UI Improvements)
- **레이아웃 최적화 - 정보 패널 위치 변경**:
  - "📊 동기화 상태"와 "🛠️ 진단 및 관리 도구" 섹션을 왼쪽 하단에서 오른쪽 로그 창 상단으로 이동.
  - 두 섹션이 오른쪽 상단에서 나란히 배치되어 창 공간을 더 효율적으로 사용.
  - 왼쪽 컬럼이 줄어들어 수직 공간 부족 문제 해소.

---

## [v1.14.1] - 2026-09-08

### 🐛 버그 수정 (Bug Fixes)
- **OAuth 인증 성공 감지 오류 수정**:
  - v1.14.0 CLI가 인증 토큰을 `auth_token` 키로 저장하는데, GUI가 구버전 키인 `access_token`을 찾아 항상 인증 실패로 오판하는 버그 수정.
  - `get_db_info()` 내 쿼리를 `auth_token`으로 수정하여 정상 감지.
- **클립보드 모니터링 중복 감지 방지**:
  - 새 OAuth 세션 시작 시 `_clipboard_last`를 빈 문자열로 초기화하던 방식을, 현재 클립보드 내용으로 초기화하도록 수정.
  - 이전 세션의 OAuth URL이 클립보드에 남아있을 때 브라우저가 재오픈되고 CSRF 오류가 발생하는 문제 해결.

---

## [v1.14.0] - 2026-09-08

### 🚀 신규 기능 (Features)
- **최신 evernote-backup v1.14.0 엔진 탑재**:
  - 최신 Windows 64비트 바이너리 교체 완료.
- **버전 불일치 자동 감지 시스템 (`version_check.py`)**:
  - GUI 실행 시 CLI 버전 호환성을 사전에 자동 점검.
  - 메이저(Major) 버전 불일치 시 실행 차단 및 안내.
  - 마이너(Minor) 버전 차이 시 사용자 확인 후 진행 가능.
- **세부 내보내기(Export) 옵션 확장**:
  - `기존 파일 덮어쓰기 (--overwrite)` 체크박스 (기본값: 활성화)
  - `노트별 개별 저장 (--single-notes)` 분할 내보내기 지원
  - `메타데이터 포함 (--add-metadata)` 태그 블록 추가 지원
  - `날짜 제외 (--no-export-date)` 타임스탬프 제외 옵션
  - `휴지통 포함 (--include-trash)` 옵션
  - `노트북 필터 (--notebook)` 및 `태그 필터 (--tag)` 텍스트 검색창 (쉼표 구분 복수 필터링 지원)
- **DB 진단 및 관리 도구 (`manage` 하위 명령 UI 노출)**:
  - `DB 무결성 검사 (manage check)`: 로컬 DB 및 노트 무결성 자동 진단.
  - `노트북 목록 조회 (manage list)`: 로컬 DB에 보관된 노트북 목록을 GUI 로그 창에 바로 출력.
- **접이식(Collapsible) 고급 설정**:
  - 글로벌 에버노트 및 인샹(중국) 서버 선택 (`--backend`)
  - 시스템 SSL CA 사용 체크박스 (`--use-system-ssl-ca`)
  - OAuth 로컬 호스트 지정 (`--oauth-host`)
  - 수동 API 인증 토큰 입력란 (`--token`)

### 🛠 리팩터링 및 구조 개선 (Refactoring)
- **subprocess 명령 빌더 분리 (`command_builder.py`)**:
  - `ExportOptions`, `SyncOptions`, `InitDbOptions` 데이터클래스 정의 및 단일 책임 원칙(SRP) 확립.
  - Clean Architecture 패턴을 적용하여 UI와 CLI 명령 조립 로직 분리.
- **EXE 탐색 경로 개선 (`get_possible_exe_locations`)**:
  - 실행 폴더, 스크립트 경로, 작업 디렉터리, `bin/`, `cli/`, 시스템 `PATH` 자동 탐색 및 정규화 중복 제거.
  - 미발견 시 사용자에게 검색된 전체 경로 목록 상세 안내.
- **테스트 스위트 전면 재구축 (`tests/`)**:
  - 원본 패키지 의존성 테스트 제거 및 GUI 자체 로직 대상 단위 테스트 19건 작성 완료 (100% 통과).
  - `pytest.ini` 및 `requirements-dev.txt` 설정 추가.

---

## [v1.13.1] - 2026-02-28

### 🚀 초기 릴리스
- evernote-backup v1.13.1 CLI 래핑 Windows GUI 도구 릴리스.
- 원클릭 브라우저 OAuth 2.0 인증 지원 및 클립보드 자동 URL 감지.
- SQLite 데이터베이스 기반 동기화(sync) 및 ENEX 내보내기(export) 자동화.
- 실시간 진행률 바 및 스크롤 로그 창 제공.
- PyInstaller 원클릭 단일 실행 파일 배포.
