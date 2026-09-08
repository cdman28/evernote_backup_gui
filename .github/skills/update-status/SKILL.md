---
name: update-status
description: |
  프로젝트 상태 파일(PROJECT_STATUS.md) 자동 생성 스킬.
  현재 프로젝트의 Python 파일 구조, 버전 정보(VERSION_HISTORY.md 자동 파싱),
  Git 변경 파일 목록을 수집하여 PROJECT_STATUS.md를 생성합니다.

  Use proactively when user asks to create or update project status file.

  Triggers: PROJECT_STATUS, 프로젝트 상태, update status, 상태 파일, status file,
  프로젝트 현황, 프로젝트 상태 파일, 상태 업데이트, project status, 현황 파일,
  프로젝트 현황 정리, 상태 파일 만들어줘, PROJECT_STATUS.md 만들어줘

  Do NOT use for: git commits, VERSION_HISTORY.md 편집, README 작성, 코드 구현 작업.
---

# Update Status 스킬

## 개요

현재 작업 중인 **프로젝트 루트 폴더**에서 `PROJECT_STATUS.md`를 자동 생성합니다.
다음 AI 대화 세션을 재개할 때 이 파일을 공유하면 이전 작업 상태를 빠르게 복원할 수 있습니다.

## 실행 방법

프로젝트 루트 폴더의 터미널에서 아래 명령 실행:

```powershell
python "d:\APP\.github\skills\update-status\scripts\update-status.py"
```

또는 사용자가 요청하면 AI가 직접 터미널에서 위 명령을 실행해 줍니다.

## 생성되는 PROJECT_STATUS.md 내용

- **마지막 업데이트 일시**
- **현재 버전** (VERSION_HISTORY.md 또는 CHANGELOG.md 자동 파싱)
- **프로젝트 파일 구조** (Python 파일 트리, Git 변경 파일 표시)
- **이번 커밋 변경 파일 목록** (Git staged 파일 기준)
- **기술 스택 및 프레임워크** 감지
- **주요 컴포넌트** 자동 감지
- **다음 세션 체크리스트**

## 지원하는 VERSION_HISTORY.md 형식

```
## V1.1 (2025-10-26)          ← 표준 형식
## 📌 V1.1 (2025-10-26)       ← 이모지 형식
### **V1.0** (2025-10-25)     ← 볼드 형식
```

## 주의사항

- 반드시 프로젝트 **루트 폴더**에서 실행할 것 (cd 명령으로 이동 후 실행)
- `VERSION_HISTORY.md`가 없어도 기본 상태 파일이 생성됨
- Git 저장소가 없어도 동작함 (변경 파일 목록만 비워짐)
