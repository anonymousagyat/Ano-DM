"""
Build Script for Ano-Download Manager (Ano-DM)
Packages the application into a standalone Windows executable using PyInstaller.
"""

import os
import sys
import shutil
import PyInstaller.__main__

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT_DIR)

assets_dir = os.path.join(ROOT_DIR, "assets")
icon_ico = os.path.join(assets_dir, "icon.ico")
dist_dir = os.path.join(ROOT_DIR, "dist")
build_dir = os.path.join(ROOT_DIR, "build")

args = [
    "ano_dm.py",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "Ano-DM",
    "--distpath", dist_dir,
    "--workpath", build_dir,
    "--specpath", ROOT_DIR,
    "--icon", icon_ico,
    "--add-data", f"{assets_dir};assets",
    "--add-data", f"{assets_dir};.",
    "--collect-all", "customtkinter",
    "--hidden-import", "win32gui",
    "--hidden-import", "win32ui",
    "--hidden-import", "win32con",
    "--hidden-import", "win32com.shell.shell",
]

print("=" * 65)
print(" Building Ano-DM Standalone Windows Executable")
print("=" * 65)
print("Root directory:", ROOT_DIR)
print("Assets directory:", assets_dir)
print("Running PyInstaller...")

PyInstaller.__main__.run(args)

# Clean up build directory after compilation
if os.path.exists(build_dir):
    try:
        shutil.rmtree(build_dir)
        print("Cleaned temporary build artifacts.")
    except Exception:
        pass

print("\nAno-DM build finished successfully!")
print(f"Executable location: {os.path.join(dist_dir, 'Ano-DM', 'Ano-DM.exe')}")
