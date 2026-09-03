from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def _manifest(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("artifacts"), list):
        raise ValueError("official snapshot manifest must contain an artifacts list")
    return loaded


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(
    *, manifest_path: Path, root: Path | None, require_all: bool, run_tests: bool
) -> dict[str, Any]:
    manifest = _manifest(manifest_path)
    resolved_environment = os.environ.copy()
    items: list[dict[str, Any]] = []
    tests: list[str] = []
    for artifact in manifest["artifacts"]:
        environment_name = str(artifact["env"])
        explicit = os.getenv(environment_name)
        path = (
            Path(explicit)
            if explicit
            else (root / str(artifact["relative_path"]) if root else None)
        )
        kind = str(artifact.get("kind", "file"))
        present = bool(path and (path.is_dir() if kind == "directory" else path.is_file()))
        if present and path is not None:
            resolved_environment[environment_name] = str(path)
            tests.append(str(artifact["test"]))
        items.append(
            {
                "env": environment_name,
                "kind": kind,
                "present": present,
                "sha256": _sha256(path) if present and path is not None else None,
            }
        )
    missing = [item["env"] for item in items if not item["present"]]
    if require_all and missing:
        return {
            "ready": False,
            "version": manifest["version"],
            "missing": missing,
            "items": items,
            "tests_run": False,
        }
    test_exit_code: int | None = None
    if run_tests and tests:
        unique_tests = list(dict.fromkeys(tests))
        test_exit_code = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *unique_tests],
            check=False,
            env=resolved_environment,
        ).returncode
    return {
        "ready": not missing and test_exit_code in {None, 0},
        "version": manifest["version"],
        "missing": missing,
        "items": items,
        "tests_run": bool(run_tests and tests),
        "test_exit_code": test_exit_code,
    }


def run() -> None:
    parser = argparse.ArgumentParser(description="Verify licensed official-source snapshots")
    parser.add_argument("--manifest", type=Path, default=Path("config/official-snapshots.yaml"))
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root
    if root is None and os.getenv("ATLAS_SNAPSHOT_ROOT"):
        root = Path(os.environ["ATLAS_SNAPSHOT_ROOT"])
    result = verify(
        manifest_path=arguments.manifest,
        root=root,
        require_all=arguments.require_all,
        run_tests=arguments.run_tests,
    )
    print(json.dumps(result, sort_keys=True))
    if arguments.require_all and not result["ready"]:
        sys.exit(1)
    if result.get("test_exit_code") not in {None, 0}:
        sys.exit(int(result["test_exit_code"]))


if __name__ == "__main__":
    run()
