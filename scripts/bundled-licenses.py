"""Collect the license texts that the pgspecial and setproctitle wheels leave out.

Usage: bundled-licenses.py

pgspecial is built with setuptools, whose default patterns for license files
(LICEN[CS]E*, COPYING*, NOTICE*, AUTHORS*) do not match its License.txt, so
its wheel has none. setproctitle's wheels have its own BSD-3-Clause license,
but its C extension is also built from src/spt_status.c, taken from
PostgreSQL, and src/spt_strlcpy.c, taken from OpenBSD, whose terms are only
in the comments at the top of those files.

This reads the versions of both packages pinned in requirements.lock,
downloads their source releases, checks them against their SHA-256 on PyPI
and writes to licenses/<name>-<version>/ pgspecial's License.txt, unless a
locked pgspecial wheel has a license file again, and the comments at the top
of setproctitle's two files. Run it whenever requirements.lock changes the
version of either package.
"""

import hashlib
import io
import json
import pathlib
import re
import shutil
import sys
import tarfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# What to take from each source release. "copy": files copied whole when no
# locked wheel has a license file. "notices": C files whose leading comments
# are written to the named file; each comment must contain the given lines,
# so that a changed header is looked at again.
PACKAGES = {
    "pgspecial": {"copy": ["License.txt"]},
    "setproctitle": {
        "notices": {
            "src/spt_status.c": (
                "LICENSE.spt_status",
                ["This file was taken from PostgreSQL.", "The Regents of the University of California"],
            ),
            "src/spt_strlcpy.c": (
                "LICENSE.spt_strlcpy",
                ["This file was taken from OpenBSD", "Copyright (c) 1998 Todd C. Miller"],
            ),
        },
    },
}

# The file names the image build takes as license files.
LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def fetch_checked(item):
    data = fetch(item["url"])
    if hashlib.sha256(data).hexdigest() != item["digests"]["sha256"]:
        sys.exit(f"{item['url']} does not match its SHA-256 on PyPI")
    return data


def locked(lock, name):
    pattern = rf"^{re.escape(name)}==([^\s;]+)[^\\\n]*?((?:\s*\\\n\s*--hash=sha256:[0-9a-f]{{64}})+)"
    match = re.search(pattern, lock, re.M)
    if not match:
        sys.exit(f"requirements.lock does not pin {name}")
    return match.group(1), set(re.findall(r"sha256:([0-9a-f]{64})", match.group(2)))


def has_license_file(wheel):
    for path in wheel.namelist():
        parts = path.split("/")
        if len(parts) < 2 or not parts[0].endswith(".dist-info"):
            continue
        if parts[1] == "licenses" or parts[-1].upper().startswith(LICENSE_NAMES):
            return True
    return False


def wheel_has_license(name, version, hashes, release):
    wheels = [f for f in release["urls"] if f["packagetype"] == "bdist_wheel" and f["digests"]["sha256"] in hashes]
    if not wheels:
        sys.exit(f"no wheel of {name} {version} on PyPI has a hash listed in requirements.lock")
    for item in wheels:
        with zipfile.ZipFile(io.BytesIO(fetch_checked(item))) as wheel:
            if has_license_file(wheel):
                print(f"{item['filename']} has a license file, so {name} {version} needs no copy")
                return True
    return False


def source_files(name, version, release, paths):
    sdists = [f for f in release["urls"] if f["packagetype"] == "sdist"]
    if len(sdists) != 1 or not sdists[0]["filename"].endswith(".tar.gz"):
        sys.exit(f"{name} {version} has no single .tar.gz source release on PyPI")
    sdist = sdists[0]
    top = sdist["filename"].removesuffix(".tar.gz")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(fetch_checked(sdist))) as tar:
        for path in paths:
            try:
                data = tar.extractfile(f"{top}/{path}").read()
            except KeyError:
                sys.exit(f"{sdist['url']} has no {top}/{path}")
            if not data.strip():
                sys.exit(f"{top}/{path} in {sdist['url']} is empty")
            files[path] = data
    return files


def leading_comments(text):
    """The comments at the top of a C file, up to its first line of code."""
    lines = []
    inside = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if not inside and stripped and not stripped.startswith("/*"):
            break
        lines.append(line)
        if inside or stripped.startswith("/*"):
            inside = not stripped.endswith("*/")
    return "".join(lines).strip() + "\n"


def collect(name, version, hashes, wanted):
    release = json.loads(fetch(f"https://pypi.org/pypi/{name}/{version}/json"))
    copy = wanted.get("copy", [])
    if copy and wheel_has_license(name, version, hashes, release):
        copy = []
    notices = wanted.get("notices", {})
    if not copy and not notices:
        return {}

    files = source_files(name, version, release, [*copy, *notices])
    texts = {pathlib.PurePosixPath(path).name: files[path] for path in copy}
    for path, (target, lines) in notices.items():
        text = leading_comments(files[path].decode())
        missing = [line for line in lines if line not in text]
        if missing:
            sys.exit(f"the comments at the top of {path} in {name} {version} no longer contain: {'; '.join(missing)}")
        texts[target] = text.encode()
    return texts


def main():
    lock = (ROOT / "requirements.lock").read_text()
    texts = {}
    for name, wanted in PACKAGES.items():
        version, hashes = locked(lock, name)
        texts[(name, version)] = collect(name, version, hashes, wanted)

    base = ROOT / "licenses"
    for name, version in texts:
        for old in base.glob(f"{name}-*"):
            if old.is_dir():
                shutil.rmtree(old)
    for (name, version), files in texts.items():
        if not files:
            continue
        out = base / f"{name}-{version}"
        out.mkdir(parents=True)
        for filename, text in files.items():
            (out / filename).write_bytes(text)
            print(f"wrote {(out / filename).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
