---
name: video-audio-transcriber
description: Transcribe audio from local video or audio files using local faster-whisper — no cloud, no uploads. Use this skill whenever the user wants to transcribe, caption, subtitle, or convert speech-to-text from a local file or folder, even if they phrase it casually ("transcribe this video", "get subtitles for", "turn the audio into text", "what does this video say", "can you read what's said in"). Works with MP4, MP3, WAV, MKV, MOV, and more. Batch-transcribes entire folders. Outputs TXT, SRT, VTT, and JSON. After transcription, offer to read and summarize the result.
argument-hint: "<file-or-folder-path> [--language nl] [--model medium] [--recursive]"
---

# Video Audio Transcriber

Use this skill whenever the user wants to turn a local video or audio file into text — whether they call it transcription, captions, subtitles, or speech-to-text.

The bundled runner uses local `faster-whisper`. It auto-creates a Python venv, installs dependencies if needed, and writes `.txt`, `.srt`, `.vtt`, and `.json` for each file.

## Important runtime notes

- **WSL — path translation**: Windows paths like `C:\Users\dutch\Downloads\video.mp4` must be silently translated to `/mnt/c/Users/dutch/Downloads/video.mp4` before passing to the script.
- **WSL — output dir**: `/mnt/c/...` is typically read-only for writes. Always use `--output "$HOME/transcripts"` (or another Linux path) so the transcript files land somewhere writable.
- **WSL — venv**: The skills directory is read-only. Always set `VIDEO_TRANSCRIBER_VENV="$HOME/.cache/video-audio-transcriber-venv"` when invoking the runner.
- **WSL — SOCKS proxy**: If the model download fails with a `socksio` error, run: `$HOME/.cache/video-audio-transcriber-venv/bin/pip install "httpx[socks]"` once, then retry.
- **Claude.ai / Desktop**: Only works if the execution environment can see the path. If not, ask the user to use Claude Code locally.
- Never delete, overwrite, move, or modify original media files.

## Supported inputs

`.mp4`, `.m4v`, `.mov`, `.mkv`, `.webm`, `.avi`, `.mp3`, `.m4a`, `.wav`, `.aac`, `.flac`, `.ogg`

## Transcription workflow

1. Resolve the path. For WSL, translate Windows paths silently.
2. Choose sensible defaults:
   - `--language nl` when the user is Dutch or speaks Dutch (and hasn't specified otherwise).
   - `--model medium` for Dutch quality.
   - `--model small` when the user asks for speed or on CPU-only hardware.
   - `--model large-v3` when the user asks for maximum quality, or when accuracy is critical (e.g. legal, medical). Needs a GPU.
3. Single file → transcribe it. Directory → process all supported files in sorted order.
4. Use `--recursive` only when the user mentions subfolders.
5. Output goes to a `transcripts` folder next to the input unless `--output` is specified.
6. After transcription succeeds, offer to read the `.txt` and summarize or answer questions about the content.

## Commands

Single file (WSL):
```bash
VIDEO_TRANSCRIBER_VENV="$HOME/.cache/video-audio-transcriber-venv" \
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/mnt/c/Users/dutch/Downloads/video.mp4" \
  --language nl \
  --model medium \
  --output "$HOME/transcripts"
```

Single file (non-WSL):
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/path/to/video.mp4" \
  --language nl \
  --model medium
```

Directory (non-recursive):
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/path/to/folder" \
  --language nl \
  --model medium
```

Directory (recursive):
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/path/to/folder" \
  --language nl \
  --model medium \
  --recursive
```

Custom output folder:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/path/to/video.mp4" \
  --language nl \
  --model medium \
  --output "/path/to/transcripts"
```

Force regeneration of existing transcripts:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/run_transcription.py" \
  "/path/to/video.mp4" \
  --force
```

## Useful options

| Flag | Effect |
|------|--------|
| `--model tiny\|base\|small\|medium\|large-v3` | Quality vs speed. Default: `medium` |
| `--language <code>` | ISO code (`nl`, `en`, `de`, `fr`…). Omit for auto-detect |
| `--recursive` | Include subdirectories in folder mode |
| `--output <path>` | Write outputs to a specific folder |
| `--formats .mp4,.mov,.mp3` | Override which extensions to process |
| `--device cpu\|cuda\|auto` | Inference device. Default: `auto` |
| `--compute-type int8\|float16\|float32\|default` | CTranslate2 precision |
| `--beam-size <n>` | Beam search width. Default: 5. Lower = faster |
| `--no-vad` | Disable voice activity detection |
| `--plain-text-only` | Write only `.txt`, skip SRT/VTT/JSON |
| `--force` | Overwrite existing transcript files |
| `--check` | Check dependencies only, no transcription |

## Output files

Each input file produces (unless `--plain-text-only`):
- `<stem>.txt` — readable transcript with timestamps
- `<stem>.srt` — subtitle file for video editors
- `<stem>.vtt` — web subtitle format
- `<stem>.json` — structured segments with metadata

A `transcription-summary.json` is also written to the output directory.

## Dependencies

The runner auto-creates a `.venv` inside the skill folder and installs `faster-whisper` on first use. No manual setup needed. If `python3` is missing:

**WSL / Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

**macOS:**
```bash
brew install python
```

If automatic install is blocked, run manually:
```bash
cd "${CLAUDE_SKILL_DIR}"
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip && pip install "faster-whisper>=1.1.0"
```

## Failure handling

- Continue with the next file if one fails; report a summary at the end.
- If the model download fails, explain that internet access is needed on first use (or pass a local model path with `--model /path/to/model`).
