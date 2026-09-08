# update-status.py
# Python Project Status Generator
# Works with any Python project structure

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

def get_git_changed_files():
    """Get list of files changed in staged area"""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []

def get_python_files_structure(changed_files):
    """Get Python project file structure"""
    py_structure = []

    # Find Python files recursively
    for root, dirs, files in os.walk('.'):
        # Skip common directories to ignore
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.venv', 'venv', 'env', '.idea', 'node_modules', 'dist', 'build', '.pytest_cache'}]

        # Filter Python files
        py_files = sorted([f for f in files if f.endswith('.py')])

        if py_files:
            # Get relative path
            rel_path = os.path.relpath(root, '.')
            if rel_path == '.':
                dir_display = 'root'
            else:
                dir_display = rel_path.replace('\\', '/')

            py_structure.append(f"|-- {dir_display}/")

            for py_file in py_files:
                file_path = os.path.join(root, py_file).replace('\\', '/')
                # Check if file was modified
                mark = " *" if any(cf in file_path for cf in changed_files) else ""
                py_structure.append(f"|   |-- {py_file}{mark}")

    return '\n'.join(py_structure) if py_structure else "(No Python files found)"

def detect_project_type():
    """Detect Python project type and framework"""
    frameworks = []

    if os.path.exists('requirements.txt'):
        frameworks.append("requirements.txt found")
        try:
            with open('requirements.txt', 'r', encoding='utf-8') as f:
                content = f.read().lower()
                if 'flask' in content:
                    frameworks.append("Flask web application")
                if 'django' in content:
                    frameworks.append("Django web application")
                if 'fastapi' in content:
                    frameworks.append("FastAPI application")
                if 'streamlit' in content:
                    frameworks.append("Streamlit application")
                if 'tkinter' in content or 'pyqt' in content or 'pyside' in content:
                    frameworks.append("Desktop GUI application")
        except:
            pass

    if os.path.exists('setup.py'):
        frameworks.append("setup.py found (Package)")

    if os.path.exists('pyproject.toml'):
        frameworks.append("pyproject.toml found")

    if os.path.exists('manage.py'):
        frameworks.append("Django project detected")

    return frameworks if frameworks else ["Standard Python project"]

def get_main_components():
    """Detect main components in the project"""
    components = []

    # Check for common directories
    if os.path.exists('models'):
        components.append("- models/ (Data models)")
    if os.path.exists('views'):
        components.append("- views/ (Views)")
    if os.path.exists('controllers'):
        components.append("- controllers/ (Controllers)")
    if os.path.exists('services'):
        components.append("- services/ (Business logic)")
    if os.path.exists('utils') or os.path.exists('helpers'):
        components.append("- utils/helpers/ (Utility functions)")
    if os.path.exists('tests'):
        components.append("- tests/ (Test cases)")
    if os.path.exists('config'):
        components.append("- config/ (Configuration)")
    if os.path.exists('static'):
        components.append("- static/ (Static files)")
    if os.path.exists('templates'):
        components.append("- templates/ (HTML templates)")

    return '\n'.join(components) if components else "- (Auto-detect main modules)"

def find_version_history_file():
    """Find version history file with flexible naming"""
    possible_names = [
        'VERSION_HISTORY.md',
        'version_history.md',
        'HISTORY.md',
        'history.md',
        'CHANGELOG.md',
        'changelog.md',
        'CHANGES.md',
        'changes.md',
        'VERSIONS.md',
        'versions.md',
    ]
    
    # 먼저 정확한 이름 매칭 시도
    for name in possible_names:
        file_path = Path(name)
        if file_path.exists():
            return file_path
    
    # 패턴 매칭으로 버전 숫자가 포함된 파일명 찾기
    patterns = [
        r'VERSION.*HISTORY.*\.md$',
        r'HISTORY.*v?\d+.*\.md$',
        r'CHANGELOG.*v?\d+.*\.md$',
        r'v?\d+.*HISTORY.*\.md$',
        r'v?\d+.*CHANGELOG.*\.md$',
    ]
    
    for file in Path('.').glob('*.md'):
        filename_upper = file.name.upper()
        for pattern in patterns:
            if re.match(pattern, filename_upper, re.IGNORECASE):
                return file
    
    return None

