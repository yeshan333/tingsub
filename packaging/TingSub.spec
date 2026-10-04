# Build on Apple Silicon with the locked desktop + bundle environment.
import os
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from macholib.MachO import MachO
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
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
# Wheel selection varies with the build host. Declare the actual native floor,
# including dependencies, instead of claiming every locally built App supports 14.
minimum = (14, 0, 0)
for source in {entry[1] for entry in a.binaries} | {exe.name}:
    with open(source, 'rb') as stream:
        magic = stream.read(4)
    if magic not in (b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
                     b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
                     b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
                     b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'):
        continue
    macho = MachO(source)
    for header in macho.headers:
        for load, command, _ in header.commands:
            value = getattr(command, 'minos', 0) if load.cmd == 0x32 else (
                getattr(command, 'version', 0) if load.cmd == 0x24 else 0)
            minimum = max(minimum, (value >> 16, (value >> 8) & 255, value & 255))
minimum_text = '.'.join(map(str, minimum[:2] if minimum[2] == 0 else minimum))
print('Bundled native minimum macOS version:', minimum_text)
app = BUNDLE(collection, name='TingSub.app', bundle_identifier='io.github.yeshan333.tingsub',
             icon=str(root / 'assets/brand/TingSub.icns'),
             info_plist={'CFBundleName': 'TingSub', 'CFBundleDisplayName': 'TingSub',
                         'CFBundleShortVersionString': version, 'CFBundleVersion': version,
                         'LSMinimumSystemVersion': minimum_text,
                         'NSHighResolutionCapable': True})
