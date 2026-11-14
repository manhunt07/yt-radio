#!/usr/bin/env python3
"""Search YouTube and play a queue of audio tracks from the terminal."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
SEARCH_TIMEOUT = 45

# mpv reads these bindings from a temporary file. No user config is changed.
PLAYER_KEYS = """\
n playlist-next weak
p playlist-prev weak
l cycle-values loop-file inf no; print-text "Repeat track: ${loop-file}"
L cycle-values loop-playlist inf no; print-text "Repeat queue: ${loop-playlist}"
q quit
"""


def clean_text(value, fallback="", limit=105):
    """Keep remote titles on one line and strip terminal control characters."""
    if not isinstance(value, str):
        return fallback
    value = "".join(" " if char.isspace() else char for char in value
                    if char.isspace() or not unicodedata.category(char).startswith("C"))
    value = " ".join(value.split())
    return (value[:limit - 1] + "…" if len(value) > limit else value) or fallback


def duration_label(entry):
    if entry.get("is_live") or entry.get("live_status") == "is_live":
        return "LIVE"
    seconds = entry.get("duration")
    if not isinstance(seconds, (int, float)) or not 0 <= seconds < 10**9:
        return "—"
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def find_ytdlp():
    dedicated = Path.home() / ".local/share/yt-radio/venv/bin/yt-dlp"
    if dedicated.is_file() and os.access(dedicated, os.X_OK):
        return str(dedicated)
    return shutil.which("yt-dlp")


def search(ytdlp, query, limit, runtime):
    """Fetch YouTube-ranked video results without resolving or playing them."""
    command = [
        ytdlp, "--ignore-config", "--flat-playlist", "--dump-single-json",
        "--skip-download", "--socket-timeout", "12",
    ]
    if runtime:
        command.extend(["--js-runtimes", runtime])
    command.extend(["--", f"ytsearch{limit}:{query}"])
    process = subprocess.run(
        command, capture_output=True, encoding="utf-8", errors="replace",
        timeout=SEARCH_TIMEOUT, check=True,
    )
    response = json.loads(process.stdout)
    if not isinstance(response, dict) or not isinstance(response.get("entries"), list):
        raise ValueError("Unexpected search response from yt-dlp.")

    results = []
    seen = set()
    for entry in response["entries"]:
        if not isinstance(entry, dict):
            continue
        video_id = entry.get("id")
        if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
            continue
        if video_id in seen:
            continue
        seen.add(video_id)
        title = clean_text(entry.get("title"), "(Untitled)")
        channel = clean_text(entry.get("channel"), limit=60) or clean_text(
            entry.get("uploader"), "Unknown channel", limit=60
        )
        results.append((video_id, title, channel, duration_label(entry)))
        if len(results) == limit:
            break
    return results


def play_queue(mpv, ytdlp, runtime, results, start_index):
    """Pass the whole result list to mpv and start at the selected track."""
    _, title, _, _ = results[start_index]
    raw_options = "ignore-config="
    if runtime:
        raw_options += f",js-runtimes={runtime}"
    urls = [f"https://www.youtube.com/watch?v={video_id}" for video_id, *_ in results]

    print(f"\nStarting at {start_index + 1}/{len(results)}  {title}\n"
          "n next · p previous · l repeat track · Shift+L repeat queue\n"
          "Space pause/resume · ←/→ seek · 9/0 volume · q back\n", flush=True)

    with tempfile.TemporaryDirectory(prefix="yt-radio-") as folder:
        keys_path = Path(folder) / "input.conf"
        keys_path.write_text(PLAYER_KEYS, encoding="utf-8")
        status = subprocess.run([
            mpv, "--no-config", "--vid=no", "--ytdl=yes", "--ytdl-format=bestaudio",
            f"--input-conf={keys_path}", f"--playlist-start={start_index}",
            "--loop-file=no", "--loop-playlist=no",
            f"--script-opts=ytdl_hook-ytdl_path={ytdlp}",
            f"--ytdl-raw-options={raw_options}", "--", *urls,
        ]).returncode
    if status:
        print("Playback failed. Try another result or update yt-dlp.", file=sys.stderr)


def choose(results):
    print()
    for index, (_, title, channel, duration) in enumerate(results, 1):
        print(f" {index:2}. {title}\n     {channel}  ·  {duration}")
    while True:
        answer = input("\nChoose a number · Enter new search · q quit › ").strip().lower()
        if not answer or answer == "q":
            return answer
        if re.fullmatch(r"[0-9]{1,2}", answer) and 1 <= int(answer) <= len(results):
            return int(answer) - 1
        print(f"Enter a number from 1 to {len(results)}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help="Optional initial search, e.g. artist song")
    parser.add_argument("-n", "--limit", type=int, default=12,
                        help="Maximum results, from 1 to 30 (default: 12)")
    args = parser.parse_args()
    if not 1 <= args.limit <= 30:
        parser.error("--limit must be between 1 and 30")

    ytdlp, mpv = find_ytdlp(), shutil.which("mpv")
    if not ytdlp or not mpv:
        missing = ", ".join(name for name, path in (("yt-dlp", ytdlp), ("mpv", mpv)) if not path)
        print(f"Missing dependency: {missing}. Install it before running yt-radio.",
              file=sys.stderr)
        return 1

    # Prefer Deno when present. Enable Node explicitly otherwise.
    runtime = "node" if shutil.which("node") and not shutil.which("deno") else None
    print("\n YT RADIO  /  YouTube audio from your terminal\n" + "─" * 49)
    pending = " ".join(args.query).strip()

    while True:
        query = pending or input("\nSong or artist (blank to quit) › ").strip()
        pending = ""
        if not query:
            return 0
        print(f"Searching YouTube for {query!r}…", flush=True)
        try:
            results = search(ytdlp, query, args.limit, runtime)
        except subprocess.TimeoutExpired:
            print("Search timed out. Check your connection and try again.", file=sys.stderr)
            continue
        except subprocess.CalledProcessError as error:
            lines = (error.stderr or "").splitlines()
            reason = clean_text(lines[-1], limit=250) if lines else ""
            print(f"Search failed: {reason or 'Check your connection and yt-dlp version.'}",
                  file=sys.stderr)
            continue
        except (ValueError, OSError):
            print("Could not read YouTube results. Try updating yt-dlp.", file=sys.stderr)
            continue
        if not results:
            print("No videos found. Try adding the artist or changing your search.")
            continue

        while True:
            choice = choose(results)
            if choice == "q":
                return 0
            if choice == "":
                break
            play_queue(mpv, ytdlp, runtime, results, choice)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