def parse_version_history():
    """Parse VERSION_HISTORY.md if exists - with flexible format support"""
    version_file = find_version_history_file()
    
    if not version_file:
        return None
    
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 다양한 버전 형식을 지원하는 정규식 패턴들
        # 우선순위: 표준 템플릿 > 기존 복잡한 형식
        version_patterns = [
            # 표준 템플릿 형식 (최우선)
            r'##\s*V([\d.]+)\s*\(([^)]+)\)',                # ## V1.1 (2025-10-26) ⭐ 표준
            # 기존 복잡한 형식들 (하위 호환)
            r'##\s*📌\s*V([\d.]+)\s*\(([^)]+)\)',        # ## 📌 V1.1 (2025-10-26)
            r'###\s*\*\*V?([\d.]+)\*\*\s*\(([^)]+)\)',  # ### **V1.0** (2025-10-25)
            r'###\s*V?([\d.]+)\s*\(([^)]+)\)',           # ### V1.0 (2025-10-25)
            r'##\s*\*\*V?([\d.]+)\*\*\s*\(([^)]+)\)',    # ## **V1.0** (2025-10-25)
            r'#\s*V?([\d.]+)\s*\(([^)]+)\)',             # # V1.0 (2025-10-25)
            r'Version\s+V?([\d.]+)\s*[-–—]\s*([^\n]+)',  # Version V1.0 - 2025-10-25
            r'v?([\d.]+)\s*\(([^)]+)\)',                 # v1.0 (2025-10-25)
        ]
        
        current_version = "Unknown"
        version_date = "Unknown"
        
        # 각 패턴을 순서대로 시도
        for pattern in version_patterns:
            version_match = re.search(pattern, content, re.IGNORECASE)
            if version_match:
                current_version = version_match.group(1)
                version_date = version_match.group(2).strip()
                break
        
        # 개요 추출 (다양한 형식 지원)
        overview_patterns = [
            r'##\s*📌\s*개요\s*\n(.*?)\n\n',
            r'##\s*Overview\s*\n(.*?)\n\n',
            r'##\s*Description\s*\n(.*?)\n\n',
            r'##\s*About\s*\n(.*?)\n\n',
        ]
        
        overview = ""
        for pattern in overview_patterns:
            overview_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if overview_match:
                overview = overview_match.group(1).strip()
                break
        
        # 개요가 없으면 첫 번째 문단을 사용
        if not overview:
            first_para = re.search(r'^[^#\n].*?(?:\n\n|\n---|\Z)', content, re.DOTALL | re.MULTILINE)
            if first_para:
                overview = first_para.group(0).strip()
        
        # 현재 버전 섹션 추출 (유연한 매칭)
        improvements = []
        main_update = ""
        
        # 버전 섹션 찾기 (다양한 헤더 레벨 지원)
        version_section_patterns = [
            rf'##\s*📌\s*V{re.escape(current_version)}.*?\n(.*?)(?=##\s*📌\s*V[\d.]|##\s*V[\d.]|\Z)',  # ## 📌 V1.1
            rf'###\s*\*\*V?{re.escape(current_version)}\*\*.*?\n(.*?)(?=###\s*\*\*V?[\d.]|##\s*V?[\d.]|\Z)',
            rf'###\s*V?{re.escape(current_version)}.*?\n(.*?)(?=###\s*V?[\d.]|##\s*V?[\d.]|\Z)',
            rf'##\s*\*\*V?{re.escape(current_version)}\*\*.*?\n(.*?)(?=##\s*\*\*V?[\d.]|#\s*V?[\d.]|\Z)',
            rf'##\s*V?{re.escape(current_version)}.*?\n(.*?)(?=##\s*V?[\d.]|#\s*V?[\d.]|\Z)',
        ]
        
        section_text = ""
        for pattern in version_section_patterns:
            current_version_section = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if current_version_section:
                section_text = current_version_section.group(1)
                break
        
        if section_text:
            # 주요 업데이트 추출 (다양한 형식)
            update_patterns = [
                # 표준 템플릿 형식 (최우선)
                r'\*\*요약\*\*:\s*([^\n]+)',                       # **요약**: 내용 ⭐ 표준
                # 기존 복잡한 형식들 (하위 호환)
                r'\*\*(최근 날짜 기반 출석 컬럼 검색 로직 개선)\*\*',
                r'###\s*🔄\s*개선 사항\s*\n\*\*([^\*\n]+)\*\*',
                r'\*\*주요 업데이트:?\s*([^\*\n]+)\*\*',
                r'\*\*Main Update:?\s*([^\*\n]+)\*\*',
                r'\*\*Update:?\s*([^\*\n]+)\*\*',
                r'주요 업데이트:?\s*([^\n]+)',
                r'Main Update:?\s*([^\n]+)',
            ]
            
            for pattern in update_patterns:
                update_match = re.search(pattern, section_text, re.IGNORECASE)
                if update_match:
                    main_update = update_match.group(1).strip()
                    break
            
            # 핵심 개선사항 추출 (다양한 헤더 형식)
            improvements_patterns = [
                # 표준 템플릿 형식 (최우선)
                r'###\s*변경사항\s*\n(.*?)(?=###|\n##|\Z)',        # ### 변경사항 ⭐ 표준
                r'###\s*주요 기능\s*\n(.*?)(?=###|\n##|\Z)',        # ### 주요 기능
                r'###\s*버그 수정\s*\n(.*?)(?=###|\n##|\Z)',        # ### 버그 수정
                # 기존 복잡한 형식들 (하위 호환)
                r'####\s*✨\s*주요 변경\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'####\s*🎯\s*핵심 개선사항\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'####\s*핵심 개선사항\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'####\s*주요 변경\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'####\s*Key Improvements?\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'####\s*Improvements?\s*\n(.*?)(?=####|\n###|\n##|\Z)',
                r'###\s*Changes?\s*\n(.*?)(?=###|\n##|\Z)',
                r'###\s*Features?\s*\n(.*?)(?=###|\n##|\Z)',
            ]
            
            for pattern in improvements_patterns:
                improvements_section = re.search(pattern, section_text, re.DOTALL | re.IGNORECASE)
                if improvements_section:
                    imp_text = improvements_section.group(1)
                    improvements = [line.strip() for line in imp_text.split('\n') 
                                   if line.strip() and re.match(r'^[-✅✓•*]\s', line.strip())]
                    break
            
            # 개선사항이 없으면 섹션의 모든 리스트 항목 수집
            if not improvements:
                all_items = re.findall(r'^[-✅✓•*]\s+(.+)$', section_text, re.MULTILINE)
                improvements = [f"- {item}" if not item.startswith(('-', '✅', '✓', '•', '*')) else item 
                               for item in all_items]
        
        # 기술 스택 추출 (다양한 형식)
        tech_stack = []
        tech_patterns = [
            r'###\s*핵심 라이브러리\s*\n(.*?)(?=###|\n##|\Z)',
            r'###\s*Core Libraries\s*\n(.*?)(?=###|\n##|\Z)',
            r'###\s*Tech Stack\s*\n(.*?)(?=###|\n##|\Z)',
            r'###\s*Technologies\s*\n(.*?)(?=###|\n##|\Z)',
            r'##\s*🛠️?\s*기술 스택\s*\n(.*?)(?=##|\Z)',
            r'##\s*Technology\s*\n(.*?)(?=##|\Z)',
        ]
        
        for pattern in tech_patterns:
            tech_section = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if tech_section:
                tech_text = tech_section.group(1)
                tech_stack = [line.strip() for line in tech_text.split('\n') 
                             if line.strip() and re.match(r'^[-✅✓•*]\s', line.strip())]
                break
        
        # 주요 기능 추출 (다양한 형식)
        features = []
        features_patterns = [
            r'####\s*파일 처리\s*\n(.*?)(?=####|\n###|\n##|\Z)',
            r'####\s*File Processing\s*\n(.*?)(?=####|\n###|\n##|\Z)',
            r'###\s*주요 기능\s*\n(.*?)(?=###|\n##|\Z)',
            r'###\s*Features\s*\n(.*?)(?=###|\n##|\Z)',
            r'###\s*Key Features\s*\n(.*?)(?=###|\n##|\Z)',
            r'##\s*✨\s*주요 기능\s*\n(.*?)(?=##|\Z)',
        ]
        
        for pattern in features_patterns:
            features_section = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if features_section:
                feat_text = features_section.group(1)
                features = [line.strip() for line in feat_text.split('\n') 
                           if line.strip() and re.match(r'^[-✅✓•*]\s', line.strip())]
                break
        
        return {
            'version': current_version,
            'date': version_date,
            'overview': overview,
            'main_update': main_update,
            'improvements': improvements[:10] if improvements else [],  # 상위 10개
            'tech_stack': tech_stack[:8] if tech_stack else [],  # 상위 8개
            'features': features[:12] if features else []  # 상위 12개
        }
    
    except Exception as e:
        print(f"Warning: Could not parse VERSION_HISTORY.md: {e}")
        return None

