# YT Radio

**Search YouTube. Pick a track. Listen from your terminal.**

YT Radio is a small Python CLI that turns YouTube video search results into an audio-only playback queue. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for search and stream extraction, and [mpv](https://mpv.io/) for playback. It doesn't open a video window, save audio files, or require a YouTube API key.

## What it does

- Searches by song, artist, or keywords and displays ranked video results with titles, channels, and durations when available.
- Starts playback at the result you pick and automatically advances through the rest of the queue.
- Lets you skip tracks, go back, pause, seek, and repeat the current track or the full queue.
- Opens with a color cassette-label signature, **YT Radio · written by manhunt07**.
- Shows a **Now Playing** card with the full title, channel, queue position, duration, and source URL. The card also shows the date, codec, sample rate, and channel count when mpv provides them.
- Animates the cassette reels independently of mpv's status refresh, only while playing. The reels freeze during pause, buffering, and seeking. Elapsed time and progress follow the actual playback position.

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

## Install YT Radio

YT Radio is a desktop terminal app. Choose the steps for your operating system. You don't need to install the app system-wide.

### 1. Get the project files

On the GitHub repository, click **Code → Download ZIP**, extract it, and open a terminal in the extracted folder. If you already have Git, copy the HTTPS URL from **Code**, then replace the example URL below:

~~~bash
git clone https://github.com/YOUR_USERNAME/yt-radio.git
cd yt-radio
~~~

Make sure your terminal is in the folder containing `yt-radio.py` and `requirements.txt`. If you downloaded the ZIP, the folder may be called `yt-radio-main`.

### 2. Install the system dependencies

#### Linux (Kali, Debian, Ubuntu)

~~~bash
sudo apt update
sudo apt install python3 python3-venv mpv
python3 --version
mpv --version
~~~

Install [Node.js LTS](https://nodejs.org/en/download) (22 or newer) or [Deno](https://docs.deno.com/runtime/getting_started/installation/) (2.3 or newer) if neither is already available. Check with `node --version` or `deno --version`. For other Linux distributions, use your package manager to install Python with venv support and an [mpv build](https://mpv.io/installation/) with the yt-dlp hook enabled.

#### macOS

Install [Homebrew](https://brew.sh/) if you don't have it, then run:

~~~bash
brew install python mpv node
python3 --version
mpv --version
node --version
~~~

If you already have supported Python and Node (or Deno), install only the missing packages. For older Macs without a compatible Homebrew build, see the [mpv installation page](https://mpv.io/installation/).

#### Windows (PowerShell)

1. Install [Python 3.11 or newer](https://www.python.org/downloads/windows/) with the Python launcher or install manager.
2. Install [Node.js LTS](https://nodejs.org/en/download) or [Deno](https://docs.deno.com/runtime/getting_started/installation/).
3. From the [mpv Windows builds](https://mpv.io/installation/#windows), pick a build for your processor that contains `mpv.exe` and `mpv.com`. Extract the full archive to a permanent folder. Search Windows for **Edit environment variables for your account**, edit your user **Path**, and add the folder containing the two files. Reopen PowerShell.

~~~powershell
py -3 --version
node --version
mpv.com --version
~~~

If you installed Deno, check `deno --version` instead. If `py` isn't available, use `python`. The player prefers `mpv.com` on Windows for terminal controls.

### 3. Install the Python dependency and launch

From the project folder, run the commands for your OS. They create an isolated `.venv` folder. You don't need to activate it or run these commands as administrator.

**Linux and macOS**

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python yt-radio.py "Sauti Sol Suzanna"
~~~

**Windows PowerShell**

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\yt-radio.py "Sauti Sol Suzanna"
~~~

If your Windows installation provides `python` but not `py`, use `python -m venv .venv` for the first line. Leave out the song name to get the interactive search prompt. On later runs, only the launch line is needed.

### Optional: run from any directory on Linux or macOS

From the project folder, install a user-level command without `sudo`:

~~~bash
python3 -m venv "$HOME/.local/share/yt-radio/venv"
"$HOME/.local/share/yt-radio/venv/bin/python" -m pip install -r requirements.txt
mkdir -p "$HOME/.local/bin"
install -m 0755 yt-radio.py "$HOME/.local/bin/yt-radio"
"$HOME/.local/bin/yt-radio" --help
~~~

If `$HOME/.local/bin` is on your `PATH`, you can type `yt-radio` directly. Otherwise, use the full path or add `export PATH="$HOME/.local/bin:$PATH"` to your shell startup file (for example, `~/.zshrc` for Zsh or `~/.bashrc` for Bash). Re-run the copy command after updating the script.

## Usage

These examples use the optional short command. If you skipped that step, pass the same arguments to the launch line for your OS in step 3.

```bash
yt-radio
yt-radio "Sauti Sol Suzanna"
yt-radio --limit 20 "Diamond Platnumz live"
yt-radio --plain "Sauti Sol Suzanna"
```

With no query, the app prompts you for one. Choose a number to start at that result. The default is 12 results, and `--limit` accepts 1–30. From the results menu, press **Enter** to search again or **q** to exit.

Use `--plain` for the original mpv status and a text-only signature. Set `NO_COLOR=1` to keep the cassette display but turn off the banner colors. The cassette status is compact in narrow terminals and disabled when the terminal is too narrow or player output is redirected.

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

- **Search works but playback fails.** Check that mpv and a supported JavaScript runtime are on your PATH, then try another result. Not every video exposes a playable audio-only stream.
- **YouTube extraction stopped working.** Update yt-dlp from the project folder:

  ~~~bash
  .venv/bin/python -m pip install --upgrade -r requirements.txt
  ~~~

  In Windows PowerShell, replace the Python path with `.\.venv\Scripts\python.exe`. If you installed the optional command, use `"$HOME/.local/share/yt-radio/venv/bin/python"` instead.
- **The command isn't found.** Use the launch line from step 3. The short `yt-radio` command requires the optional install and a matching `PATH` entry.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The tests mock search and playback, so they don't need YouTube access or a sound device. The included GitHub Actions workflow runs them on pushes and pull requests. These tests don't establish live streaming availability.

YT Radio is an independent project and is not affiliated with YouTube.
