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


# mpv retains stdin and all existing key bindings. Lua owns only the display.
CASSETTE_SCRIPT = r"""
local mp = require "mp"
local utils = require "mp.utils"
local tracks = utils.parse_json(@TRACKS@)
local width = @WIDTH@
local reel = {"o-", "oo", "-o", "OO"}
local tick, last_time = 0, nil
local active, last_line, painted = false, "", 0
local shown = nil

local function clear()
    if painted > 0 then
        io.stderr:write("\r", string.rep(" ", painted), "\r")
        io.stderr:flush()
    end
    last_line, painted = "", 0
end

local function clock(seconds)
    if not seconds or seconds ~= seconds or seconds < 0 then return "--:--" end
    seconds = math.floor(seconds)
    if seconds >= 3600 then
        return string.format("%d:%02d:%02d", math.floor(seconds / 3600),
                             math.floor(seconds / 60) % 60, seconds % 60)
    end
    return string.format("%02d:%02d", math.floor(seconds / 60), seconds % 60)
end

local function track_card()
    local index = mp.get_property_number("playlist-pos", -1) + 1
    if index == shown or not tracks[index] then return end
    shown = index
    clear()
    local track = tracks[index]
    local duration = mp.get_property_number("duration")
    local codec = mp.get_property("audio-codec-name", ""):gsub("[^%w ._%-]", ""):sub(1, 16)
    local rate = mp.get_property_number("audio-params/samplerate")
    local channels = mp.get_property_number("audio-params/channel-count")
    local date = mp.get_property("metadata/by-key/Date", "")
    local year, month, day = date:match("^(%d%d%d%d)(%d%d)(%d%d)$")
    if not year then year, month, day = date:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)$") end
    io.stderr:write("\nSIDE A / NOW PLAYING\n", string.rep("-", math.min(48, width)), "\n")
    for _, line in ipairs(track.title) do io.stderr:write(line, "\n") end
    for _, line in ipairs(track.channel) do io.stderr:write(line, "\n") end
    io.stderr:write(string.format("  Queue    %02d / %02d\n", index, #tracks))
    io.stderr:write("  Length   ", duration and clock(duration) or track.duration, "\n")
    if year then io.stderr:write("  Date     ", year, "-", month, "-", day, "\n") end
    if codec ~= "" then io.stderr:write("  Codec    ", codec:sub(1, width - 11), "\n") end
    if rate then io.stderr:write(string.format("  Audio    %g kHz\n", rate / 1000)) end
    if channels then io.stderr:write(string.format("  Channels %d\n", channels)) end
    for _, line in ipairs(track.source) do io.stderr:write(line, "\n") end
    io.stderr:write(string.rep("-", math.min(48, width)), "\n")
    io.stderr:flush()
end

local function refresh()
    if not active then return end
    local now = mp.get_time()
    local position = mp.get_property_number("time-pos")
    local duration = mp.get_property_number("duration")
    local buffering = mp.get_property_bool("paused-for-cache", false)
    local seeking = mp.get_property_bool("seeking", false)
    local paused = mp.get_property_bool("pause", false)
    local state = buffering and "BUFFER" or seeking and "SEEK"
                  or paused and "PAUSE" or position and "PLAY" or "LOAD"
    if state == "PLAY" and last_time then
        tick = tick + math.min(0.2, math.max(0, now - last_time))
    end
    last_time = now
    local phase = math.floor(tick * 7) % #reel + 1
    local tape = "[(" .. reel[phase] .. ")=" .. "(" .. reel[#reel + 1 - phase] .. ")]"
    local line = tape .. " " .. state
    local timed = line .. " " .. clock(position) .. "/" .. clock(duration)
    if #timed <= width then
        line = timed
        if duration and duration > 0 and width - #line >= 9 then
            local size = math.min(15, width - #line - 3)
            local filled = math.floor(size * math.min(1, math.max(0, (position or 0) / duration)))
            line = line .. " [" .. string.rep("#", filled) .. string.rep(".", size - filled) .. "]"
        end
        local volume = mp.get_property_number("volume")
        local vol = volume and string.format("  VOL %d%%", math.floor(volume + 0.5)) or ""
        if #line + #vol <= width then line = line .. vol end
    end
    if line ~= last_line then
        io.stderr:write("\r", line, string.rep(" ", math.max(0, painted - #line)))
        io.stderr:flush()
        last_line, painted = line, #line
    end
end

mp.add_periodic_timer(0.065, refresh)
mp.register_event("start-file", function()
    clear()
    active, shown, tick, last_time = true, nil, 0, nil
    refresh()
end)
mp.register_event("playback-restart", function()
    track_card()
    refresh()
end)
mp.register_event("end-file", function()
    active = false
    clear()
end)
mp.register_event("shutdown", clear)
"""

def terminal_columns():
    return shutil.get_terminal_size(fallback=(80, 24)).columns


def rich_terminal(output):
    """Keep redirected output and minimal terminals free of ANSI escapes."""
    return output.isatty() and os.environ.get("TERM") != "dumb"


def wrap_field(label, value, width):
    """Wrap metadata by terminal cells, preserving long titles and URLs."""
    prefix = f"  {label:<9}"
    indent = " " * len(prefix)
    space = max(1, width - len(prefix))
    lines = []
    line, used = "", 0
    for char in value:
        cells = (0 if unicodedata.category(char) in {"Mn", "Me"} else
                 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1)
        if line and used + cells > space:
            last_space = line.rfind(" ")
            if last_space > 0 and char != " ":
                front, line = line[:last_space], line[last_space + 1:]
                lines.append(front)
                used = sum(0 if unicodedata.category(c) in {"Mn", "Me"} else
                           2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1
                           for c in line)
            if line and used + cells > space:
                lines.append(line.rstrip())
                line, used = "", 0
        if line or char != " ":
            line += char
            used += cells
    lines.append(line.rstrip())
    return [prefix + lines[0], *(indent + line for line in lines[1:])]


