"""Download, validate and atomically activate model pairs without losing a working pair."""

import fnmatch
import json
import os
import stat
import tempfile
from pathlib import Path

from .catalog import CATALOG, DEFAULT_ASR, DEFAULT_TRANSLATION
from .downloads import DownloadProgress, validate_download

PATTERNS = ["*.json", "*.safetensors", "*.npz", "*.txt", "*.model", "*.jinja"]


def read_config(path):
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Invalid model configuration: {path.name}")
    return value


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.stem + "-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def snapshot_status(item):
    """Return readiness and weight bytes without following missing cache blobs."""
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        return False, 0
    path = Path(item["path"])
    try:
        weights = list(path.glob("*.safetensors")) + list(path.glob("*.npz"))
        details = [weight.stat() for weight in weights]
        if not (path / "config.json").is_file() or not details:
            return False, 0
        if not all(stat.S_ISREG(info.st_mode) for info in details):
            return False, 0
        return True, sum(info.st_size for info in details)
    except OSError:
        # Snapshot links may outlive their blobs, or a cache may disappear
        # between scanning the directory and reading the file metadata.
        return False, 0


def complete(item):
    return snapshot_status(item)[0]


def selection_at(directory):
    active = read_config(directory / "models.json")
    return {
        kind: active.get(kind, {}).get("repo", default)
        for kind, default in (("asr", DEFAULT_ASR), ("translation", DEFAULT_TRANSLATION))
    }


def validate_selection(directory, selection):
    if not isinstance(selection, dict) or set(selection) != {"asr", "translation"}:
        raise ValueError("Choose one speech model and one translation model")
    current = selection_at(directory)
    for kind, repo in selection.items():
        allowed = {item["repo"] for item in CATALOG if item["kind"] == kind} | {current[kind]}
        if not isinstance(repo, str) or repo not in allowed:
            raise ValueError("Unsupported model selection")
    return selection


def catalog_at(directory):
    active = read_config(directory / "models.json")
    library = read_config(directory / "model-library.json")
    for item in active.values():
        if isinstance(item, dict) and item.get("repo"):
            library[item["repo"]] = item
    catalog = [dict(item, downloaded=complete(library.get(item["repo"]))) for item in CATALOG]
    for kind, item in active.items():
        if isinstance(item, dict) and item.get("repo") not in {entry["repo"] for entry in catalog}:
            catalog.append(
                {
                    "kind": kind,
                    "repo": item["repo"],
                    "name": item["repo"],
                    "description": {"zh-CN": "当前自定义模型", "en": "Current custom model"},
                    "license": "See upstream",
                    "downloaded": complete(item),
                }
            )
    return catalog


def prepare_models(
    directory,
    asr=None,
    translation=None,
    *,
    force=False,
    validate=False,
    downloader=None,
    revision_for=None,
    engine_factory=None,
    download=None,
):
    directory.mkdir(parents=True, exist_ok=True)
    source = validate_download(download or read_config(directory / "download.json") or None)
    atomic_json(directory / "download.json", source)
    active = read_config(directory / "models.json")
    library = read_config(directory / "model-library.json")
    selected = selection_at(directory)
    selected.update(
        {kind: repo for kind, repo in (("asr", asr), ("translation", translation)) if repo}
    )
    for item in active.values():
        if isinstance(item, dict) and item.get("repo"):
            library[item["repo"]] = item
    api = None
    if downloader is None or revision_for is None:
        from huggingface_hub import HfApi, snapshot_download

        downloader = downloader or snapshot_download
        if revision_for is None:
            api = HfApi(endpoint=source["endpoint"], token=False)

    def progress(stage, kind="", repo="", error="", **details):
        atomic_json(
            directory / "preparation.json",
            {
                "stage": stage,
                "kind": kind,
                "repo": repo,
                "error": error,
                "source": source["source"],
                **details,
            },
        )

    candidate = directory / "candidate-models.json"
    try:
        result = {}
        for index, (kind, repo) in enumerate(selected.items(), 1):
            previous = library.get(repo, {})
            if not force and complete(previous) and previous.get("revision"):
                result[kind] = previous
                print(f"复用 {repo} @ {previous['revision']}", flush=True)
                continue
            progress("resolve", kind, repo, index=index, count=len(selected))
            info = api.model_info(repo, files_metadata=True) if api else None
            revision = info.sha if info else revision_for(repo)
            files = (
                [
                    item
                    for item in info.siblings
                    if any(fnmatch.fnmatch(item.rfilename, pattern) for pattern in PATTERNS)
                ]
                if info
                else []
            )
            total = (
                sum(item.size for item in files)
                if files and all(item.size is not None for item in files)
                else None
            )
            snapshot = (
                directory
                / "model-cache"
                / ("models--" + repo.replace("/", "--"))
                / "snapshots"
                / revision
            )
            cached = sum(
                item.size or 0
                for item in files
                if (snapshot / item.rfilename).is_file()
                and (snapshot / item.rfilename).stat().st_size == item.size
            )
            tracker = DownloadProgress(
                lambda details, kind=kind, repo=repo, index=index: progress(
                    "download", kind, repo, index=index, count=len(selected), **details
                ),
                total=total,
                cached=cached,
            )
            tracker.report(0, force=True)
            print(f"下载 {kind}: {repo} @ {revision}", flush=True)
            try:
                path = downloader(
                    repo,
                    revision=revision,
                    cache_dir=str(directory / "model-cache"),
                    allow_patterns=PATTERNS,
                    endpoint=source["endpoint"],
                    token=False,
                    tqdm_class=tracker.progress_class(),
                )
            finally:
                tracker.finish()
            item = {"repo": repo, "revision": revision, "path": str(path)}
            if not complete(item):
                raise ValueError(f"Incomplete model snapshot: {repo}")
            library[repo] = result[kind] = item
            atomic_json(directory / "model-library.json", library)
        atomic_json(directory / "model-library.json", library)
        atomic_json(candidate, result)
        if validate:
            progress("validate")
            print("正在实际加载并预热所选模型；完成前继续保留原配置。", flush=True)
            if engine_factory is None:
                from .engine import MLXEngine

                engine_factory = MLXEngine
            engine = engine_factory(candidate)
            engine.translate("今日は新しい技術について話します。", "ja", "zh-en")
        os.replace(candidate, directory / "models.json")
        progress("complete")
        print("所选模型已就绪，配置已更新。", flush=True)
        return result
    except Exception as exc:
        progress("error", error=str(exc))
        raise
    finally:
        candidate.unlink(missing_ok=True)
