"""
version_check.py
evernote-backup CLI 버전 감지 및 호환성 검증 모듈 (SRP 원칙 준수)
"""

import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

SUPPORTED_CLI_VERSION = "1.14.0"


class VersionStatus(str, Enum):
    MATCH = "MATCH"                    # 버전 완전 일치
    PATCH_MISMATCH = "PATCH_MISMATCH"  # 패치 버전 차이 (진행 안전)
    MINOR_MISMATCH = "MINOR_MISMATCH"  # 마이너 버전 차이 (경고 후 진행 허용)
    MAJOR_MISMATCH = "MAJOR_MISMATCH"  # 메이저 버전 차이 (실행 차단 권장)
    UNKNOWN = "UNKNOWN"                # 버전 확인 불가 (파싱 실패 등)


@dataclass
class VersionCheckResult:
    status: VersionStatus
    expected_version: str
    detected_version: Optional[str]
    message: str

    @property
    def can_proceed(self) -> bool:
        """실행을 계속 진행할 수 있는지 여부 (MAJOR_MISMATCH만 차단)."""
        return self.status != VersionStatus.MAJOR_MISMATCH


def parse_version_string(raw_text: str) -> Optional[Tuple[int, int, int]]:
    """'evernote-backup.exe, version 1.14.0' 등의 문자열에서 (major, minor, patch) 튜플을 추출합니다."""
    if not raw_text:
        return None

    # 정규식으로 'version X.Y.Z' 또는 'X.Y.Z' 탐색
    match = re.search(r"(?:version\s+)?(\d+)\.(\d+)(?:\.(\d+))?", raw_text, re.IGNORECASE)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3)) if match.group(3) is not None else 0
    return (major, minor, patch)


def format_version_tuple(ver_tuple: Optional[Tuple[int, int, int]]) -> str:
    """버전 튜플을 'X.Y.Z' 문자열로 변환합니다."""
    if not ver_tuple:
        return "알 수 없음"
    return f"{ver_tuple[0]}.{ver_tuple[1]}.{ver_tuple[2]}"


def run_cli_version(exe_path: str, timeout: float = 5.0) -> Optional[str]:
    """evernote-backup.exe --version 명령어를 실행하여 출력 문자열을 얻습니다."""
    if not exe_path or not os.path.isfile(exe_path):
        return None

    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=startupinfo,
        )
        output = (result.stdout or "").strip() or (result.stderr or "").strip()
        return output if output else None
    except Exception:
        return None


def check_version_compatibility(
    exe_path: str,
    expected_version: str = SUPPORTED_CLI_VERSION,
    timeout: float = 5.0,
) -> VersionCheckResult:
    """CLI 버전과 지원 기대 버전의 호환성을 검사합니다."""
    expected_tuple = parse_version_string(expected_version)
    if not expected_tuple:
        raise ValueError(f"잘못된 기대 버전 형식: {expected_version}")

    raw_output = run_cli_version(exe_path, timeout=timeout)
    if not raw_output:
        return VersionCheckResult(
            status=VersionStatus.UNKNOWN,
            expected_version=expected_version,
            detected_version=None,
            message=f"CLI 버전 확인 실패: '{exe_path} --version' 실행 결과를 읽을 수 없습니다.",
        )

    detected_tuple = parse_version_string(raw_output)
    if not detected_tuple:
        return VersionCheckResult(
            status=VersionStatus.UNKNOWN,
            expected_version=expected_version,
            detected_version=raw_output.strip()[:50],
            message=f"버전 문자열 파싱 실패: '{raw_output.strip()}'",
        )

    detected_str = format_version_tuple(detected_tuple)

    # 1. 완전 일치
    if detected_tuple == expected_tuple:
        return VersionCheckResult(
            status=VersionStatus.MATCH,
            expected_version=expected_version,
            detected_version=detected_str,
            message=f"CLI 버전 일치 ({detected_str})",
        )

    exp_major, exp_minor, exp_patch = expected_tuple
    det_major, det_minor, det_patch = detected_tuple

    # 2. 메이저 불일치
    if det_major != exp_major:
        return VersionCheckResult(
            status=VersionStatus.MAJOR_MISMATCH,
            expected_version=expected_version,
            detected_version=detected_str,
            message=(
                f"⚠️ CLI 주요(Major) 버전 불일치!\n"
                f"- 감지된 버전: v{detected_str}\n"
                f"- 지원 기대 버전: v{expected_version}\n\n"
                f"메이저 버전 차이로 인해 명령어가 호환되지 않을 수 있어 실행을 중단합니다.\n"
                f"호환되는 evernote-backup.exe(v{expected_version})를 다운로드해 주세요."
            ),
        )

    # 3. 마이너 불일치
    if det_minor != exp_minor:
        return VersionCheckResult(
            status=VersionStatus.MINOR_MISMATCH,
            expected_version=expected_version,
            detected_version=detected_str,
            message=(
                f"⚠️ CLI 마이너(Minor) 버전 차이 감지:\n"
                f"- 감지된 버전: v{detected_str}\n"
                f"- 지원 기대 버전: v{expected_version}\n\n"
                f"일부 새로운 옵션이나 변경사항으로 인해 예기치 않은 동작이 발생할 수 있습니다.\n"
                f"계속 진행하시겠습니까?"
            ),
        )

    # 4. 패치 불일치
    return VersionCheckResult(
        status=VersionStatus.PATCH_MISMATCH,
        expected_version=expected_version,
        detected_version=detected_str,
        message=(
            f"ℹ️ CLI 패치(Patch) 버전 차이:\n"
            f"- 감지된 버전: v{detected_str}\n"
            f"- 권장 버전: v{expected_version}\n"
            f"패치 버전 차이는 정상 호환됩니다."
        ),
    )
