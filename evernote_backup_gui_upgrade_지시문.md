# Evernote Backup GUI 업그레이드 작업지시문 (Antigravity용)

> 대상 저장소: https://github.com/cdman28/evernote_backup_gui
> 현재 버전: v1.13.1 (CLI를 subprocess로 호출하는 exe 동봉 방식)
> 목표: 최신 evernote-backup CLI(1.14.0 기준)에 맞춰 GUI 업그레이드
> 최종 갱신: tests 폴더 진단 결과 반영 (2026-09-08)

---

## 0. 작업 전 필수 확인 (반드시 먼저 실행)

에이전트는 아래 사항을 코드 실행/파일 읽기로 **직접 확인**한 뒤 결과를 보고할 것. 추측 금지.

1. `evernote_backup_gui.py` 전체를 읽고 다음을 확인:
   - `possible_locations` 리스트(exe 탐색 경로) 전체 내용
   - `_run_export_phase()` 함수의 실제 구현(export 시 어떤 플래그를 붙이는지)
   - `init-db --force` 호출 부분의 전체 인자 목록
   - `VERSION`, `BUILD_DATE` 상수 위치
2. `tests/` 폴더 관련 사전 진단 결과 (GitHub 코드 검색으로 이미 확인 완료, 재검증만 할 것):
   - 폴더 내 16개 파일 중 12개 파일이 `from evernote_backup import ...` 형태로 원본 evernote-backup 패키지의 내부 모듈(`cli_app`, `note_storage`, `evernote_client_api_http`, `token_util`, `note_exporter_util`, `note_formatter` 등)을 직접 import
   - `requirements.txt`에는 `pyperclip>=1.8.0`만 있고 `evernote_backup` 패키지는 설치 대상이 아님
   - 파일명 구성(`test_op_sync.py`, `test_op_export.py`, `test_op_manage.py`, `test_cli_app.py` 등)이 원본 `vzhd1701/evernote-backup` 저장소의 테스트 스위트 구조와 동일 → 스캐폴딩 과정에서 원본 저장소 테스트가 통째로 잘못 복사된 것으로 판단
   - **Antigravity는 실제로 `pytest tests/`를 실행해서 `ModuleNotFoundError`가 예상대로 발생하는지 최종 확인만 하고, 아래 5단계로 바로 진행할 것** (판단을 다시 하지 말 것)
3. 확인 결과를 아래 형식으로 보고:
   ```
   📋 코드 확인 결과
   - possible_locations: [실제 내용]
   - export 명령 구성: [실제 코드]
   - init-db 인자: [실제 코드]
   - pytest tests/ 실행 결과: [실제 에러 메시지 전문]
   ```

---

## 1. exe 교체 및 탐색 로직 재검증

- [ ] evernote-backup 공식 저장소(vzhd1701/evernote-backup) 릴리스 페이지에서 최신 Windows용 `bin_evernote_backup_*_win_x64.zip`을 다운로드해 `evernote-backup.exe`로 교체
- [ ] `possible_locations` 리스트가 다음 케이스를 모두 커버하는지 점검하고, 누락 시 추가:
  - GUI exe와 동일 폴더
  - GUI 스크립트(.py) 실행 시 현재 작업 디렉터리
  - 사용자가 별도 하위 폴더(`bin/`, `cli/` 등)에 넣는 경우는 현재 지원하지 않는다면, 지원 여부를 사용자에게 먼저 질문할 것 (임의로 확장하지 말 것)
- [ ] exe를 못 찾을 경우 사용자에게 보여주는 에러 메시지에 "정확히 어느 경로들을 검색했는지" 명시하도록 개선

---

## 2. 버전 불일치 감지 기능 추가 (신규 기능)

**목적**: GUI가 기대하는 CLI 버전과 실제 옆에 놓인 exe 버전이 다를 때 사용자에게 경고.

- [ ] GUI 시작 시 또는 백업 실행 직전에 `evernote-backup.exe --version` (또는 실제 지원하는 버전 확인 플래그, 사전 확인 필요)을 subprocess로 실행해 버전 문자열 파싱
- [ ] GUI 내부의 기대 버전 상수(`SUPPORTED_CLI_VERSION` 신규 정의 권장)와 비교
- [ ] 버전이 다르면:
  - 완전히 다른 major 버전이면 실행을 막고 경고창 표시
  - minor 버전 차이면 "경고만 표시 후 계속 진행 가능" 옵션 제공
- [ ] 이 기능은 새 파일(`version_check.py` 등)로 분리해 단일 책임 원칙(SRP)을 지킬 것 — `evernote_backup_gui.py`에 직접 로직을 섞지 말 것
- [ ] 관련 단위 테스트를 함께 작성 (버전 문자열 파싱 실패, 버전 일치, 버전 불일치 3가지 케이스) — 이 테스트는 5단계에서 새로 만드는 테스트 스위트에 포함시킬 것

---

## 3. 최신 CLI 옵션 GUI 노출

우선순위 순으로 진행. 한 번에 하나씩 구현 후 사용자 확인받고 다음으로 진행할 것.

