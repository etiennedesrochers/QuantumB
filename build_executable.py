#!/usr/bin/env python
"""
Build executable for AutoCAD Electrical Drawing Generator
Requires PyInstaller: pip install pyinstaller
"""
import subprocess
import sys
import shutil
import time
from pathlib import Path

def remove_directory_with_retry(path, max_retries=3, delay=0.5):
    """Remove directory with retries to handle locked files."""
    for attempt in range(max_retries):
        if not path.exists():
            return True
        try:
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                return True
            time.sleep(delay)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Warning: Could not fully remove {path}: {e}")
            time.sleep(delay)
    return False

def build_executable():
    """Build the executable using PyInstaller."""
    project_dir = Path(__file__).parent
    build_dir = project_dir / "dist"
    
    # Clean up existing build artifacts with retries to avoid permission errors
    print("Cleaning up previous build artifacts...")
    remove_directory_with_retry(build_dir, max_retries=3, delay=0.5)
    remove_directory_with_retry(project_dir / "build", max_retries=3, delay=0.5)
    
    # Remove old spec file to ensure fresh generation
    spec_file = project_dir / "QuantumB.spec"
    if spec_file.exists():
        try:
            spec_file.unlink()
        except Exception as e:
            print(f"Warning: Could not remove spec file: {e}")
    
    # PyInstaller command with optimizations for this application
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",  # Create a single executable file
        "--windowed",  # Hide console window on Windows
        "--name=QuantumB",  # Output executable name
        "--distpath=dist",  # Output directory
        "--workpath=build",  # Build directory
        "--specpath=.",  # Spec file location
        "--add-data=templates:templates",  # Include templates folder
        "--add-data=symbols:symbols",  # Include symbols folder
        "--add-data=order_file:order_file",  # Include order file folder
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=ezdxf",
        "--hidden-import=pandas",
        str(project_dir / "app.py"),  # Entry point
    ]
    
    # Add icon if it exists
    icon_path = project_dir / "app.ico"
    if icon_path.exists():
        cmd.insert(5, f"--icon={icon_path}")
    else:
        print("Note: app.ico not found, building without icon")
    
    print("Building executable...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_dir)
    
    if result.returncode == 0:
        print("\n✓ Executable built successfully!")
        print(f"Location: {build_dir / 'QuantumB.exe'}")
    else:
        print("\n✗ Build failed!")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()

if __name__ == "__main__":
    build_executable()
