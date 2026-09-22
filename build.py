#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil


def install_requirements():
    print('Installing dependencies...')
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
            check=True,
        )
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'pyinstaller'],
            check=True,
        )
        subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'],
            check=True,
        )
        print('Dependencies installed.')
        return True
    except subprocess.CalledProcessError as e:
        print(f'Failed to install dependencies: {e}')
        return False


def download_adb():
    if os.path.exists(os.path.join('adb_tools', 'adb.exe')):
        print('ADB already present in adb_tools/.')
        return True
    print('Downloading ADB Platform Tools...')
    try:
        subprocess.run([sys.executable, 'download_adb.py'], check=True)
        print('ADB downloaded.')
        return True
    except subprocess.CalledProcessError as e:
        print(f'Failed to download ADB: {e}')
        return False


def build_executable():
    print('Building executable from main.py...')
    try:
        os.makedirs('dist', exist_ok=True)
        sep = ';' if os.name == 'nt' else ':'
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--onefile',
            '--windowed',
            '--name', 'EVONY_Auto',
            '--add-data', f'images{sep}images',
            '--add-data', f'actions{sep}actions',
            '--add-data', f'components{sep}components',
            '--add-data', f'utils{sep}utils',
            '--add-data', f'adb_tools{sep}adb_tools',
            '--add-data', f'config.json{sep}.',
            '--hidden-import', 'cv2',
            '--hidden-import', 'numpy',
            '--hidden-import', 'tkinter',
            '--hidden-import', 'playwright',
            '--collect-all', 'cv2',
            '--collect-all', 'numpy',
            '--collect-all', 'playwright',
            'main.py',
        ]
        subprocess.run(cmd, check=True)
        print('Build succeeded.')
        return True
    except subprocess.CalledProcessError as e:
        print(f'Build failed: {e}')
        return False


def cleanup():
    for dir_name in ('build', '__pycache__'):
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)


def main():
    print('Building EVONY Auto v2 (Drag & Drop)...')
    print('=' * 50)
    if not install_requirements():
        return False
    if not download_adb():
        return False
    if not build_executable():
        return False
    cleanup()
    print('=' * 50)
    print('Done. Executable: dist/EVONY_Auto.exe')
    return True


if __name__ == '__main__':
    if not main():
        sys.exit(1)
