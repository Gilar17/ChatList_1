"""Сборка ChatList.exe с версией из version.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from version import __version__

PROJECT_DIR = Path(__file__).resolve().parent
DIST_DIR = PROJECT_DIR / "dist"
EXE_NAME = "ChatList.exe"


def build_exe(python_executable: str | None = None) -> Path:
    python = python_executable or sys.executable
    icon_path = PROJECT_DIR / "app.ico"
    command = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name=ChatList",
        "--collect-all",
        "PyQt6",
    ]
    if icon_path.is_file():
        command.append(f"--icon={icon_path}")
    command.append("main.py")

    subprocess.check_call(command, cwd=PROJECT_DIR)
    exe_path = DIST_DIR / EXE_NAME
    if not exe_path.is_file():
        raise FileNotFoundError(f"Не найден собранный файл: {exe_path}")
    return exe_path


if __name__ == "__main__":
    output_path = build_exe()
    print(f"Сборка завершена: {output_path} (версия {__version__})")
