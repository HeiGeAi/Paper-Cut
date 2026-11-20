import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validate_project as validator


class ProjectValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for file in ("video-script.md", "storyboard.md", "index.html"):
            (self.root / file).write_text("fixture")
        (self.root / "asset.png").write_bytes(b"fixture-asset")
        self.digest = hashlib.sha256(b"fixture-asset").hexdigest()
        self.project = {"schemaVersion": 1, "stage": "delivery", "video": {"width": 1920, "height": 1080, "fps": 30, "durationSeconds": 3},
                        "scenes": [{"id": "a", "start": 0, "duration": 2}, {"id": "b", "start": 1, "duration": 2}]}
        self.asset = {"id": "a", "role": "subject", "status": "approved", "sourcePath": "asset.png", "processedPath": "asset.png", "sha256": self.digest}

    def validate(self, asset=None):
        (self.root / "paper-cut-project.json").write_text(json.dumps(self.project))
        (self.root / "assets-manifest.json").write_text(json.dumps({"schemaVersion": 1, "assets": [self.asset if asset is None else asset]}))
        with patch("sys.argv", ["validate_project.py", str(self.root)]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return validator.main()

    def test_valid_overlapping_scenes_and_planned_asset(self):
        self.assertEqual(self.validate(), 0)
        self.assertEqual(self.validate({"id": "p", "role": "subject", "status": "planned"}), 0)

    def test_missing_empty_or_directory_paths_rejected(self):
        for status in ("generated", "processed", "approved", "approved-for-preview", "approved-for-revision"):
            keys = ("sourcePath",) if status == "generated" else ("sourcePath", "processedPath")
            for key in keys:
                for invalid in (None, "", ".", "missing.png", " "):
                    with self.subTest(status=status, key=key, invalid=invalid):
                        asset = {**self.asset, "status": status, key: invalid}
                        self.assertEqual(self.validate(asset), 1)

    def test_generated_source_only_and_processed_hash(self):
        asset = {**self.asset, "status": "generated"}
        del asset["processedPath"]
        self.assertEqual(self.validate(asset), 0)
        (self.root / "processed.png").write_bytes(b"processed")
        asset = {**self.asset, "status": "processed", "processedPath": "processed.png", "sha256": hashlib.sha256(b"processed").hexdigest()}
        self.assertEqual(self.validate(asset), 0)
        self.assertEqual(self.validate({**asset, "sha256": self.digest}), 1)

    def test_hash_missing_malformed_or_mismatch_rejected(self):
        for digest in (None, "", "a" * 63, "z" * 64, "0" * 64):
            self.assertEqual(self.validate({**self.asset, "sha256": digest}), 1)

    def test_symlink_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "asset.png"
            target.write_bytes(b"fixture-asset")
            (self.root / "external.png").symlink_to(target)
            self.assertEqual(self.validate({**self.asset, "processedPath": "external.png"}), 1)

    def test_video_values_reject_booleans_nonfinite_and_nonpositive(self):
        for key in ("width", "height", "fps", "durationSeconds"):
            original = self.project["video"][key]
            for value in (True, False, float("nan"), float("inf"), -float("inf"), 0, -1):
                with self.subTest(key=key, value=value):
                    self.project["video"][key] = value
                    self.assertEqual(self.validate(), 1)
            self.project["video"][key] = original
        for key in ("width", "height"):
            original = self.project["video"][key]
            for value in (1.5, 1920.0):
                self.project["video"][key] = value
                self.assertEqual(self.validate(), 1)
            self.project["video"][key] = original

    def test_scene_values_reject_booleans_nonfinite_and_invalid_bounds(self):
        for key in ("start", "duration"):
            original = self.project["scenes"][0][key]
            values = [True, False, float("nan"), float("inf"), -float("inf"), -1]
            if key == "duration":
                values.append(0)
            for value in values:
                self.project["scenes"][0][key] = value
                self.assertEqual(self.validate(), 1)
            self.project["scenes"][0][key] = original

    def test_bundled_sample(self):
        root = Path(validator.__file__).resolve().parent.parent
        for manifest in (root / "examples").glob("*/assets-manifest.json"):
            with patch("sys.argv", ["validate_project.py", str(manifest.parent)]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validator.main(), 0)
