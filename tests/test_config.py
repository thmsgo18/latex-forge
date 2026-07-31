from __future__ import annotations

import latex_forge.config as config_module


def test_no_config_file_returns_none_template(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "_CONFIG_PATH", tmp_path / ".latex-forge.toml")
    assert config_module.get_default_template() is None


def test_default_template_read_from_config(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_template = "project-report-fr"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_template() == "project-report-fr"


def test_no_config_file_returns_none_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "_CONFIG_PATH", tmp_path / ".latex-forge.toml")
    assert config_module.get_default_output_dir() is None


def test_default_output_dir_valid(tmp_path, monkeypatch):
    output_dir = tmp_path / "projects"
    output_dir.mkdir()
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text(
        f'default_output_dir = "{output_dir.as_posix()}"\n', encoding="utf-8"
    )
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_output_dir() == output_dir


def test_default_output_dir_nonexistent_dir(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text(
        'default_output_dir = "/nonexistent/path/that/does/not/exist"\n', encoding="utf-8"
    )
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_output_dir() is None


def test_malformed_config_returns_none(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text("not valid toml ][[\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_template() is None
    assert config_module.get_default_output_dir() is None


def test_empty_template_string_returns_none(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_template = ""\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_template() is None


def test_no_config_file_returns_none_sharing(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "_CONFIG_PATH", tmp_path / ".latex-forge.toml")
    assert config_module.get_default_sharing() is None


def test_default_sharing_read_from_config(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_sharing = "pdf-only"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_sharing() == "pdf-only"


def test_default_sharing_invalid_value_returns_none(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_sharing = "everything"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_sharing() is None


def test_default_sharing_old_none_value_now_ignored(tmp_path, monkeypatch):
    # "none" used to be a valid --sharing value; it's now expressed via --repo none instead.
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_sharing = "none"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_sharing() is None


def test_no_config_file_returns_none_repo_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "_CONFIG_PATH", tmp_path / ".latex-forge.toml")
    assert config_module.get_default_repo_mode() is None


def test_default_repo_mode_read_from_config(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_repo_mode = "existing"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_repo_mode() == "existing"


def test_default_repo_mode_invalid_value_returns_none(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_repo_mode = "everything"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_repo_mode() is None


def test_no_config_file_returns_none_visibility(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "_CONFIG_PATH", tmp_path / ".latex-forge.toml")
    assert config_module.get_default_visibility() is None


def test_default_visibility_read_from_config(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_visibility = "public"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_visibility() == "public"


def test_default_visibility_invalid_value_returns_none(tmp_path, monkeypatch):
    config_file = tmp_path / ".latex-forge.toml"
    config_file.write_text('default_visibility = "everything"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_PATH", config_file)
    assert config_module.get_default_visibility() is None
