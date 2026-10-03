import hashlib
import shutil
from pathlib import Path


def whisper_directory(source: Path, data_dir: Path) -> Path:
    """Adapt newer MLX checkpoint filenames to mlx-whisper 0.4's local layout.

    Keep upstream snapshots immutable. Symlinks avoid duplicating large weights.
    """
    if (source / "weights.safetensors").is_file() or (source / "weights.npz").is_file():
        return source
    weights = source / "model.safetensors"
    if not weights.is_file():
        raise ValueError("Whisper 本地权重不完整，请重新下载模型")
    digest = hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:16]
    target = data_dir / "asr-compat" / digest
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "config.json", target / "config.json")
    link = target / "weights.safetensors"
    if not link.exists():
        link.symlink_to(weights.resolve())
    return target