### 3-1. Export 옵션 확장 (우선순위 높음)
- [ ] `--notebook` / `--tag` 필터: 노트북/태그 이름 입력창 또는 드롭다운 추가
- [ ] `--single-notes`: 체크박스로 노출
- [ ] `--overwrite`: 체크박스로 노출
- [ ] `--add-metadata`: 체크박스로 노출
- [ ] `--no-export-date`: 체크박스로 노출
- [ ] `--include-trash`: 체크박스로 노출

### 3-2. 진단 기능 추가 (우선순위 중간)
- [ ] `manage check` 실행 버튼 추가 (DB 무결성 검사)
- [ ] `manage list` 실행 버튼 추가 (백업된 노트북 목록 조회, 결과를 GUI 로그 창에 표시)

### 3-3. 고급 인증 옵션 (우선순위 낮음, 별도 "고급 설정" 섹션으로 분리 권장)
- [ ] `--include-tasks --token`: 별도 토큰 입력창 필요, 일반 사용자에게는 기본적으로 숨김 처리
- [ ] `--use-system-ssl-ca`, `--oauth-host`, `--backend china`: "고급 설정" 접기(collapsible) 섹션에 배치

---

## 4. subprocess 명령 빌더 리팩터링

- [ ] 현재 `cmd = [...]` 형태로 직접 리스트를 작성하는 부분을 아래와 같은 헬퍼 함수로 통합:
  ```python
  def build_export_command(exe_path, export_dir, options: ExportOptions) -> list[str]:
      """ExportOptions 객체를 기반으로 CLI 명령 리스트를 생성한다."""
  ```
- [ ] 옵션은 dataclass(`ExportOptions`, `SyncOptions`)로 정의해 어떤 플래그가 있는지 한눈에 보이게 할 것
- [ ] 이 리팩터링은 **먼저 계획만 제시**하고 승인받은 뒤 진행 (기존 동작 변경 없이 구조만 정리하는 것이 목적임을 명확히 할 것)

---

## 5. tests 폴더 전면 교체 (판정 완료 — 바로 실행)

> 0단계 진단으로 원본 패키지 테스트임이 확정됐으므로, 재판단 없이 아래를 실행한다.

- [ ] `tests/` 폴더의 기존 16개 파일 **전체 삭제**:
  `__init__.py`, `conftest.py`, `test_cli_app.py`, `test_cli_app_util.py`, `test_evernote_client_api.py`, `test_evernote_client_oauth.py`, `test_note_exporter_util.py`, `test_note_formatter.py`, `test_note_storage.py`, `test_op_export.py`, `test_op_init_db.py`, `test_op_manage.py`, `test_op_manage_check.py`, `test_op_manage_list.py`, `test_op_reauth.py`, `test_op_sync.py`, `test_op_sync_v2.py`
- [ ] 삭제 전 안전을 위해 별도 브랜치(`cleanup/remove-upstream-tests`)에서 작업하고, 삭제 후 `git log`로 언제든 복구 가능함을 확인
- [ ] 새 테스트를 GUI 자체 로직 기준으로 처음부터 작성 (최소 커버리지 목표):
  - `possible_locations` exe 탐색 로직 테스트 (exe 있음/없음/여러 경로 중 하나만 있음)
  - `build_export_command` / `build_sync_command` 등 4단계에서 만들 명령 빌더 함수 테스트
  - `version_check.py` 버전 파싱·비교 로직 테스트 (2단계 신규 기능)
  - init-db, sync, export 각 단계의 subprocess 호출 시 mock을 사용한 명령어 조립 검증 (실제 exe 실행 없이)
- [ ] `requirements-dev.txt`(신규 파일) 생성: `pytest>=8.0.0` 정도만 추가. `evernote_backup` 패키지는 여전히 설치하지 않음(subprocess로만 호출하는 구조이므로 불필요)

---

## 6. 문서/버전 문자열 일괄 갱신

- [ ] `evernote_backup_gui.py`: `VERSION`, `BUILD_DATE`, 모듈 docstring
- [ ] `README.md`: 다운로드 안내 문구, UI 목업 텍스트, 버전 표기
- [ ] `에버노트백업도구_v1.13.1.spec` → `에버노트백업도구_v{신규버전}.spec`로 파일명 변경 및 내부 `name=` 값 갱신

---

## 진행 순서 요약

1. 0단계 확인 결과 보고(특히 `pytest tests/` 실제 실행 결과) → 사용자 검토
2. 1~2단계 (exe 교체 + 버전 체크) 구현 → 사용자 확인
3. 3-1 (export 옵션) 구현 → 사용자 확인
4. 3-2 (진단 기능) 구현 → 사용자 확인
5. 3-3 (고급 옵션) 구현 → 사용자 확인
6. 4단계 리팩터링 계획 제시 → 승인 → 구현
7. 5단계: 기존 tests 폴더 삭제 → 새 테스트 작성 → `pytest` 통과 확인
8. 6단계 버전 문자열 갱신 → 최종 빌드(.spec 실행) → 전체 동작 확인

각 단계 완료 시 전체 코드를 다시 제공받아 검토할 것.
