# YT Radio

**Search YouTube. Pick a track. Listen from your terminal.**

YT Radio is a small Python CLI that turns YouTube video search results into an audio-only playback queue. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for search and stream extraction, and [mpv](https://mpv.io/) for playback. It doesn't open a video window, save audio files, or require a YouTube API key.

## What it does

- Searches by song, artist, or keywords and displays ranked video results with titles, channels, and durations when available.
- Starts playback at the result you pick and automatically advances through the rest of the queue.
- Lets you skip tracks, go back, pause, seek, and repeat the current track or the full queue.

Search uses YouTube's video results as returned by yt-dlp. Results may differ from a signed-in browser, and channels and playlists aren't shown.

## Requirements

| Dependency | What it does |
| --- | --- |
| Python 3.11+ and `venv` | Runs the CLI and keeps dependencies separate from your system Python. |
| mpv | Streams the selected audio and handles playback controls. |
| yt-dlp with its default extras | Searches YouTube and resolves audio streams. Installed from `requirements.txt`. |
| Node.js 22+ **or** Deno 2.3+ | Provides the JavaScript runtime yt-dlp uses for YouTube playback. Use a current supported release. |
| Internet connection and an interactive terminal | Needed for search, streaming, and keyboard controls. |

See the [yt-dlp JavaScript setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS) for runtime details. YT Radio enables Node if it finds Node on your `PATH` and does not find Deno.

## Setup on Kali, Debian, or Ubuntu

Run these commands from the project folder. Install a supported version of Node.js or Deno separately if you don't have one on your `PATH`.

```bash
sudo apt update
sudo apt install python3 python3-venv mpv
python3 -m venv "$HOME/.local/share/yt-radio/venv"
"$HOME/.local/share/yt-radio/venv/bin/python" -m pip install -r requirements.txt
python3 yt-radio.py
```

The script checks the dedicated virtual environment first, then looks for `yt-dlp` on your `PATH`. You don't need to activate the environment.

### Run it from any directory

```bash
sudo install -m 0755 yt-radio.py /usr/local/bin/yt-radio
yt-radio --help
```

Use `/usr/local/bin/yt-radio` if that directory isn't on your shell's `PATH`. Run the player as your normal user, without `sudo`. Re-run the install command after updating the script.

## Usage

```bash
yt-radio
yt-radio "Sauti Sol Suzanna"
yt-radio --limit 20 "Diamond Platnumz live"
```

With no query, the app prompts you for one. Choose a number to start at that result. The default is 12 results, and `--limit` accepts 1–30. From the results menu, press **Enter** to search again or **q** to exit.

| Key during playback | Action |
| --- | --- |
| `n` | Next track |
| `p` | Previous track |
| `l` (lowercase L) | Toggle repeat for the current track |
| `Shift+L` | Toggle repeat for the whole queue |
| `Space` | Pause or resume |
| `←` / `→` | Seek backward or forward |
| `9` / `0` | Lower or raise volume |
| `q` | Stop playback and return to the results |

## Troubleshooting

- **Search works but playback fails.** Confirm that `mpv --version` works and that `node --version` or `deno --version` reports a supported runtime. Try another video. Some videos may be unavailable or may not expose a playable audio-only stream.
- **YouTube extraction stopped working.** Update yt-dlp and its extras, then retry.

  ```bash
  "$HOME/.local/share/yt-radio/venv/bin/python" -m pip install --upgrade -r requirements.txt
  ```

- **The command isn't found.** Run `python3 yt-radio.py` from the project folder or use the absolute path from the installation step.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The tests mock search and playback, so they don't need YouTube access or a sound device. The included GitHub Actions workflow runs them on pushes and pull requests. These tests don't establish live streaming availability.

YT Radio is an independent project and is not affiliated with YouTube.
