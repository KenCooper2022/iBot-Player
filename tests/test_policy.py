"""Tests for the Action/Policy abstraction that generalizes BotPlayer beyond Block Jam."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot_player as bp


class ActionFromTapMatchTests(unittest.TestCase):
    def test_wraps_a_match_as_a_single_point_tap(self):
        match = bp.Match(label="gem", x=0.4, y=0.6, confidence=0.95)
        action = bp.Action.from_tap_match(match)
        self.assertEqual(action.kind, bp.ActionKind.TAP)
        self.assertEqual(action.points, ((0.4, 0.6),))
        self.assertEqual(action.hold_seconds, 0.0)
        self.assertEqual(action.confidence, 0.95)
        self.assertEqual((action.x, action.y), (0.4, 0.6))


class StubClassifier:
    """A minimal stand-in for BlockJamClassifier used to test TemplateMatchPolicy in isolation."""

    def __init__(self, ready, match):
        self._ready = ready
        self._match = match

    @property
    def ready(self):
        return self._ready

    def next_confirmed_action(self, frame):
        return self._match


class TemplateMatchPolicyTests(unittest.TestCase):
    def test_not_ready_when_classifier_is_not_ready(self):
        policy = bp.TemplateMatchPolicy(StubClassifier(ready=False, match=None))
        self.assertFalse(policy.ready)

    def test_propose_action_returns_none_when_classifier_finds_nothing(self):
        policy = bp.TemplateMatchPolicy(StubClassifier(ready=True, match=None))
        self.assertIsNone(policy.propose_action(object()))

    def test_propose_action_wraps_the_classifiers_match(self):
        match = bp.Match(label="gem", x=0.1, y=0.2, confidence=0.9)
        policy = bp.TemplateMatchPolicy(StubClassifier(ready=True, match=match))
        action = policy.propose_action(object())
        self.assertEqual(action.label, "gem")
        self.assertEqual(action.kind, bp.ActionKind.TAP)
        self.assertEqual(action.points, ((0.1, 0.2),))


class SelectPolicyTests(unittest.TestCase):
    def test_falls_back_to_template_match_when_nothing_is_trained(self):
        # No trained model exists for a throwaway game name, so this must fall
        # back to the always-available BlockJamClassifier-backed policy.
        policy = bp.select_policy("Nonexistent Test Game 12345")
        self.assertIsInstance(policy, bp.TemplateMatchPolicy)


if __name__ == "__main__":
    unittest.main()
