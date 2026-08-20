#!/usr/bin/env python3
"""
Portable Executable Builder Script
Packages Universal Image Toolkit into a standalone portable single-file executable using PyInstaller.
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    current_os = platform.system()
    print(f"==================================================")
    print(f"  Building Universal Image Toolkit for {current_os}")
    print(f"==================================================")

    base_dir = Path(__file__).parent.resolve()
    app_entry = base_dir / "app.py"

    # Clean previous build artifacts
    dist_dir = base_dir / "dist"
    build_dir = base_dir / "build"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Determine icon file
    icon_flag = []
    if current_os == "Darwin" and (base_dir / "assets" / "icon.icns").exists():
        icon_flag = [f"--icon={base_dir / 'assets' / 'icon.icns'}"]
    elif (base_dir / "assets" / "icon.ico").exists():
        icon_flag = [f"--icon={base_dir / 'assets' / 'icon.ico'}"]

    # Separator for --add-data
    sep = ";" if current_os == "Windows" else ":"
    data_flag = [f"--add-data={base_dir / 'assets'}{sep}assets"]

    # Base PyInstaller arguments
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=UniversalImageToolkit",
        "--onefile",
        "--windowed",
        "--noconsole",
        "--clean",
        "--collect-all=customtkinter",
        *icon_flag,
        *data_flag,
        f"--paths={base_dir}",
        str(app_entry),
    ]

    print("\nRunning build command:")
    print(" ".join(cmd))
    print("\nCompiling... please wait.")

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("🎉 Build Succeeded!")
        print("=" * 50)
        if current_os == "Windows":
            print(f"Standalone Portable Executable: {dist_dir / 'UniversalImageToolkit.exe'}")
        elif current_os == "Darwin":
            print(f"Standalone Portable App / Binary: {dist_dir / 'UniversalImageToolkit'}")
        else:
            print(f"Standalone Portable Binary: {dist_dir / 'UniversalImageToolkit'}")
        print("\nYou can now distribute this single file anywhere without needing Python installed!")
    else:
        print("\n❌ Build Failed. See logs above for details.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
