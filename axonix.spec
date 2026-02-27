# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\akikf\\programing\\nn\\axonix\\web\\static', 'axonix/web/static')]
binaries = []
hiddenimports = ['axonix.core.agent', 'axonix.core.runner', 'axonix.core.backend', 'axonix.core.cli', 'axonix.core.config', 'axonix.core.history', 'axonix.core.loop', 'axonix.core.memory', 'axonix.core.models', 'axonix.core.first_run', 'axonix.tools.file_tools', 'axonix.tools.shell_tools', 'axonix.tools.web_tools', 'axonix.tools.code_tools', 'axonix.agents.specialized', 'axonix.web.server']
tmp_ret = collect_all('ollama')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('llama_cpp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\akikf\\programing\\nn\\axonix_main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'cv2', 'torch', 'tensorflow', 'numpy', 'PyQt6', 'PySide6', 'PyQt5', 'PySide2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='axonix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
