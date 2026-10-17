#!/usr/bin/env python3
"""Read-only disk inventory for a project and the toolchain caches behind it.

Usage: python3 scan.py <project-dir> [--top N] [--min-mb M]

Prints, without changing anything:
  1. the largest top-level entries in the project;
  2. git-ignored and untracked entries (deleting these cannot be undone from git);
  3. stray files at the project root that look like shell-redirection accidents;
  4. global caches for the ecosystems the project uses, plus free disk space.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()

# (marker files in the project, label, global cache paths)
ECOSYSTEMS = [
    (["*.xcodeproj", "*.xcworkspace", "Package.swift"], "Xcode / Swift", [
        "Library/Developer/Xcode/DerivedData",
        "Library/Developer/Xcode/Archives",
        "Library/Developer/Xcode/iOS DeviceSupport",
        "Library/Developer/Xcode/watchOS DeviceSupport",
        "Library/Developer/Xcode/macOS DeviceSupport",
        "Library/Developer/CoreSimulator/Devices",
        "Library/Caches/com.apple.dt.Xcode",
    ]),
    (["package.json"], "Node", [
        ".npm/_cacache", "Library/pnpm/store", ".local/share/pnpm/store",
        "Library/Caches/Yarn", ".cache/yarn",
    ]),
    (["pyproject.toml", "requirements.txt", "setup.py"], "Python", [
        "Library/Caches/pip", ".cache/pip", ".cache/uv", ".cache/huggingface",
    ]),
    (["Cargo.toml"], "Rust", [".cargo/registry", ".cargo/git"]),
    (["go.mod"], "Go", ["Library/Caches/go-build", ".cache/go-build", "go/pkg/mod"]),
    (["build.gradle", "build.gradle.kts", "settings.gradle"], "Gradle / Android", [
        ".gradle/caches", ".android/avd",
    ]),
]

# Project-local directories that are almost always regenerable.
REGENERABLE = {
    "node_modules", "dist", ".next", ".nuxt", ".turbo", ".parcel-cache", ".vite",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv",
    "target", ".gradle", "DerivedData", ".build",
}

STRAY_NAMES = {":-", "-", "=", "nohup.out", "''", '""'}


def size_of(path: Path) -> int:
    """Disk usage in bytes, like du -sk."""
    try:
        out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True).stdout
        return int(out.split()[0]) * 1024
    except (IndexError, ValueError):
        return 0


def human(n: int) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return str(n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-mb", type=float, default=1.0)
    args = ap.parse_args()
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"not a directory: {project}", file=sys.stderr)
        return 1
    min_bytes = int(args.min_mb * 1024 * 1024)

    print(f"# {project}  total {human(size_of(project))}\n")

    print("## Largest entries")
    entries = [(size_of(p), p) for p in project.iterdir()]
    for s, p in sorted(entries, reverse=True)[: args.top]:
        tag = "  [regenerable]" if p.name in REGENERABLE else ""
        print(f"  {human(s):>8}  {p.name}{tag}")

    is_git = (project / ".git").exists()
    if is_git:
        print("\n## Not in git (cannot be restored from git once deleted)")
        # --ignored lists ignored ("!!") and untracked ("??") entries together.
        r = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "--ignored"],
                           capture_output=True, text=True)
        rows = []
        for line in r.stdout.splitlines():
            code, rel = line[:2], line[3:].strip('"')
            if code not in ("!!", "??"):
                continue
            s = size_of(project / rel)
            if s >= min_bytes:
                rows.append((s, "ignored" if code == "!!" else "untracked", rel))
        for s, mark, rel in sorted(rows, reverse=True):
            tag = "  [regenerable]" if Path(rel.rstrip("/")).name in REGENERABLE else ""
            print(f"  {human(s):>8}  {mark:9}  {rel}{tag}")
        if not rows:
            print(f"  nothing over {args.min_mb} MB")
    else:
        print("\n(not a git repository: every deletion is permanent)")

    strays = [p.name for p in project.iterdir()
              if p.is_file() and (p.name in STRAY_NAMES or p.name.startswith(("-", ":")))]
    if strays:
        print("\n## Suspicious root files (check contents before deleting)")
        for name in strays:
            print(f"  {name}")

    print("\n## Global caches")
    found_any = False
    for markers, label, paths in ECOSYSTEMS:
        if not any(any(project.glob(m)) or any(project.glob(f"*/{m}")) for m in markers):
            continue
        found_any = True
        print(f"  {label}")
        for rel in paths:
            p = HOME / rel
            if p.exists():
                print(f"    {human(size_of(p)):>8}  ~/{rel}")
    if shutil.which("docker"):
        found_any = True
        print("  Docker: run `docker system df` to see image, container and volume usage")
    if not found_any:
        print("  no known ecosystem detected")

    usage = shutil.disk_usage(project)
    print(f"\n## Disk  free {human(usage.free)} of {human(usage.total)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
