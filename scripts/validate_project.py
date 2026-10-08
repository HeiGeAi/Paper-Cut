#!/usr/bin/env python3
"""Validate Paper Cut state and asset contracts without invoking providers."""

from __future__ import annotations

import argparse
import json
import math
import hashlib
import re
import sys
from pathlib import Path


STAGES = {"intake", "storyboard-review", "asset-review", "asset-production", "assembly", "qa", "preview-review", "preview", "delivery"}
ROLES = {"background", "subject", "prop", "texture", "type", "typography", "audio", "reference"}
STATUSES = {"planned", "generated", "processed", "approved", "approved-for-preview", "approved-for-revision", "rejected", "superseded"}


def finite_number(value: object) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def reject_constant(value: str):
    raise ValueError(f"invalid JSON numeric constant: {value}")


def load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except FileNotFoundError:
        raise ValueError(f"missing file: {path.name}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.name}: {exc}") from None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()
    root = args.project_dir.resolve()
    errors: list[str] = []
    try:
        project = load(root / "paper-cut-project.json")
        manifest = load(root / "assets-manifest.json")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not isinstance(project, dict) or not isinstance(manifest, dict):
        print("root JSON values must be objects", file=sys.stderr)
        return 1

    if project.get("schemaVersion") != 1:
        errors.append("paper-cut-project.json schemaVersion must be 1")
    if project.get("stage") not in STAGES:
        errors.append(f"invalid stage: {project.get('stage')!r}")
    video = project.get("video")
    if not isinstance(video, dict):
        errors.append("video must be an object")
    else:
        for key in ("width", "height", "fps", "durationSeconds"):
            value = video.get(key)
            if not finite_number(value) or value <= 0:
                errors.append(f"video.{key} must be finite and positive")
            elif key in {"width", "height"} and type(value) is not int:
                errors.append(f"video.{key} must be an integer")

    scenes = project.get("scenes", [])
    if not isinstance(scenes, list):
        errors.append("scenes must be an array")
        scenes = []
    scene_ids: set[str] = set()
    last_start = -1.0
    max_end = 0.0
    for index, scene in enumerate(scenes):
        prefix = f"scenes[{index}]"
        if not isinstance(scene, dict):
            errors.append(f"{prefix} must be an object")
            continue
        scene_id, start, duration = scene.get("id"), scene.get("start"), scene.get("duration")
        if not isinstance(scene_id, str) or not scene_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif scene_id in scene_ids:
            errors.append(f"duplicate scene id: {scene_id}")
        else:
            scene_ids.add(scene_id)
        if not finite_number(start) or start < 0:
            errors.append(f"{prefix}.start must be non-negative")
            continue
        if start < last_start:
            errors.append(f"{prefix}.start is not monotonic")
        last_start = float(start)
        if not finite_number(duration) or duration <= 0:
            errors.append(f"{prefix}.duration must be positive")
            continue
        max_end = max(max_end, float(start + duration))
    if isinstance(video, dict) and finite_number(video.get("durationSeconds")) and max_end > video["durationSeconds"] + 0.05:
        errors.append("scene timing exceeds video.durationSeconds")

    assets = manifest.get("assets", [])
    if manifest.get("schemaVersion") != 1 or not isinstance(assets, list):
        errors.append("assets-manifest.json must have schemaVersion 1 and an assets array")
        assets = []
    asset_ids: set[str] = set()
    for index, asset in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif asset_id in asset_ids:
            errors.append(f"duplicate asset id: {asset_id}")
        else:
            asset_ids.add(asset_id)
        if asset.get("role") not in ROLES:
            errors.append(f"{prefix}.role is invalid")
        if asset.get("status") not in STATUSES:
            errors.append(f"{prefix}.status is invalid")
        for scene_id in asset.get("sceneIds", []):
            if scene_id not in scene_ids:
                errors.append(f"{prefix} references unknown scene {scene_id!r}")
        status = asset.get("status")
        realized = status in {"generated", "processed", "approved", "approved-for-preview", "approved-for-revision"}
        required_paths = {"sourcePath"} if realized else set()
        if realized and status != "generated":
            required_paths.add("processedPath")
        files = {}
        for key in ("sourcePath", "processedPath"):
            relative = asset.get(key)
            if relative is None or relative == "":
                if key in required_paths:
                    errors.append(f"{prefix}.{key} is required for {status} assets")
                continue
            if not isinstance(relative, str) or not relative.strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")
                continue
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                errors.append(f"{prefix}.{key} must be a relative path inside the project: {relative}")
                continue
            if realized:
                candidates = [(root / relative).resolve(), (root / "hyperframes" / relative).resolve()]
                file = next((p for p in candidates if p.is_relative_to(root) and p.is_file()), None)
                if file is None:
                    errors.append(f"{prefix}.{key} must identify a regular file inside the project: {relative}")
                else:
                    files[key] = file
        # Hash identifies the deliverable, or the source before processing.
        if realized:
            digest = asset.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                errors.append(f"{prefix}.sha256 must be a SHA-256 hex digest")
            else:
                file = files.get("processedPath") or files.get("sourcePath")
                if file is not None:
                    checksum = hashlib.sha256()
                    try:
                        with file.open("rb") as handle:
                            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                                checksum.update(chunk)
                    except OSError as exc:
                        errors.append(f"{prefix}: cannot read asset file: {exc}")
                        continue
                    if checksum.hexdigest() != digest.lower():
                        errors.append(f"{prefix}.sha256 does not match the asset file")

    for required in ("video-script.md", "storyboard.md"):
        if not (root / required).is_file():
            errors.append(f"missing file: {required}")
    if not (root / "index.html").is_file() and not (root / "hyperframes" / "index.html").is_file():
        errors.append("missing HyperFrames index.html")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"valid": True, "scenes": len(scenes), "assets": len(assets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
