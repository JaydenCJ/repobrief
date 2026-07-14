"""Health signals: docs, license identification, CI, tests, lockfiles."""

from repobrief.fswalk import walk
from repobrief.health import assess, identify_license

from conftest import write

MIT_TEXT = (
    "MIT License\n\nCopyright (c) 2026 Someone\n\n"
    "Permission is hereby granted, free of charge, to any person obtaining a copy...\n"
)


def health_of(root):
    return assess(str(root), {f.path for f in walk(str(root))})


def test_identify_license_families():
    assert identify_license(MIT_TEXT) == "MIT"
    assert identify_license("Apache License\nVersion 2.0, January 2004\n") == "Apache-2.0"
    assert identify_license("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n") == "GPL-3.0"
    assert (
        identify_license("Redistribution and use in source and binary forms, with or without...")
        == "BSD"
    )
    assert identify_license("Some homegrown terms.") == "present (unrecognized)"


def test_assess_finds_docs_and_license(sample_repo):
    h = health_of(sample_repo)
    assert h.readme == "README.md"
    assert h.license == "MIT"
    assert not h.contributing and not h.changelog


def test_lowercase_readme_is_found(tmp_path):
    write(tmp_path, "readme.md", "# hi\n")
    assert health_of(tmp_path).readme == "readme.md"


def test_ci_detection_counts_workflows(tmp_path):
    write(tmp_path, ".github/workflows/ci.yml", "name: ci\n")
    write(tmp_path, ".github/workflows/release.yaml", "name: release\n")
    write(tmp_path, ".gitlab-ci.yml", "stages: []\n")
    h = health_of(tmp_path)
    assert "GitHub Actions (2 workflows)" in h.ci
    assert "GitLab CI" in h.ci


def test_test_detection_by_directory_or_filename(tmp_path):
    assert health_of(tmp_path).has_tests is False
    write(tmp_path, "pkg/handler_test.go", "package pkg\n")
    assert health_of(tmp_path).has_tests is True
    (tmp_path / "pkg" / "handler_test.go").unlink()
    # A conventional test directory counts even with unconventional filenames.
    write(tmp_path, "spec/fancy.rb", "describe...\n")
    assert health_of(tmp_path).has_tests is True


def test_lockfiles_reported_in_stable_order(tmp_path):
    write(tmp_path, "go.sum", "h1:...\n")
    write(tmp_path, "package-lock.json", "{}\n")
    h = health_of(tmp_path)
    assert h.lockfiles == ["package-lock.json", "go.sum"]
