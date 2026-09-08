# 📋 Evernote Backup GUI 버전 변경 이력 (Version History)

모든 주요 변경 사항은 본 문서에 기록됩니다.

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
