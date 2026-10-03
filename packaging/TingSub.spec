# Build on Apple Silicon with the locked desktop + bundle environment.
import os
from importlib.metadata import distributions
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
binaries, datas, hidden = [], [], []
for package in ('mlx', 'mlx_whisper', 'mlx_lm', 'tiktoken', 'tokenizers', 'webview'):
    data, binary, modules = collect_all(package)
    datas += data
    binaries += binary
    hidden += modules
for package in ('mlx-lm', 'mlx-whisper', 'transformers', 'tokenizers', 'huggingface-hub', 'tqdm', 'regex', 'numpy', 'safetensors', 'packaging', 'pyyaml', 'requests'):
    datas += copy_metadata(package)
# Preserve dependency license files and metadata, including native wheels.
for distribution in distributions():
    if distribution.metadata['Name'] not in ('tingsub',):
        datas += copy_metadata(distribution.metadata['Name'])
hidden += collect_submodules('mlx_lm.models')
hidden += ['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
           'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on', 'webview.platforms.cocoa']
datas += [(str(root / 'src/live_subs/desktop_ui'), 'live_subs/desktop_ui'),
          (str(root / 'extension'), 'extension'), (str(root / 'LICENSE'), 'notices'),
          (str(root / 'docs/en/models.md'), 'notices')]
a = Analysis([str(root / 'packaging/desktop_entry.py')], pathex=[str(root / 'src')],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             hookspath=[str(root / "packaging/hooks")],
             excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'IPython', 'pytest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='TingSub', console=False,
          target_arch='arm64', codesign_identity=os.environ.get('TINGSUB_CODESIGN_IDENTITY'))
collection = COLLECT(exe, a.binaries, a.datas, name='TingSub')
app = BUNDLE(collection, name='TingSub.app', bundle_identifier='io.github.yeshan333.tingsub',
             info_plist={'CFBundleName': 'TingSub', 'CFBundleDisplayName': 'TingSub',
                         'CFBundleShortVersionString': '0.1.0', 'LSMinimumSystemVersion': '14.0',
                         'NSHighResolutionCapable': True})
