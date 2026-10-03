from live_subs.models import whisper_directory


def test_new_whisper_checkpoint_loads_from_compatible_names_without_mutating_snapshot(tmp_path):
    source = tmp_path / "upstream"
    source.mkdir()
    (source / "config.json").write_text('{"model_type":"whisper"}')
    (source / "model.safetensors").write_bytes(b"checkpoint fixture")
    target = whisper_directory(source, tmp_path / "local")
    assert (target / "weights.safetensors").read_bytes() == b"checkpoint fixture"
    assert (target / "weights.safetensors").is_symlink()
    assert not (source / "weights.safetensors").exists()
    assert whisper_directory(source, tmp_path / "local") == target
