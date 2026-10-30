# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('docs', 'docs'),
        ('config.json', '.'),
        ('prompt.txt', '.'),
        ('requirements.txt', '.'),
        # vendor-upload-pkg 核心文件
        ('vendor-upload-pkg/upload.py', 'vendor-upload-pkg'),
        ('vendor-upload-pkg/cookie.txt.template', 'vendor-upload-pkg'),
        ('vendor-upload-pkg/src/rotate_session.py', 'vendor-upload-pkg/src'),
        ('vendor-upload-pkg/docs/README.md', 'vendor-upload-pkg/docs'),
    ],
    hiddenimports=[
        'flask', 'werkzeug', 'requests',
        'device_monitor', 'copy_progress_window',
        'rotate_video', 'split_video',
        '_upload_now', 'app', 'run',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinterdnd2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='视频管理',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='视频管理',
)
