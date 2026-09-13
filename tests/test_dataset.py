"""Tests for aligning recorded (frame, action) pairs into a training dataset,
and for saving/loading a trained NearestNeighborPolicy round-trip.

These are pure-Python: no Quartz/AppKit involved, just manifest.json parsing,
image files on disk, and byte-level feature comparisons.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot_player as bp


def _write_frame(frames_dir: Path, index: int, color) -> Path:
    image = Image.new("RGB", (200, 200), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 180, 180), fill=color)
    draw.line((20, 20, 180, 180), fill=(0, 0, 0), width=2)
    draw.line((20, 180, 180, 20), fill=(0, 0, 0), width=2)
    path = frames_dir / f"frame-{index:06d}.png"
    image.save(path, "PNG")
    return path


def _write_session(root: Path, game: str, frames: list[dict], actions: list[dict]) -> Path:
    session_dir = root / "20260101-000000-deadbeef"
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)
    frame_entries = []
    for frame in frames:
        path = _write_frame(frames_dir, frame["index"], frame.get("color", (10, 120, 200)))
        frame_entries.append(
            {
                "index": frame["index"],
                "path": str(path.relative_to(session_dir)),
                "captured_at": "2026-01-01T00:00:00+0000",
                "monotonic": frame["monotonic"],
                "window": {"x": 0, "y": 0, "width": 200, "height": 200},
            }
        )
    manifest = {
        "format": bp.RECORDING_FORMAT,
        "version": bp.RECORDING_VERSION,
        "game": {"name": game, "key": bp.game_key(game)},
        "started_at": "2026-01-01T00:00:00+0000",
        "capture_interval_seconds": bp.RECORDING_INTERVAL_SECONDS,
        "input_sent": False,
        "input_observed": True,
        "input_observed_reason": None,
        "frames": frame_entries,
        "actions": actions,
        "ended_at": "2026-01-01T00:01:00+0000",
        "frame_count": len(frame_entries),
        "action_count": len(actions),
        "stopped_by_frame_limit": False,
    }
    (session_dir / "manifest.json").write_text(json.dumps(manifest))
    return session_dir


class BuildFrameActionDatasetTests(unittest.TestCase):
    def test_action_aligns_to_nearest_preceding_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = _write_session(
                root,
                "Test Game",
                frames=[{"index": 0, "monotonic": 100.0}, {"index": 1, "monotonic": 100.3}, {"index": 2, "monotonic": 100.6}],
                actions=[{"id": "a1", "kind": "tap", "points": [[0.5, 0.5]], "started_at": 100.35, "ended_at": 100.4, "hold_seconds": 0.0}],
            )
            examples = bp.build_frame_action_dataset([session], "Test Game")
            self.assertEqual(len(examples), 1)
            self.assertEqual(examples[0].source_frame_index, 1)
            self.assertEqual(examples[0].action.kind, bp.ActionKind.TAP)
            self.assertEqual(examples[0].action.points, ((0.5, 0.5),))

    def test_action_before_any_frame_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = _write_session(
                root,
                "Test Game",
                frames=[{"index": 0, "monotonic": 100.0}],
                actions=[{"id": "a1", "kind": "tap", "points": [[0.5, 0.5]], "started_at": 99.0, "ended_at": 99.1, "hold_seconds": 0.0}],
            )
            examples = bp.build_frame_action_dataset([session], "Test Game")
            self.assertEqual(examples, [])

    def test_action_with_too_large_a_gap_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = _write_session(
                root,
                "Test Game",
                frames=[{"index": 0, "monotonic": 100.0}],
                actions=[{"id": "a1", "kind": "tap", "points": [[0.5, 0.5]], "started_at": 100.0 + bp.MAX_FRAME_ACTION_GAP_SECONDS + 1, "ended_at": 105.0, "hold_seconds": 0.0}],
            )
            examples = bp.build_frame_action_dataset([session], "Test Game")
            self.assertEqual(examples, [])

    def test_multiple_actions_each_align_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = _write_session(
                root,
                "Test Game",
                frames=[{"index": 0, "monotonic": 100.0}, {"index": 1, "monotonic": 101.0}],
                actions=[
                    {"id": "a1", "kind": "tap", "points": [[0.1, 0.1]], "started_at": 100.1, "ended_at": 100.2, "hold_seconds": 0.0},
                    {"id": "a2", "kind": "tap", "points": [[0.9, 0.9]], "started_at": 101.1, "ended_at": 101.2, "hold_seconds": 0.0},
                ],
            )
            examples = bp.build_frame_action_dataset([session], "Test Game")
            self.assertEqual(len(examples), 2)
            self.assertEqual({example.source_frame_index for example in examples}, {0, 1})

    def test_v1_recording_with_no_actions_key_yields_no_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "legacy-session"
            frames_dir = session_dir / "frames"
            frames_dir.mkdir(parents=True)
            path = _write_frame(frames_dir, 0, (10, 120, 200))
            manifest = {
                "format": bp.RECORDING_FORMAT,
                "version": 1,
                "game": {"name": "Test Game", "key": bp.game_key("Test Game")},
                "started_at": "2026-01-01T00:00:00+0000",
                "capture_interval_seconds": bp.RECORDING_INTERVAL_SECONDS,
                "input_sent": False,
                "frames": [
                    {
                        "index": 0,
                        "path": str(path.relative_to(session_dir)),
                        "captured_at": "2026-01-01T00:00:00+0000",
                        "window": {"x": 0, "y": 0, "width": 200, "height": 200},
                    }
                ],
            }
            (session_dir / "manifest.json").write_text(json.dumps(manifest))
            examples = bp.build_frame_action_dataset([session_dir], "Test Game")
            self.assertEqual(examples, [])


class TrainedPolicyRoundTripTests(unittest.TestCase):
    def test_save_and_load_round_trip_proposes_the_saved_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_application_support = bp.application_support
            bp.application_support = lambda: Path(tmp)
            try:
                marker_image = Image.new("RGB", (200, 200), (255, 255, 255))
                draw = ImageDraw.Draw(marker_image)
                draw.rectangle((20, 20, 180, 180), fill=(30, 200, 30))
                draw.line((20, 20, 180, 180), fill=(0, 0, 0), width=2)

                example = bp.TrainingExample(
                    id="example001",
                    action=bp.Action(label="example001", kind=bp.ActionKind.TAP, points=((0.5, 0.5),), hold_seconds=0.0, confidence=1.0),
                    prefilter=bp.frame_prefilter(marker_image),
                    features=bp.frame_features(marker_image),
                    source_recording="fake-session",
                    source_frame_index=0,
                )
                saved_count = bp.save_trained_policy("Test Game", [example])
                self.assertEqual(saved_count, 1)

                policy = bp._load_trained_policy_impl("Test Game")
                self.assertIsNotNone(policy)
                self.assertTrue(policy.ready)

                proposed = policy.propose_action(marker_image)
                self.assertIsNotNone(proposed)
                self.assertEqual(proposed.kind, bp.ActionKind.TAP)
                self.assertEqual(proposed.points, ((0.5, 0.5),))
                self.assertGreaterEqual(proposed.confidence, bp.NN_POLICY_MATCH_THRESHOLD)

                unlike_image = Image.new("RGB", (200, 200), (0, 0, 0))
                self.assertIsNone(policy.propose_action(unlike_image))
            finally:
                bp.application_support = original_application_support

    def test_load_returns_none_when_no_model_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_application_support = bp.application_support
            bp.application_support = lambda: Path(tmp)
            try:
                self.assertIsNone(bp._load_trained_policy_impl("Never Trained Game"))
            finally:
                bp.application_support = original_application_support


if __name__ == "__main__":
    unittest.main()
