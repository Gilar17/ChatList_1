"""Сборка установщика ChatList для Windows (Inno Setup)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from build import EXE_NAME, PROJECT_DIR, build_exe
from version import __version__

INSTALLER_DIR = PROJECT_DIR / "installer"
OUTPUT_DIR = PROJECT_DIR / "install"
ISS_PATH = INSTALLER_DIR / "chatlist.iss"


def find_inno_compiler() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    compiler = shutil.which("ISCC")
    if compiler:
        return Path(compiler)
    raise FileNotFoundError(
        "Не найден компилятор Inno Setup (ISCC.exe). "
        "Установите Inno Setup 6: https://jrsoftware.org/isinfo.php"
    )


def generate_iss(app_version: str) -> None:
    icon_path = PROJECT_DIR / "app.ico"
    setup_icon_line = f"SetupIconFile={icon_path}" if icon_path.is_file() else ""
    uninstall_icon_line = (
        f"UninstallDisplayIcon={{app}}\\{EXE_NAME}" if icon_path.is_file() else ""
    )
    version_info = f"{app_version}.0" if app_version.count(".") == 2 else app_version

    iss_text = """; Автоматически сгенерировано build_installer.py из version.py

#define MyAppName "ChatList"
#define MyAppVersion "{app_version}"
#define MyAppPublisher "ChatList"
#define MyAppExeName "{exe_name}"

[Setup]
AppId={{{{8F4E2A61-9C3D-4B17-A6E5-1D9F7C842B10}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{#MyAppName}} {{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=no
OutputDir=..\\install
OutputBaseFilename=ChatList-{{#MyAppVersion}}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
{setup_icon_line}
{uninstall_icon_line}
UninstallDisplayName={{#MyAppName}} {{#MyAppVersion}}
CreateUninstallRegKey=yes
Uninstallable=yes
VersionInfoVersion={version_info}
VersionInfoProductVersion={version_info}
VersionInfoCompany={{#MyAppPublisher}}
VersionInfoDescription=Установщик {{#MyAppName}}
VersionInfoProductName={{#MyAppName}}
VersionInfoProductTextVersion={{#MyAppVersion}}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\\dist\\{exe_name}"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Comment: "ChatList {{#MyAppVersion}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon; Comment: "ChatList {{#MyAppVersion}}"

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Запустить {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
""".format(
        app_version=app_version,
        exe_name=EXE_NAME,
        version_info=version_info,
        setup_icon_line=setup_icon_line,
        uninstall_icon_line=uninstall_icon_line,
    )
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ISS_PATH.write_text(iss_text, encoding="utf-8")


def build_installer(python_executable: str | None = None) -> Path:
    python = python_executable or sys.executable

    subprocess.check_call([python, "-m", "pip", "install", "pyinstaller"], cwd=PROJECT_DIR)

    exe_path = build_exe(python_executable=python)
    print(f"Исполняемый файл: {exe_path}")

    generate_iss(__version__)
    print(f"Сценарий Inno Setup: {ISS_PATH}")

    compiler = find_inno_compiler()
    subprocess.check_call([str(compiler), str(ISS_PATH)], cwd=INSTALLER_DIR)

    installer_path = OUTPUT_DIR / f"ChatList-{__version__}-Setup.exe"
    if not installer_path.is_file():
        raise FileNotFoundError(f"Не найден установщик: {installer_path}")
    return installer_path


if __name__ == "__main__":
    result = build_installer()
    print(f"Установщик создан: {result}")
