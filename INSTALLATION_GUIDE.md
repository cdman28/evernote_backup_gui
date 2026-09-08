# 에버노트 백업 도구 - 설치 및 실행 가이드

> 다른 PC에서 처음 사용하는 경우 반드시 읽으세요!

---

## ⚠️ 설치 전 필수 사항

이 앱은 **evernote-backup CLI 위의 GUI 래퍼**입니다.  
따라서 CLI가 반드시 설치되어 있어야 합니다.

---

## 📋 단계별 설치

### 1단계: Python 설치
**요구사항**: Python 3.10 이상

1. [python.org](https://www.python.org) 방문
2. Windows 설치 프로그램 다운로드 (64-bit 권장)
3. 설치 시 **✅ "Add Python to PATH" 체크**
4. 설치 완료 후 PowerShell 재시작

**확인**:
```powershell
python --version
# 출력: Python 3.10.x 이상
```

### 2단계: evernote-backup CLI 설치
**가장 중요합니다!**

PowerShell을 **관리자 권한**으로 열고:
```powershell
pip install evernote-backup
```

**확인**:
```powershell
evernote-backup --version
# 출력: 1.14.0 이상
```

❌ **"evernote-backup is not recognized" 오류가 나면?**
- PowerShell 재시작
- 또는: `python -m evernote_backup --version` 시도

### 3단계: GUI 실행

[GitHub Releases](https://github.com/cdman28/evernote_backup_gui/releases)에서:
- `에버노트백업도구_v1.14.3.exe` 다운로드
- 더블 클릭으로 실행

---

## 🔍 문제 해결

### 문제 1: "evernote-backup을 찾을 수 없습니다"
```powershell
# 해결책 1: PATH 다시 설정 후 재시작
# 해결책 2: 직접 호출
python -m evernote_backup --help

# 해결책 3: 전체 경로로 설치 확인
pip show evernote-backup
```

### 문제 2: "액세스 거부" 또는 권한 오류
- PowerShell을 **관리자 권한**으로 재시작
- `pip install evernote-backup` 재실행

### 문제 3: exe 실행 안 됨
**Windows Defender 차단 가능**:
1. Windows Defender 보안 센터 열기
2. "바이러스 및 위협 방지" → "바이러스 및 위협 방지 설정"
3. "Windows Defender를 통한 차단된 앱" 확인
4. 앱 허용

### 문제 4: OAuth 로그인 실패
```powershell
# 인터넷 연결 확인
ping api.evernote.com

# 방화벽 설정 확인
# Evernote API 서버(api.evernote.com) 접근 가능한지 확인
```

### 문제 5: "Database is locked" 오류
- 다른 창에서 같은 DB 접근 중
- GUI 창을 모두 닫고 다시 시작

---

## ✅ 정상 작동 확인

1. GUI 실행
2. "🔐 OAuth 로그인" 버튼 클릭
3. 브라우저에서 Evernote 계정 로그인
4. GUI로 돌아와서 "✅ 인증 완료" 표시 확인
5. "동기화 시작" 클릭하여 백업 시작

---

## 📦 필요한 것들

| 항목 | 상태 | 설명 |
|------|------|------|
| Python 3.10+ | ✅ 필수 | 패키지 관리 |
| evernote-backup CLI | ✅ 필수 | 백업 엔진 |
| GUI exe | ✅ 필수 | 사용자 인터페이스 |
| 인터넷 연결 | ✅ 필수 | Evernote 서버 접근 |
| Evernote 계정 | ✅ 필수 | 로그인 |

---

## 🆘 여전히 안 되면?

**정보 수집 후 보고하기**:
```powershell
# 1. Python 버전
python --version

# 2. evernote-backup 설치 확인
pip show evernote-backup

# 3. CLI 버전
evernote-backup --version

# 4. GUI 실행 시 오류 메시지 캡처
# (콘솔 창이 나타난 경우 메시지 기록)
```

위 정보들을 함께 제공하면 빠르게 해결할 수 있습니다!

---

**Happy Backing Up! 🎉**
