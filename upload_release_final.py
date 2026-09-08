#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import os
from urllib.parse import quote

# GitHub API 설정
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"  # 실행 시 실제 토큰으로 교체
REPO_OWNER = "cdman28"
REPO_NAME = "evernote_backup_gui"
TAG_NAME = "v1.14.3"
FILE_PATH = r".\dist\EvernoteBackupGUI_v1.14.3.exe"
FILE_NAME = "EvernoteBackupGUI_v1.14.3.exe"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# 1. 기존 릴리즈 정보 조회
print("기존 릴리즈 정보 조회 중...")
get_release_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{TAG_NAME}"
response = requests.get(get_release_url, headers=headers)

if response.status_code != 200:
    print(f"❌ 릴리즈 조회 실패 (새로 생성 예정)")
else:
    release_data = response.json()
    release_id = release_data["id"]
    
    # 2. 기존 에셋 삭제
    print("기존 에셋 삭제 중...")
    if release_data.get("assets"):
        for asset in release_data["assets"]:
            asset_id = asset["id"]
            delete_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/assets/{asset_id}"
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code == 204:
                print(f"✅ 에셋 삭제됨: {asset['name']}")

# 3. 새 파일 업로드
print(f"파일 업로드 중: {FILE_NAME}...")

# 파일 읽기
with open(FILE_PATH, "rb") as f:
    file_data = f.read()

# 업로드 URL 구성
upload_url = f"https://uploads.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/{response.json()['id'] if response.status_code == 200 else 'ERROR'}/assets?name={quote(FILE_NAME)}"

# 업로드 헤더
upload_headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/octet-stream",
}

# 파일 업로드
if response.status_code == 200:
    release_id = response.json()["id"]
    upload_url = f"https://uploads.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/{release_id}/assets?name={quote(FILE_NAME)}"
    
    upload_response = requests.post(upload_url, headers=upload_headers, data=file_data)
    
    if upload_response.status_code == 201:
        asset_data = upload_response.json()
        print(f"✅ 파일 업로드 완료!")
        print(f"   파일명: {asset_data['name']}")
        print(f"   크기: {asset_data['size'] / (1024*1024):.2f} MB")
        print(f"   다운로드 URL: {asset_data['browser_download_url']}")
    else:
        print(f"❌ 파일 업로드 실패: {upload_response.status_code}")
        print(f"   응답: {upload_response.text}")

print("\n✅ 릴리즈 업데이트 완료!")
print(f"   릴리즈 페이지: https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/tag/{TAG_NAME}")
