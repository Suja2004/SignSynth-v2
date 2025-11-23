# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import nltk

block_cipher = None

# Paths
venv_path = r'C:\Users\DELL\PycharmProjects\render3D\.venv\Lib\site-packages'
project_path = r'C:\Users\DELL\PycharmProjects\SignSynthv2'
panda3d_path = os.path.join(project_path, '.venv', 'Lib', 'site-packages', 'panda3d')

nltk_data_dirs = []
for path in nltk.data.path:
    if os.path.exists(path):
        nltk_data_dirs.append(path)
        print(f"Found NLTK data at: {path}")

nltk_datas = []
if nltk_data_dirs:
    nltk_data_dir = nltk_data_dirs[0]

    for subdir in ['tokenizers', 'corpora', 'taggers']:
        src = os.path.join(nltk_data_dir, subdir)
        if os.path.exists(src):
            nltk_datas.append((src, f'nltk_data/{subdir}'))
            print(f"Adding NLTK data: {src}")
else:
    print("WARNING: No NLTK data found! App may need to download at runtime.")

a = Analysis(
    [os.path.join(project_path, 'main.py')],
    pathex=[],
    binaries=[
        (os.path.join(project_path, '.venv', 'Lib', 'site-packages', 'vosk', 'libvosk.dll'), 'vosk'),

        # --- FIX 1: Move plugins to root ('.') instead of 'plugins' ---
        (os.path.join(panda3d_path, 'libpandagl.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3tinydisplay.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandadx9.dll'), '.'),
        (os.path.join(panda3d_path, 'cgD3D9.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3assimp.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3ptloader.dll'), '.'),

        # --- FIX 2: Add libp3windisplay.dll (REQUIRED for Windows) ---
        (os.path.join(panda3d_path, 'libp3windisplay.dll'), '.'),

        # Standard Panda3D DLLs
        (os.path.join(panda3d_path, 'libp3direct.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3dtool.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3dtoolconfig.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3interrogatedb.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3ffmpeg.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3fmod_audio.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3vision.dll'), '.'),
        (os.path.join(panda3d_path, 'libp3vrpn.dll'), '.'),
        (os.path.join(panda3d_path, 'libpanda.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaexpress.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaegg.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaphysics.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaskel.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandafx.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaai.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandabullet.dll'), '.'),
        (os.path.join(panda3d_path, 'libpandaode.dll'), '.'),
        (os.path.join(panda3d_path, 'MSVCP140.dll'), '.'),
        (os.path.join(panda3d_path, '*.pyd'), '.'),
    ],
    datas=[
        (os.path.join(project_path, 'sign_poses.json'), './'),
        (os.path.join(project_path, 'SignSynth.ico'), './'),
        (os.path.join(project_path, 'character'), 'character'),
        (os.path.join(project_path, 'skybox'), 'skybox'),
        (os.path.join(project_path, 'vosk-model-small-en-us-0.15'), 'vosk-model-small-en-us-0.15'),
        (os.path.join(panda3d_path, 'etc'), 'etc'),
        (panda3d_path, 'panda3d'),
    ] + nltk_datas,
    hiddenimports=[
        'panda3d.core',
        'direct.showbase.ShowBase',
        'direct.task',
        'direct.task.Task',
        'direct.gui.DirectGui',
        'direct.gui.DirectButton',
        'direct.gui.DirectFrame',
        'direct.gui.OnscreenText',
        'direct.interval.IntervalGlobal',
        'direct.interval.LerpInterval',
        'pandac.PandaModules',
        'win32com.client',
        'pyaudio',
        'vosk',
        'nltk',
        'requests',
        'packaging',
        'packaging.version',
        'packaging.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SignSynth',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    icon=r'C:\Users\DELL\PycharmProjects\SignSynthv2\SignSynth.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='SignSynth'
)
