"""Manifest discovery and project-identity resolution."""

from repobrief.manifest import load

from conftest import write


def test_package_json_provides_identity(sample_repo):
    m = load(str(sample_repo))
    assert m.name == "acme-relay"
    assert m.description == "Tiny webhook relay for example.test"
    assert m.version == "1.2.0"
    assert m.source == "package.json"


def test_pyproject_wins_over_package_json(tmp_path):
    # Mixed repos (a Python tool with a docs site) should identify by pyproject.
    write(tmp_path, "pyproject.toml", '[project]\nname = "pytool"\ndescription = "d"\n')
    write(tmp_path, "package.json", '{"name": "docs-site"}')
    m = load(str(tmp_path))
    assert m.name == "pytool" and m.source == "pyproject.toml"


def test_cargo_identity(tmp_path):
    write(tmp_path, "Cargo.toml", '[package]\nname = "rusty"\ndescription = "fast"\nversion = "0.9.1"\n')
    m = load(str(tmp_path))
    assert (m.name, m.description, m.version) == ("rusty", "fast", "0.9.1")


def test_gomod_module_last_segment_becomes_name(tmp_path):
    write(tmp_path, "go.mod", "module example.test/team/satellite\n\ngo 1.22\n")
    m = load(str(tmp_path))
    assert m.name == "satellite" and m.source == "go.mod"
    assert m.gomod_module == "example.test/team/satellite"


def test_no_manifest_falls_back_to_directory_name(tmp_path):
    root = tmp_path / "bare-dir"
    root.mkdir()
    m = load(str(root))
    assert m.name == "bare-dir" and m.source == "directory name"
    assert m.description is None


def test_broken_or_partial_manifests_degrade_instead_of_crashing(tmp_path):
    write(tmp_path, "package.json", "{not json at all")
    # A pyproject that only configures tools (common pre-PEP-621) has no identity.
    write(tmp_path, "pyproject.toml", "[tool.black]\nline-length = 100\n")
    m = load(str(tmp_path))
    assert m.package_json is None
    assert m.pyproject is not None  # still parsed and available to analyzers
    assert m.source == "directory name"
