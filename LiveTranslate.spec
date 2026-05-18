# -*- mode: python ; coding: utf-8 -*-
import os
import shutil

from PyInstaller.utils.hooks import collect_all

datas = [('vendor', 'vendor')]
binaries = []
hiddenimports = ['pyaudiowpatch', 'webrtcvad']
tmp_ret = collect_all('argostranslate')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('faster_whisper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ctranslate2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tokenizers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sentencepiece')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['packaging_hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'stanza', 'onnxruntime', 'spacy', 'torchvision', 'torchaudio', 'tensorflow', 'keras'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LiveTranslate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LiveTranslate',
)

# PyQt5 wheels can carry an older VC runtime in Qt5/bin. Because Qt is
# imported before faster-whisper/ctranslate2 runs inference, Windows may keep
# that older MSVCP140.dll loaded for the whole process and native inference can
# crash with APPCRASH in MSVCP140.dll. Keep the bundled Qt runtime in sync with
# the system VC runtime used by modern C++ wheels.
qt_bin_dir = os.path.join(DISTPATH, 'LiveTranslate', '_internal', 'PyQt5', 'Qt5', 'bin')
system32_dir = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
for dll_name in (
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll',
):
    source = os.path.join(system32_dir, dll_name)
    if os.path.exists(source) and os.path.isdir(qt_bin_dir):
        shutil.copy2(source, os.path.join(qt_bin_dir, dll_name))
