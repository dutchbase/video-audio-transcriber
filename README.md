# video-audio-transcriber

A [Claude Code](https://claude.ai/code) skill that transcribes local video and audio files using [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) — entirely on-device, no uploads, no API keys.

Supports MP4, MKV, MOV, MP3, WAV, and more. Outputs `.txt`, `.srt`, `.vtt`, and `.json` for each file. Works on a single file or an entire folder.

---

## Features

- **100% local** — audio never leaves your machine
- **Batch transcription** — process a whole folder in one command
- **Clean Markdown output** — plain prose without timestamps by default; SRT/VTT/JSON available when needed
- **Auto-installs dependencies** — creates its own Python virtual environment on first use
- **Language detection** — auto-detect or specify a language code (`nl`, `en`, `de`, …)
- **WSL-aware** — works on Windows Subsystem for Linux with automatic path translation

## Supported models

| Model | Speed | Quality | Notes |
|-------|-------|---------|-------|
| `tiny` | Fastest | Low | Good for quick drafts |
| `base` | Fast | OK | — |
| `small` | Fast | Good | Recommended for speed |
| `medium` | Medium | Great | **Recommended default** |
| `large-v3` | Slow | Best | GPU recommended |

## Supported file types

`.mp4` `.m4v` `.mov` `.mkv` `.webm` `.avi` `.mp3` `.m4a` `.wav` `.aac` `.flac` `.ogg`

---

## Installation

### As a global Claude Code skill (available in all projects)

```bash
git clone https://github.com/dutchbase/video-audio-transcriber.git
cp -r video-audio-transcriber ~/.claude/skills/
```

### As a project-level skill

```bash
git clone https://github.com/dutchbase/video-audio-transcriber.git
cp -r video-audio-transcriber .claude/skills/
```

### From the zip

Download the release zip, extract it, and copy the `video-audio-transcriber/` folder into `~/.claude/skills/` or `.claude/skills/`.

---

## Usage in Claude Code

Once installed, just ask naturally:

```
Transcribe this video: /path/to/video.mp4
```

```
Get subtitles for all videos in ~/recordings
```

```
/video-audio-transcriber "/path/to/video.mp4" --model medium --markdown-only
```

Claude will pick up the skill automatically, translate paths if needed, and offer to summarize the transcript when it's done.

### WSL (Windows Subsystem for Linux)

Pass your Windows path directly — Claude translates it silently:

```
Transcribe C:\Users\you\Downloads\meeting.mp4
```

Output is written to `~/transcripts/` since `/mnt/c` is typically read-only for writes in WSL.

---

## Manual usage (without Claude)

```bash
# Check dependencies
python3 scripts/run_transcription.py --check

# Single file — markdown output, language auto-detected
python3 scripts/run_transcription.py "/path/to/video.mp4" --model medium --markdown-only

# Whole folder
python3 scripts/run_transcription.py "/path/to/folder" --model medium --markdown-only

# Recursive folder + custom output dir + explicit language
python3 scripts/run_transcription.py "/path/to/folder" \
  --model medium --markdown-only --language nl --recursive \
  --output "/path/to/transcripts"
```

On first run the script creates a `.venv` inside the skill folder and installs `faster-whisper`. If the skill folder is read-only (e.g. on WSL), point it elsewhere:

```bash
VIDEO_TRANSCRIBER_VENV="$HOME/.cache/video-audio-transcriber-venv" \
python3 scripts/run_transcription.py "/path/to/video.mp4" --model medium
```

### All options

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `medium` | `tiny`, `base`, `small`, `medium`, `large-v3`, or a local model path |
| `--language` | auto-detect | ISO language code: `nl`, `en`, `de`, `fr`, … |
| `--output` | `./transcripts` | Output directory |
| `--recursive` | off | Include subdirectories when input is a folder |
| `--formats` | all supported | Comma-separated extension allowlist, e.g. `.mp4,.mov` |
| `--device` | `auto` | `cpu`, `cuda`, or `auto` |
| `--compute-type` | `default` | `int8`, `float16`, `float32`, or `default` |
| `--beam-size` | `5` | Beam search width — lower is faster |
| `--no-vad` | off | Disable voice activity detection |
| `--markdown-only` | off | Write only `.md` (clean prose, no timestamps), skip all other formats |
| `--plain-text-only` | off | Write only `.txt` with timestamps, skip SRT/VTT/JSON |
| `--force` | off | Overwrite existing transcript files |
| `--check` | — | Check dependencies and exit |

---

## Output files

For each input file, the following are written to the output directory:

| File | Description |
|------|-------------|
| `<name>.txt` | Plain transcript with `[hh:mm:ss --> hh:mm:ss]` timestamps |
| `<name>.srt` | SubRip subtitle file |
| `<name>.vtt` | WebVTT subtitle file |
| `<name>.json` | Structured JSON with language, confidence, and per-segment data |
| `transcription-summary.json` | Batch summary (OK / skipped / failed counts) |

---

## Requirements

- Python 3.9 or later
- `python3-venv` (usually included; on Debian/Ubuntu: `sudo apt install python3-venv`)
- Internet access on first run to download the Whisper model (~500 MB for `medium`)
- A GPU is optional but speeds up `large-v3` significantly

---

## License

MIT
