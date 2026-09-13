"""Characterization tests for bot_player.py's pure image/logic functions.

These tests pin down current behavior of the parts of the monolith that do
not touch Quartz/AppKit (window lookup, native input, TCC/permissions), so a
later mechanical file split or refactor can be checked against them. They are
not meant to exercise the macOS-only capture/input code paths.
"""

import argparse
import json
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot_player as bp


def solid_frame(size=(300, 300), background=(255, 255, 255)):
    return Image.new("RGB", size, background)


def stamp_square(frame, box, color):
    """Draw a distinctly colored, textured square onto frame at box=(l,t,r,b)."""
    draw = ImageDraw.Draw(frame)
    draw.rectangle(box, fill=color)
    left, top, right, bottom = box
    # Add internal texture so ImageStat variance-based "usable" checks pass.
    draw.line((left, top, right, bottom), fill=(0, 0, 0), width=2)
    draw.line((left, bottom, right, top), fill=(0, 0, 0), width=2)
    return frame


class NormalizedRegionTests(unittest.TestCase):
    def test_valid_region_parses(self):
        self.assertEqual(bp.normalized_region("0.1,0.2,0.3,0.4"), (0.1, 0.2, 0.3, 0.4))

    def test_region_outside_window_is_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            bp.normalized_region("0.9,0.9,0.5,0.5")

    def test_malformed_region_is_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            bp.normalized_region("not,a,region")


class CropNormalizedTests(unittest.TestCase):
    def test_crop_extracts_expected_pixel_box(self):
        frame = solid_frame((200, 100))
        cropped = bp.crop_normalized(frame, (0.25, 0.5, 0.5, 0.25))
        self.assertEqual(cropped.size, (100, 25))


class GameKeyTests(unittest.TestCase):
    def test_normalizes_case_and_punctuation(self):
        self.assertEqual(bp.game_key("Block Jam 3D!"), "block-jam-3d")

    def test_empty_name_falls_back_to_game(self):
        self.assertEqual(bp.game_key("***"), "game")


class FrameUsabilityTests(unittest.TestCase):
    def test_blank_frame_is_unusable(self):
        self.assertFalse(bp._frame_is_usable(solid_frame((200, 200), (255, 255, 255))))

    def test_textured_frame_is_usable(self):
        frame = solid_frame((200, 200))
        stamp_square(frame, (20, 20, 180, 180), (30, 120, 200))
        self.assertTrue(bp._frame_is_usable(frame))

    def test_tiny_frame_is_unusable(self):
        self.assertFalse(bp._frame_is_usable(solid_frame((50, 50))))


class FingerprintTests(unittest.TestCase):
    def test_identical_frames_are_stable_and_unchanged(self):
        frame = solid_frame((200, 200))
        stamp_square(frame, (40, 40, 120, 120), (10, 200, 10))
        before = bp.board_fingerprint(frame)
        after = bp.board_fingerprint(frame.copy())
        self.assertFalse(bp.board_changed(before, after))
        self.assertTrue(bp.fingerprints_stable(before, after))

    def test_large_change_is_detected(self):
        before_frame = solid_frame((200, 200), (255, 255, 255))
        after_frame = solid_frame((200, 200), (255, 255, 255))
        stamp_square(after_frame, (40, 60, 160, 200), (0, 0, 0))
        before = bp.board_fingerprint(before_frame)
        after = bp.board_fingerprint(after_frame)
        self.assertTrue(bp.board_changed(before, after))
        self.assertFalse(bp.fingerprints_stable(before, after))

    def test_difference_fraction_is_zero_for_identical_fingerprints(self):
        frame = solid_frame((200, 200))
        stamp_square(frame, (40, 40, 120, 120), (10, 200, 10))
        before = bp.board_fingerprint(frame)
        after = bp.board_fingerprint(frame.copy())
        self.assertEqual(bp.fingerprint_difference_fraction(before, after), 0.0)

    def test_difference_fraction_is_one_for_mismatched_lengths(self):
        self.assertEqual(bp.fingerprint_difference_fraction(b"", b"\x00"), 1.0)


