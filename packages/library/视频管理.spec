# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/templates', 'templates'),
        ('src/static', 'static'),
        ('docs', 'docs'),
        ('runtime/data/config.json', '.'),
        ('runtime/data/prompt.txt', '.'),
        ('requirements.txt', '.'),
        # vendor-upload-pkg 核心文件（已移至 src/）
        ('src/vendor-upload-pkg/upload.py', 'vendor-upload-pkg'),
        ('src/vendor-upload-pkg/cookie.txt.template', 'vendor-upload-pkg'),
        ('src/vendor-upload-pkg/src/rotate_session.py', 'vendor-upload-pkg/src'),
        ('src/vendor-upload-pkg/docs/README.md', 'vendor-upload-pkg/docs'),
    ],
    hiddenimports=[
        'flask', 'werkzeug', 'requests',
        'device_monitor', 'copy_progress_window',
        'rotate_video', 'split_video',
        '_upload_now', 'app', 'run',
        'models', 'services', 'utils', 'routes',
        'models.csv_store', 'models.dim_registry',
        'services.lazy_loader', 'services.video',
        'services.preprocess_service', 'services.scan_service',
        'services.upload_service', 'services.data_service',
        'services.dim_service', 'services.upload_options',
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
