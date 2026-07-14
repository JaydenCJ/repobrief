"""Entry-point detection across ecosystems."""

from repobrief.entrypoints import find_entrypoints
from repobrief.fswalk import walk
from repobrief.manifest import load

from conftest import write


def find(root):
    files = {f.path for f in walk(str(root))}
    return find_entrypoints(str(root), files, load(str(root)))


def by_kind(eps, kind):
    return [e for e in eps if e.kind == kind]


def test_pyproject_console_scripts_and_empty_repo(tmp_path):
    assert find(tmp_path) == []  # nothing to detect in an empty tree
    write(tmp_path, "pyproject.toml", '[project]\nname = "t"\n\n[project.scripts]\nmytool = "t.cli:main"\n')
    (ep,) = by_kind(find(tmp_path), "console-script")
    assert ep.name == "mytool" and ep.run == "mytool" and ep.path == "pyproject.toml"


def test_python_dunder_main_under_src_layout(tmp_path):
    write(tmp_path, "src/mypkg/__main__.py", "print('hi')\n")
    (ep,) = by_kind(find(tmp_path), "python -m")
    assert ep.run == "python -m mypkg"  # src/ prefix stripped from the module path


def test_python_dunder_main_flat_layout_and_root_script(tmp_path):
    write(tmp_path, "mypkg/__main__.py", "print('hi')\n")
    write(tmp_path, "manage.py", "print('django-ish')\n")
    eps = find(tmp_path)
    assert any(e.run == "python -m mypkg" for e in eps)
    assert any(e.run == "python manage.py" for e in eps)


def test_node_bin_as_string_and_dict(tmp_path):
    write(tmp_path, "package.json", '{"name": "one", "bin": "cli.js"}')
    (ep,) = by_kind(find(tmp_path), "node bin")
    assert ep.name == "one" and ep.run == "node cli.js"

    write(tmp_path, "package.json", '{"name": "two", "bin": {"beta": "b.js", "alpha": "a.js"}}')
    eps = by_kind(find(tmp_path), "node bin")
    assert [(e.name, e.path) for e in eps] == [("alpha", "a.js"), ("beta", "b.js")]


def test_node_main_field_and_fallback_script(tmp_path):
    write(tmp_path, "package.json", '{"name": "svc", "main": "./lib/app.js"}')
    (ep,) = by_kind(find(tmp_path), "node main")
    assert ep.path == "lib/app.js"

    write(tmp_path, "package.json", '{"name": "svc2"}')
    write(tmp_path, "server.js", "// serves 127.0.0.1\n")
    (ep,) = by_kind(find(tmp_path), "node script")
    assert ep.run == "node server.js"


def test_cargo_declared_bins_and_src_main(tmp_path):
    write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "rusty"\n\n[[bin]]\nname = "alpha"\npath = "src/bin/alpha.rs"\n',
    )
    write(tmp_path, "src/main.rs", "fn main() {}\n")
    write(tmp_path, "src/bin/alpha.rs", "fn main() {}\n")
    write(tmp_path, "src/bin/beta.rs", "fn main() {}\n")
    eps = by_kind(find(tmp_path), "cargo bin")
    runs = {e.run for e in eps}
    assert runs == {"cargo run --bin alpha", "cargo run", "cargo run --bin beta"}
    # alpha declared in Cargo.toml must not be double-reported from src/bin/.
    assert len([e for e in eps if e.name == "alpha"]) == 1


def test_go_cmd_layout_requires_package_main(tmp_path):
    write(tmp_path, "go.mod", "module example.test/satellite\n")
    write(tmp_path, "cmd/serve/main.go", "package main\n\nfunc main() {}\n")
    write(tmp_path, "cmd/lib/main.go", "package lib\n")  # not runnable
    eps = by_kind(find(tmp_path), "go main")
    assert [(e.name, e.run) for e in eps] == [("serve", "go run ./cmd/serve")]


def test_go_root_main(tmp_path):
    write(tmp_path, "go.mod", "module example.test/tool\n")
    write(tmp_path, "main.go", "package main\n\nfunc main() {}\n")
    (ep,) = by_kind(find(tmp_path), "go main")
    assert ep.run == "go run ." and ep.name == "tool"


def test_dockerfile_and_procfile(tmp_path):
    write(
        tmp_path,
        "Dockerfile",
        "FROM scratch\nCMD [\"early\"]\nENTRYPOINT [\"/bin/app\", \"--serve\"]\n",
    )
    write(tmp_path, "Procfile", "web: gunicorn app:api\nworker: python worker.py\n# comment\n")
    eps = find(tmp_path)
    (docker,) = by_kind(eps, "docker")
    assert docker.name == 'ENTRYPOINT ["/bin/app", "--serve"]'  # last exec form wins
    assert [(e.name, e.run) for e in by_kind(eps, "procfile")] == [
        ("web", "gunicorn app:api"),
        ("worker", "python worker.py"),
    ]