class BoardChangeDiagnosticTests(unittest.TestCase):
    def test_saves_before_after_and_region_crops_with_change_fraction(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            original_application_support = bp.application_support
            bp.application_support = lambda: Path(tmp)
            try:
                before_frame = solid_frame((200, 200), (255, 255, 255))
                after_frame = solid_frame((200, 200), (255, 255, 255))
                stamp_square(after_frame, (40, 60, 160, 180), (0, 0, 0))

                result_dir = bp.save_board_change_diagnostic("Block Jam 3D", before_frame, after_frame)

                self.assertTrue((result_dir / "before-full.png").is_file())
                self.assertTrue((result_dir / "after-full.png").is_file())
                self.assertTrue((result_dir / "before-board-region.png").is_file())
                self.assertTrue((result_dir / "after-board-region.png").is_file())
                info = json.loads((result_dir / "info.json").read_text())
                self.assertEqual(info["game"], "Block Jam 3D")
                self.assertEqual(info["board_change_threshold"], bp.BOARD_CHANGE_THRESHOLD)
                self.assertGreater(info["change_fraction"], 0.0)
            finally:
                bp.application_support = original_application_support


class BestMatchTests(unittest.TestCase):
    def test_finds_known_marker_position(self):
        frame = solid_frame((300, 300))
        box = (150, 30, 210, 90)  # 60x60 marker at top-right-ish
        stamp_square(frame, box, (200, 30, 30))
        marker = frame.crop(box)
        template = bp.Template(label="marker", role="target", relative_width=60 / 300, relative_height=60 / 300, image=marker)

        match = bp.best_match(frame, template)

        self.assertIsNotNone(match)
        expected_x = (150 + 210) / 2 / 300
        expected_y = (30 + 90) / 2 / 300
        self.assertAlmostEqual(match.x, expected_x, delta=0.03)
        self.assertAlmostEqual(match.y, expected_y, delta=0.03)
        self.assertGreater(match.confidence, 0.9)

    def test_absent_marker_scores_low_confidence(self):
        frame = solid_frame((300, 300))
        marker = solid_frame((60, 60), (0, 0, 0))
        stamp_square(marker, (5, 5, 55, 55), (255, 255, 0))
        template = bp.Template(label="marker", role="target", relative_width=0.2, relative_height=0.2, image=marker)

        match = bp.best_match(frame, template)

        self.assertIsNotNone(match)
        self.assertLess(match.confidence, bp.MATCH_THRESHOLD)


class BlockJamClassifierTests(unittest.TestCase):
    def _templates_for(self, label):
        target_image = solid_frame((40, 40), (0, 0, 0))
        stamp_square(target_image, (4, 4, 36, 36), (255, 200, 0))
        pile_image = target_image.copy()
        target = bp.Template(label=label, role="target", relative_width=40 / 400, relative_height=40 / 200, image=target_image)
        pile = bp.Template(label=label, role="pile", relative_width=40 / 400, relative_height=40 / 200, image=pile_image)
        return target, pile, target_image

    def test_not_ready_without_matching_target_and_pile_labels(self):
        target, _pile, _img = self._templates_for("gem")
        classifier = bp.BlockJamClassifier([target])
        self.assertFalse(classifier.ready)

    def test_confirms_action_only_when_both_regions_match(self):
        target, pile, marker = self._templates_for("gem")
        classifier = bp.BlockJamClassifier([target, pile])
        self.assertTrue(classifier.ready)

        frame = solid_frame((400, 200))
        # best_match's search grid starts at each region's own top-left corner
        # and steps by 5px, so placement must land on that grid to score 1.0.
        target_box = (10, 5, 50, 45)  # inside top 30% strip, grid-aligned to (0, 0)
        pile_box = (208, 98, 248, 138)  # inside the 24-72% pile band, grid-aligned to (8, 48)
        frame.paste(marker, target_box[:2])
        frame.paste(marker, pile_box[:2])

        action = classifier.next_confirmed_action(frame)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "gem")
        self.assertGreaterEqual(action.confidence, bp.MATCH_THRESHOLD)

    def test_no_action_when_pile_item_is_missing(self):
        target, pile, marker = self._templates_for("gem")
        classifier = bp.BlockJamClassifier([target, pile])

        frame = solid_frame((400, 200))
        frame.paste(marker, (10, 5))  # only the target strip has the marker

        self.assertIsNone(classifier.next_confirmed_action(frame))


class TrainingSimilarityTests(unittest.TestCase):
    def test_identical_crops_are_maximally_similar(self):
        image = solid_frame((40, 40))
        stamp_square(image, (5, 5, 35, 35), (10, 10, 200))
        self.assertGreater(bp._training_similarity(image, image.copy()), 0.99)

    def test_different_crops_are_less_similar(self):
        left = solid_frame((40, 40), (255, 255, 255))
        right = solid_frame((40, 40), (0, 0, 0))
        self.assertLess(bp._training_similarity(left, right), 0.5)


class GenerateTrainingCandidatesTests(unittest.TestCase):
    def _frame_with_matching_marker(self, index):
        frame = solid_frame((400, 300))
        marker = solid_frame((60, 60), (0, 0, 0))
        stamp_square(marker, (5, 5, 55, 55), (0, 180, 240))
        # Same normalized position in every frame so proposals accumulate support.
        frame.paste(marker, (20, 20))  # inside TRAINING_TARGET_REGION (top 30%)
        frame.paste(marker, (150, 120))  # inside TRAINING_PILE_REGION
        return bp.TrainingFrame(image=frame, index=index, timestamp=float(index))

    def test_raises_when_too_few_frames(self):
        frames = [self._frame_with_matching_marker(i) for i in range(3)]
        with self.assertRaises(bp.TrainingSourceError):
            bp.generate_training_candidates(frames, "Block Jam 3D")

    def test_repeated_pairs_across_frames_become_trustworthy(self):
        frames = [self._frame_with_matching_marker(i) for i in range(bp.MIN_TRAINING_FRAMES)]
        candidates = bp.generate_training_candidates(frames, "Block Jam 3D")
        self.assertTrue(candidates)
        self.assertTrue(all(candidate["support"] >= 2 for candidate in candidates))

    def test_blank_footage_has_no_trustworthy_pairs(self):
        frames = [bp.TrainingFrame(image=solid_frame((400, 300)), index=i, timestamp=float(i)) for i in range(bp.MIN_TRAINING_FRAMES)]
        with self.assertRaises(bp.TrainingSourceError):
            bp.generate_training_candidates(frames, "Block Jam 3D")


if __name__ == "__main__":
    unittest.main()
