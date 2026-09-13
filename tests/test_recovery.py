"""Tests for BotPlayer's recoverable-stop / auto-restart mechanism.

A stop is only ever auto-restarted when it was explicitly marked
recoverable AND the user hasn't asked Bot Player to stop AND play is still
requested. STOP_REQUESTED must always win regardless of how a stop was
marked -- that's the property these tests exist to pin down.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot_player as bp


class StubPolicy:
    name = "stub"

    @property
    def ready(self):
        return True

    def propose_action(self, frame):
        return None


def make_player():
    return bp.BotPlayer(game="Test Game", allow_play=True, icon_template=None, policy=StubPolicy())


class BotPlayerStopTests(unittest.TestCase):
    def test_stop_defaults_to_not_recoverable(self):
        player = make_player()
        player.stop("something went wrong")
        self.assertFalse(player.running)
        self.assertFalse(player.stop_was_recoverable)

    def test_stop_can_be_marked_recoverable(self):
        player = make_player()
        player.stop("transient hiccup", recoverable=True)
        self.assertFalse(player.running)
        self.assertTrue(player.stop_was_recoverable)

    def test_second_stop_call_does_not_overwrite_first_recoverable_flag(self):
        player = make_player()
        player.stop("first stop", recoverable=True)
        player.stop("second stop", recoverable=False)
        # stop() is a no-op once already stopped, so the original flag stands.
        self.assertTrue(player.stop_was_recoverable)


class AutoRestartDecisionTests(unittest.TestCase):
    def setUp(self):
        self._stop_was_set = bp.STOP_REQUESTED.is_set()
        self._start_was_set = bp.START_REQUESTED.is_set()
        bp.STOP_REQUESTED.clear()
        bp.START_REQUESTED.set()

    def tearDown(self):
        if self._stop_was_set:
            bp.STOP_REQUESTED.set()
        else:
            bp.STOP_REQUESTED.clear()
        if self._start_was_set:
            bp.START_REQUESTED.set()
        else:
            bp.START_REQUESTED.clear()

    def test_restarts_when_recoverable_and_play_still_requested(self):
        player = make_player()
        player.stop("transient hiccup", recoverable=True)
        self.assertTrue(bp._should_auto_restart(player))
        new_player, restarting = bp._restart_or_stop(player)
        self.assertTrue(restarting)
        self.assertIsNone(new_player)

    def test_user_stop_request_overrides_a_recoverable_flag(self):
        player = make_player()
        player.stop("transient hiccup", recoverable=True)
        bp.STOP_REQUESTED.set()
        self.assertFalse(bp._should_auto_restart(player))
        new_player, restarting = bp._restart_or_stop(player)
        self.assertFalse(restarting)
        self.assertIs(new_player, player)

    def test_non_recoverable_stop_never_restarts(self):
        player = make_player()
        player.stop("permission lost", recoverable=False)
        self.assertFalse(bp._should_auto_restart(player))
        new_player, restarting = bp._restart_or_stop(player)
        self.assertFalse(restarting)
        self.assertIs(new_player, player)

    def test_does_not_restart_once_play_is_no_longer_requested(self):
        player = make_player()
        player.stop("transient hiccup", recoverable=True)
        bp.START_REQUESTED.clear()
        self.assertFalse(bp._should_auto_restart(player))


if __name__ == "__main__":
    unittest.main()