def generate_status_file():
    """Generate PROJECT_STATUS.md file"""

    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    changed_files = get_git_changed_files()

    # Format changed files list
    if changed_files and changed_files[0]:
        changed_list = '\n'.join([f"- {f}" for f in changed_files])
    else:
        changed_list = "- (No changes)"

    # Get Python files structure
    py_structure = get_python_files_structure(changed_files)

    # Get project name
    project_name = os.path.basename(os.getcwd())

    # Detect project type
    project_types = detect_project_type()
    project_type_str = '\n'.join([f"- {pt}" for pt in project_types])

    # Get main components
    main_components = get_main_components()
    
    # Parse version history if available
    version_info = parse_version_history()

    # Generate content
    if version_info:
        # 버전 정보가 있을 때 - 상세한 내용
        content = f"""# {project_name} - Project Status

## Last Update
- **Date**: {date}
- **Current Version**: V{version_info['version']} ({version_info['date']})
- **Auto-generated**: update-status.py

---

## 📌 Project Overview

{version_info['overview']}

### Current Version Highlights
{('**' + version_info['main_update'] + '**' + chr(10)) if version_info['main_update'] else ''}
{chr(10).join(version_info['improvements'])}

---

## Project File Structure

```
{py_structure}
```

* = Modified in this commit

---

## Modified Files in This Commit

{changed_list}

---

## 🛠️ Technical Stack

### Core Libraries
{chr(10).join(version_info['tech_stack'])}

### Project Type
{project_type_str}

---

## 🎯 Key Features

{chr(10).join(version_info['features'])}

---

## Package Description

(Auto-detected Python project structure)

### Main Components
{main_components}

---

## Important Information

### Python Version
- Check runtime.txt or README for Python version requirements

### Dependencies
- Check requirements.txt or pyproject.toml for package dependencies

### Version History
- See VERSION_HISTORY.md for complete version history and changelog

---

## Checklist for Next Session
1. Share this file (PROJECT_STATUS.md) with AI
2. Specify file location to modify
3. Confirm last modification date
4. Verify final version from file tree
5. Check VERSION_HISTORY.md for detailed changes

---

*Auto-generated by update-status.py - {date}*
*Version information extracted from VERSION_HISTORY.md*
"""
    else:
        # 버전 정보가 없을 때 - 기본 내용
        content = f"""# {project_name} - Project Status

## Last Update
- **Date**: {date}
- **Auto-generated**: update-status.py

---

## Project File Structure

```
{py_structure}
```

* = Modified in this commit

---

## Modified Files in This Commit

{changed_list}

---

## Package Description

(Auto-detected Python project structure)

### Main Components
{main_components}

---

## Important Information

### Project Type
{project_type_str}

### Python Version
- Check runtime.txt or README for Python version requirements

### Dependencies
- Check requirements.txt or pyproject.toml for package dependencies

---

## Checklist for Next Session
1. Share this file (PROJECT_STATUS.md) with AI
2. Specify file location to modify
3. Confirm last modification date
4. Verify final version from file tree

---

*Auto-generated by update-status.py - {date}*
"""

    # Write to file
    with open('PROJECT_STATUS.md', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ PROJECT_STATUS.md generated successfully!")
    if version_info:
        version_file = find_version_history_file()
        print(f"📦 Version V{version_info['version']} information included from {version_file.name if version_file else 'VERSION_HISTORY.md'}")

if __name__ == "__main__":
    generate_status_file()
