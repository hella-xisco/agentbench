"""Verify and optionally extract the submission's split measurement archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "data/analysis"
    proof = json.loads((directory / "checksums.json").read_text())
    checked_files = 0
    for group in ("source_files", "asset_files", "configuration_files", "result_files", "material_files", "style_files"):
        for relative, expected in proof.get(group, {}).items():
            path = Path(relative)
            target = ROOT / path
            if path.is_absolute() or ".." in path.parts or not target.resolve().is_relative_to(ROOT.resolve()):
                raise RuntimeError(f"Unsafe submission-file path: {relative}")
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Submission-file checksum mismatch: {relative}")
            checked_files += 1
    parts = proof["archive_parts"]
    archive_bytes = bytearray()
    for name, expected in sorted(parts.items()):
        if Path(name).name != name:
            raise RuntimeError("Invalid archive-part name")
        content = (directory / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise RuntimeError(f"Archive-part checksum mismatch: {name}")
        archive_bytes.extend(content)
    if hashlib.sha256(archive_bytes).hexdigest() != proof["archive_sha256"]:
        raise RuntimeError("Combined archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        members = archive.getmembers()
        expected_inputs = proof["inputs"]
        if len(members) != len(expected_inputs) or {m.name for m in members} != set(expected_inputs):
            raise RuntimeError("Measurement archive members differ from the allowlist")
        for member in members:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or path.parts[0] != "experiments":
                raise RuntimeError(f"Unsafe archive member: {member.name}")
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != expected_inputs[member.name]:
                raise RuntimeError(f"Measurement checksum mismatch: {member.name}")
            if args.extract:
                target = ROOT / path
                if not target.resolve().is_relative_to(ROOT.resolve()):
                    raise RuntimeError(f"Extraction path escapes repository: {target}")
                if target.exists() and target.read_bytes() != content:
                    raise RuntimeError(f"Different existing measurement file: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    print(f"Verified {checked_files} submission files, {len(parts)} archive parts and {len(members)} exact measurement inputs" + ("; extracted" if args.extract else ""))


if __name__ == "__main__":
    main()
