"""Transaction tests inject a loader; actual MLX inference is checked separately."""

import json
from unittest.mock import Mock

import pytest

from live_subs.catalog import DEFAULT_ASR, DEFAULT_TRANSLATION
from live_subs.model_manager import catalog_at, prepare_models, validate_selection


def snapshot(directory, repo):
    folder = directory / repo.replace("/", "--")
    folder.mkdir(exist_ok=True)
    (folder / "config.json").write_text("{}")
    (folder / "weights.safetensors").write_bytes(b"fixture: not inference weights")
    return {"repo": repo, "revision": "pinned-revision", "path": str(folder)}


@pytest.fixture
def current(tmp_path):
    active = {
        "asr": snapshot(tmp_path, DEFAULT_ASR),
        "translation": snapshot(tmp_path, DEFAULT_TRANSLATION),
    }
    (tmp_path / "models.json").write_text(json.dumps(active))
    return active


def test_failed_new_model_load_keeps_working_pair_and_cached_download_for_retry(tmp_path, current):
    old = (tmp_path / "models.json").read_bytes()
    repo = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
    download = Mock(side_effect=lambda repo, **_: snapshot(tmp_path, repo)["path"])
    with pytest.raises(RuntimeError, match="cannot load"):
        prepare_models(
            tmp_path,
            translation=repo,
            validate=True,
            downloader=download,
            revision_for=lambda _: "new-revision",
            engine_factory=Mock(side_effect=RuntimeError("cannot load")),
        )
    assert (tmp_path / "models.json").read_bytes() == old
    assert not (tmp_path / "candidate-models.json").exists()
    assert json.loads((tmp_path / "preparation.json").read_text())["stage"] == "error"
    assert next(item for item in catalog_at(tmp_path) if item["repo"] == repo)["downloaded"]
    engine = Mock()
    prepare_models(
        tmp_path,
        translation=repo,
        validate=True,
        downloader=download,
        revision_for=lambda _: "unexpected-network-call",
        engine_factory=engine,
    )
    assert download.call_count == 1
    engine.return_value.translate.assert_called_once()
    assert json.loads((tmp_path / "models.json").read_text())["translation"]["repo"] == repo


def test_returning_to_previous_pair_works_offline_without_redownloading(tmp_path, current):
    repo = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
    prepare_models(
        tmp_path,
        translation=repo,
        downloader=lambda repo, **_: snapshot(tmp_path, repo)["path"],
        revision_for=lambda _: "revision",
        validate=True,
        engine_factory=Mock(),
    )
    offline = Mock(side_effect=AssertionError("Network must not be used"))
    restored = prepare_models(
        tmp_path,
        translation=DEFAULT_TRANSLATION,
        downloader=offline,
        revision_for=offline,
        validate=True,
        engine_factory=Mock(),
    )
    assert restored == current
    offline.assert_not_called()


def test_interrupted_download_does_not_replace_active_model_pair(tmp_path, current):
    with pytest.raises(KeyboardInterrupt):
        prepare_models(
            tmp_path,
            translation="new/model",
            revision_for=lambda _: "rev",
            downloader=Mock(side_effect=KeyboardInterrupt),
        )
    assert json.loads((tmp_path / "models.json").read_text()) == current
    assert not (tmp_path / "candidate-models.json").exists()


def test_gui_rejects_wrong_model_kind_and_unlisted_repositories(tmp_path, current):
    for repo in (DEFAULT_ASR, "untrusted/arbitrary-code"):
        with pytest.raises(ValueError, match="Unsupported"):
            validate_selection(tmp_path, {"asr": DEFAULT_ASR, "translation": repo})


def test_prepare_without_options_preserves_previously_selected_models(tmp_path):
    active = {
        "asr": snapshot(tmp_path, "custom/whisper"),
        "translation": snapshot(tmp_path, "custom/qwen"),
    }
    (tmp_path / "models.json").write_text(json.dumps(active))
    offline = Mock(side_effect=AssertionError("Unexpected network"))
    assert prepare_models(tmp_path, downloader=offline, revision_for=offline) == active
    assert {item["repo"] for item in catalog_at(tmp_path)} >= {"custom/whisper", "custom/qwen"}


def test_mirror_preparation_pins_metadata_revision_and_never_forwards_login_token(
    tmp_path, current, monkeypatch
):
    from types import SimpleNamespace

    import huggingface_hub

    repo = "mlx-community/whisper-small-mlx-4bit"
    api = Mock()
    api.model_info.return_value = SimpleNamespace(
        sha="mirror-revision", siblings=[SimpleNamespace(rfilename="weights.safetensors", size=200)]
    )
    constructor = Mock(return_value=api)
    monkeypatch.setattr(huggingface_hub, "HfApi", constructor)
    observed = []

    def download(model, **options):
        assert options["endpoint"] == "https://hf-mirror.com"
        assert options["token"] is False
        assert options["revision"] == "mirror-revision"
        bar = options["tqdm_class"](total=200, unit="B", name="huggingface_hub.snapshot_download")
        bar.update(50)
        bar.close()
        observed.append(json.loads((tmp_path / "preparation.json").read_text()))
        return snapshot(tmp_path, model)["path"]

    prepare_models(tmp_path, asr=repo, downloader=download, download={"source": "mirror"})
    constructor.assert_called_once_with(endpoint="https://hf-mirror.com", token=False)
    assert observed[0]["bytes"] == 50
    assert observed[0]["total_bytes"] == 200
    assert json.loads((tmp_path / "download.json").read_text())["source"] == "mirror"
    assert json.loads((tmp_path / "preparation.json").read_text())["stage"] == "complete"


@pytest.mark.parametrize("suffix", [".safetensors", ".npz"])
def test_missing_weight_blob_is_shown_as_incomplete_and_redownloaded(
    tmp_path, current, monkeypatch, suffix
):
    from pathlib import Path

    from live_subs.desktop import DesktopController
    from live_subs.model_manager import complete

    folder = Path(current["asr"]["path"])
    dangling = folder / ("missing-shard" + suffix)
    dangling.symlink_to(tmp_path / "missing-blob")
    assert not complete(current["asr"]), "a valid shard cannot hide a missing sibling shard"
    monkeypatch.setattr("live_subs.desktop.probe", lambda _: ("stopped", False))
    state = DesktopController(tmp_path).snapshot()
    assert state["models"][0]["ready"] is False
    assert state["models"][0]["bytes"] == 0
    selected = next(item for item in state["catalog"] if item["repo"] == DEFAULT_ASR)
    assert selected["downloaded"] is False

    def repair(repo, **options):
        dangling.unlink()
        return snapshot(tmp_path, repo)["path"]

    download = Mock(side_effect=repair)
    result = prepare_models(tmp_path, downloader=download, revision_for=lambda _: "repaired")
    assert download.call_args.args == (DEFAULT_ASR,)
    assert download.call_count == 1
    assert complete(result["asr"])
    assert result["translation"] == current["translation"]


def test_weight_directories_are_incomplete_but_valid_cache_symlinks_are_reusable(tmp_path):
    from pathlib import Path

    from live_subs.model_manager import snapshot_status

    item = snapshot(tmp_path, DEFAULT_ASR)
    weight = Path(item["path"]) / "weights.safetensors"
    weight.unlink()
    weight.mkdir()
    assert snapshot_status(item) == (False, 0)
    weight.rmdir()
    blob = tmp_path / "blob"
    blob.write_bytes(b"cached model")
    weight.symlink_to(blob)
    assert snapshot_status(item) == (True, len(b"cached model"))
