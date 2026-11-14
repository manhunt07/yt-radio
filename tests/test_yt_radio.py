"""Offline tests for search, menu selection, and player configuration."""

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "yt-radio.py"
SPEC = importlib.util.spec_from_file_location("yt_radio", SCRIPT)
radio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(radio)


class SearchTests(unittest.TestCase):
    @patch.object(radio.subprocess, "run")
    def test_keeps_search_order_and_filters_invalid_or_duplicate_ids(self, run):
        query = "Sauti Sol & Friends"
        run.return_value.stdout = json.dumps({"entries": [
            None,
            {"id": "invalid"},
            {"id": "0123456789B", "title": "Second\nline", "channel": "Artist", "duration": 205},
            {"id": "0123456789B", "title": "Duplicate"},
            {"id": "0123456789A", "title": "Live", "is_live": True},
        ]})
        results = radio.search("yt-dlp", query, 5, "node")
        self.assertEqual(results, [
            ("0123456789B", "Second line", "Artist", "3:25"),
            ("0123456789A", "Live", "Unknown channel", "LIVE"),
        ])
        self.assertEqual(run.call_args.args[0][-2:], ["--", f"ytsearch5:{query}"])

    @patch.object(radio.subprocess, "run")
    def test_rejects_unexpected_search_response(self, run):
        run.return_value.stdout = '{"entries": null}'
        with self.assertRaises(ValueError):
            radio.search("yt-dlp", "song", 12, None)


class PlayerTests(unittest.TestCase):
    @patch("builtins.print")
    @patch("builtins.input", side_effect=["99", "2"])
    def test_menu_reprompts_and_returns_zero_based_index(self, _input, _print):
        self.assertEqual(radio.choose([
            ("0123456789A", "First", "Artist", "2:00"),
            ("0123456789B", "Second", "Artist", "3:30"),
        ]), 1)

    @patch("builtins.print")
    @patch.object(radio.subprocess, "run")
    def test_queue_starts_at_selection_and_has_audio_only_controls(self, run, _print):
        def fake_player(args):
            self.assertIn("--vid=no", args)
            self.assertIn("--ytdl-format=bestaudio", args)
            self.assertIn("--playlist-start=1", args)
            self.assertEqual(args[args.index("--") + 1:], [
                "https://www.youtube.com/watch?v=0123456789A",
                "https://www.youtube.com/watch?v=0123456789B",
            ])
            path = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--input-conf="))
            bindings = Path(path).read_text(encoding="utf-8")
            for binding in (
                "n playlist-next weak",
                "p playlist-prev weak",
                "l cycle-values loop-file inf no",
                "L cycle-values loop-playlist inf no",
                "q quit",
            ):
                self.assertIn(binding, bindings)
            return subprocess.CompletedProcess(args, 0)

        run.side_effect = fake_player
        radio.play_queue("mpv", "yt-dlp", None, [
            ("0123456789A", "First", "Artist", "2:00"),
            ("0123456789B", "Second", "Artist", "3:30"),
        ], 1)
        run.assert_called_once()
