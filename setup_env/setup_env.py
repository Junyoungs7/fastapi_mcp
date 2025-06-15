import os
import platform
import subprocess
from pathlib import Path

# 현재 스크립트 경로 기준
BASE_DIR = Path(__file__).resolve().parent.parent
VENV_NAME = "mcp"
VENV_DIR = BASE_DIR / VENV_NAME
REQUIREMENTS_FILE = BASE_DIR / "setup_env" / "requirements.txt"

def create_virtualenv():
    if VENV_DIR.exists():
        print(f"✅ 가상환경 '{VENV_NAME}' 이미 존재: {VENV_DIR}")
        return

    print(f"🌀 uv로 가상환경 생성 중 (경로: {VENV_DIR})...")
    subprocess.check_call(["uv", "venv", str(VENV_DIR)])
    print(f"✅ 가상환경 생성 완료")

def install_pip_if_missing(python_exec: Path):
    try:
        subprocess.check_call([str(python_exec), "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        print("📦 pip이 설치되지 않음. ensurepip로 설치 중...")
        subprocess.check_call([str(python_exec), "-m", "ensurepip"])
        subprocess.check_call([str(python_exec), "-m", "pip", "install", "--upgrade", "pip"])

def install_requirements():
    if not REQUIREMENTS_FILE.exists():
        print(f"⚠️ {REQUIREMENTS_FILE} 없음. 설치 생략.")
        return

    if platform.system() == "Windows":
        python_exec = VENV_DIR / "Scripts" / "python.exe"
    else:
        python_exec = VENV_DIR / "bin" / "python3"

    install_pip_if_missing(python_exec)

    print(f"📦 requirements.txt 설치 중...")
    subprocess.check_call([str(python_exec), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])

def main():
    print("🚀 환경 설정 시작")
    create_virtualenv()
    install_requirements()

if __name__ == "__main__":
    main()