def cassette_source(results, urls, width):
    tracks = [
        {
            "title": wrap_field("Title", title, width),
            "channel": wrap_field("Channel", channel, width),
            "duration": duration,
            "source": wrap_field("URL", url, width),
        }
        for (_, title, channel, duration), url in zip(results, urls)
    ]
    data = json.dumps(tracks, ensure_ascii=False)
    boundary = "="
    while "]" + boundary + "]" in data:
        boundary += "="
    literal = f"[{boundary}[{data}]{boundary}]"
    return CASSETTE_SCRIPT.replace("@WIDTH@", str(width)).replace("@TRACKS@", literal)


def print_signature(plain=False):
    width = terminal_columns()
    if plain or not rich_terminal(sys.stdout) or width < 38:
        print("\nYT Radio | written by manhunt07\n", flush=True)
        return

    colors = not os.environ.get("NO_COLOR")
    def tint(text, code):
        return f"\033[{code}m{text}\033[0m" if colors else text

    edge = "  +" + "-" * 32 + "+"
    rows = [
        tint(edge, "33"),
        "  " + tint("|", "33") + "  " + tint("SIDE A", "1;33") + "      " + tint("TERMINAL AUDIO", "36") + "    " + tint("|", "33"),
        "  " + tint("|", "33") + "  " + tint("YT RADIO", "1;97;44") + " " * 22 + tint("|", "33"),
        "  " + tint("|", "33") + "  " + tint("written by manhunt07", "1;36") + " " * 10 + tint("|", "33"),
        tint(edge, "33"),
    ]
    print("\n" + "\n".join(rows) + "\n", flush=True)


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
    name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    candidates = (
        Path(sys.executable).parent / name,
        Path.home() / ".local/share/yt-radio/venv/bin/yt-dlp",
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("yt-dlp")


def find_mpv():
    """Prefer the Windows console launcher for terminal keyboard controls."""
    if os.name == "nt":
        return shutil.which("mpv.com") or shutil.which("mpv.exe")
    return shutil.which("mpv")


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
        title = clean_text(entry.get("title"), "(Untitled)", limit=480)
        channel = clean_text(entry.get("channel"), limit=60) or clean_text(
            entry.get("uploader"), "Unknown channel", limit=60
        )
        results.append((video_id, title, channel, duration_label(entry)))
        if len(results) == limit:
            break
    return results


def play_queue(mpv, ytdlp, runtime, results, start_index, plain=False):
    """Pass the whole result list to mpv and start at the selected track."""
    _, title, _, _ = results[start_index]
    raw_options = "ignore-config="
    if runtime:
        raw_options += f",js-runtimes={runtime}"
    urls = [f"https://www.youtube.com/watch?v={video_id}" for video_id, *_ in results]

    width = terminal_columns()
    show_deck = not plain and rich_terminal(sys.stderr) and width >= 24
    if not show_deck:
        print(f"\nStarting at {start_index + 1}/{len(results)}  {title}", flush=True)
    print("\nn next · p previous · l repeat track\n"
          "Shift+L repeat queue · Space pause\n"
          "←/→ seek · 9/0 volume · q back\n", flush=True)

    with tempfile.TemporaryDirectory(prefix="yt-radio-") as folder:
        keys_path = Path(folder) / "input.conf"
        keys_path.write_text(PLAYER_KEYS, encoding="utf-8")
        visual = []
        if show_deck:
            cassette_path = Path(folder) / "cassette.lua"
            cassette_path.write_text(cassette_source(results, urls, min(90, width - 1)),
                                     encoding="utf-8")
            visual = ["--quiet", "--msg-level=all=warn", f"--script={cassette_path}"]
        status = subprocess.run([
            mpv, "--no-config", "--vid=no", "--ytdl=yes", "--ytdl-format=bestaudio",
            f"--input-conf={keys_path}", f"--playlist-start={start_index}",
            "--loop-file=no", "--loop-playlist=no",
            f"--script-opts=ytdl_hook-ytdl_path={ytdlp}",
            f"--ytdl-raw-options={raw_options}", *visual, "--", *urls,
        ]).returncode
    if status:
        print("Playback failed. Try another result or update yt-dlp.", file=sys.stderr)


def choose(results):
    print()
    for index, (_, title, channel, duration) in enumerate(results, 1):
        width = terminal_columns()
        if rich_terminal(sys.stdout) and width >= 24:
            lines = wrap_field("", title, min(105, width - 1) + 6)
            label = f" {index:2}. "
            print(label + lines[0][11:])
            for line in lines[1:]:
                print(" " * len(label) + line[11:])
        else:
            print(f" {index:2}. {title}")
        print(f"     {channel}  ·  {duration}")
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
    parser.add_argument("--plain", action="store_true", help="Disable the cassette and styled banner")
    args = parser.parse_args()
    if not 1 <= args.limit <= 30:
        parser.error("--limit must be between 1 and 30")

    print_signature(args.plain)
    ytdlp, mpv = find_ytdlp(), find_mpv()
    if not ytdlp or not mpv:
        missing = ", ".join(name for name, path in (("yt-dlp", ytdlp), ("mpv", mpv)) if not path)
        print(f"Missing dependency: {missing}. Install it before running yt-radio.",
              file=sys.stderr)
        return 1

    # Prefer Deno when present. Enable Node explicitly otherwise.
    runtime = "node" if shutil.which("node") and not shutil.which("deno") else None
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
            play_queue(mpv, ytdlp, runtime, results, choice, args.plain)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
