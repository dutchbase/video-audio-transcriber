#!/usr/bin/env python3
"""Transcribe local media files with faster-whisper.

This script is designed to be called via run_transcription.py, which prepares
its virtual environment and dependencies first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable



def load_whisper_model_class():
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except Exception as exc:  # pragma: no cover - operational fallback
        print("ERROR: faster-whisper is not installed in this Python environment.", file=sys.stderr)
        print("Run the bundled bootstrapper first:", file=sys.stderr)
        print("  python3 scripts/run_transcription.py --check", file=sys.stderr)
        print(f"Original error: {exc}", file=sys.stderr)
        raise SystemExit(2)

DEFAULT_FORMATS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".flac",
    ".ogg",
}


@dataclass
class SegmentOut:
    id: int
    start: float
    end: float
    text: str


@dataclass
class FileResult:
    input: str
    status: str
    outputs: dict[str, str]
    error: str | None = None
    duration_seconds: float | None = None
    language: str | None = None
    language_probability: float | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe video/audio files to TXT, SRT, VTT, and JSON with faster-whisper.")
    parser.add_argument("input", help="Path to a media file or directory")
    parser.add_argument("--output", "-o", help="Output directory. Defaults to ./transcripts next to the input.")
    parser.add_argument("--model", default="medium", help="Whisper model name or local model path. Default: medium")
    parser.add_argument("--language", help="Language code, e.g. nl, en, de. Omit for auto-detect.")
    parser.add_argument("--recursive", action="store_true", help="Include subdirectories when input is a directory.")
    parser.add_argument("--formats", default=",".join(sorted(DEFAULT_FORMATS)), help="Comma-separated extension allowlist, e.g. .mp4,.mov,.mp3")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Inference device. Default: auto")
    parser.add_argument("--compute-type", default="default", help="CTranslate2 compute type, e.g. default, int8, float16, float32")
    parser.add_argument("--beam-size", type=int, default=5, help="Beam size. Default: 5")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD filtering")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs if they already exist")
    parser.add_argument("--plain-text-only", action="store_true", help="Only create .txt output")
    parser.add_argument("--markdown-only", action="store_true", help="Write a clean .md transcript without timestamps, skip all other formats")
    return parser.parse_args(argv)


def normalize_formats(value: str) -> set[str]:
    formats: set[str] = set()
    for part in value.split(","):
        ext = part.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        formats.add(ext)
    return formats or DEFAULT_FORMATS


def collect_files(input_path: Path, formats: set[str], recursive: bool) -> list[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if input_path.is_file():
        if input_path.suffix.lower() not in formats:
            raise ValueError(f"Unsupported extension: {input_path.suffix}. Allowed: {', '.join(sorted(formats))}")
        return [input_path]

    if not input_path.is_dir():
        raise ValueError(f"Input is neither a file nor a directory: {input_path}")

    iterator = input_path.rglob("*") if recursive else input_path.iterdir()
    files = [p for p in iterator if p.is_file() and p.suffix.lower() in formats]
    return sorted(files, key=lambda p: str(p).lower())


def default_output_dir(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path / "transcripts"
    return input_path.parent / "transcripts"


def safe_stem_for(file_path: Path, all_files: list[Path]) -> str:
    stem = sanitize_stem(file_path.stem)
    count_same_stem = sum(1 for item in all_files if sanitize_stem(item.stem) == stem)
    if count_same_stem <= 1:
        return stem
    digest = hashlib.sha1(str(file_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


def sanitize_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value.strip())
    return cleaned or "transcript"


def seconds_to_srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def seconds_to_vtt_time(seconds: float) -> str:
    return seconds_to_srt_time(seconds).replace(",", ".")


def write_txt(path: Path, segments: list[SegmentOut]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for seg in segments:
            f.write(f"[{seconds_to_vtt_time(seg.start)} --> {seconds_to_vtt_time(seg.end)}] {seg.text.strip()}\n")


def write_srt(path: Path, segments: list[SegmentOut]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for idx, seg in enumerate(segments, start=1):
            f.write(f"{idx}\n")
            f.write(f"{seconds_to_srt_time(seg.start)} --> {seconds_to_srt_time(seg.end)}\n")
            f.write(seg.text.strip() + "\n\n")


def write_vtt(path: Path, segments: list[SegmentOut]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            f.write(f"{seconds_to_vtt_time(seg.start)} --> {seconds_to_vtt_time(seg.end)}\n")
            f.write(seg.text.strip() + "\n\n")


def write_json(path: Path, *, source: Path, model: str, info: object, segments: list[SegmentOut]) -> None:
    payload = {
        "source": str(source),
        "model": model,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "segments": [asdict(seg) for seg in segments],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_markdown(path: Path, segments: list[SegmentOut]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        paragraph: list[str] = []
        prev_end = 0.0
        for seg in segments:
            if paragraph and seg.start - prev_end > 3.0:
                f.write(" ".join(paragraph) + "\n\n")
                paragraph = []
            paragraph.append(seg.text.strip())
            prev_end = seg.end
        if paragraph:
            f.write(" ".join(paragraph) + "\n")


def expected_outputs(output_dir: Path, stem: str, plain_text_only: bool, markdown_only: bool = False) -> dict[str, Path]:
    if markdown_only:
        return {"md": output_dir / f"{stem}.md"}
    outputs = {"txt": output_dir / f"{stem}.txt"}
    if not plain_text_only:
        outputs.update(
            {
                "srt": output_dir / f"{stem}.srt",
                "vtt": output_dir / f"{stem}.vtt",
                "json": output_dir / f"{stem}.json",
            }
        )
    return outputs


def transcribe_one(
    model,
    file_path: Path,
    output_dir: Path,
    stem: str,
    args: argparse.Namespace,
) -> FileResult:
    outputs = expected_outputs(output_dir, stem, args.plain_text_only, getattr(args, "markdown_only", False))
    if not args.force and all(path.exists() for path in outputs.values()):
        return FileResult(
            input=str(file_path),
            status="skipped_exists",
            outputs={key: str(path) for key, path in outputs.items()},
        )

    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        segments_iter, info = model.transcribe(
            str(file_path),
            language=args.language,
            beam_size=args.beam_size,
            vad_filter=not args.no_vad,
        )
        segments = [SegmentOut(id=i, start=s.start, end=s.end, text=s.text.strip()) for i, s in enumerate(segments_iter)]

        if getattr(args, "markdown_only", False):
            write_markdown(outputs["md"], segments)
        else:
            write_txt(outputs["txt"], segments)
            if not args.plain_text_only:
                write_srt(outputs["srt"], segments)
                write_vtt(outputs["vtt"], segments)
                write_json(outputs["json"], source=file_path, model=args.model, info=info, segments=segments)

        elapsed = time.time() - start_time
        return FileResult(
            input=str(file_path),
            status="ok",
            outputs={key: str(path) for key, path in outputs.items()},
            duration_seconds=round(elapsed, 2),
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
        )
    except Exception as exc:
        return FileResult(
            input=str(file_path),
            status="failed",
            outputs={key: str(path) for key, path in outputs.items()},
            error=str(exc),
        )


def print_result(result: FileResult) -> None:
    print(f"\n[{result.status}] {result.input}")
    if result.language:
        prob = "" if result.language_probability is None else f" ({result.language_probability:.2%})"
        print(f"  language: {result.language}{prob}")
    if result.duration_seconds is not None:
        print(f"  elapsed: {result.duration_seconds}s")
    if result.error:
        print(f"  error: {result.error}")
    for kind, path in result.outputs.items():
        print(f"  {kind}: {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    formats = normalize_formats(args.formats)

    try:
        files = collect_files(input_path, formats, args.recursive)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not files:
        print(f"No supported media files found in: {input_path}")
        print(f"Allowed extensions: {', '.join(sorted(formats))}")
        return 1

    output_dir = Path(args.output).expanduser().resolve() if args.output else default_output_dir(input_path).resolve()

    print("Video Audio Transcriber")
    print(f"Input: {input_path}")
    print(f"Files: {len(files)}")
    print(f"Output: {output_dir}")
    print(f"Model: {args.model}")
    print(f"Language: {args.language or 'auto-detect'}")
    print(f"Device: {args.device}")
    print(f"Compute type: {args.compute_type}")

    WhisperModel = load_whisper_model_class()

    try:
        model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    except Exception as exc:
        print(f"ERROR: Could not load model '{args.model}': {exc}", file=sys.stderr)
        print("If this is the first run, internet access may be needed to download the model.", file=sys.stderr)
        print("Alternatively, pass --model /path/to/local/model.", file=sys.stderr)
        return 2

    results: list[FileResult] = []
    for index, file_path in enumerate(files, start=1):
        print(f"\n=== {index}/{len(files)}: {file_path} ===")
        stem = safe_stem_for(file_path, files)
        result = transcribe_one(model, file_path, output_dir, stem, args)
        results.append(result)
        print_result(result)

    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status.startswith("skipped"))
    failed = sum(1 for r in results if r.status == "failed")

    summary = {
        "input": str(input_path),
        "output": str(output_dir),
        "model": args.model,
        "language": args.language,
        "total": len(results),
        "ok": ok,
        "skipped": skipped,
        "failed": failed,
        "results": [asdict(r) for r in results],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "transcription-summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== Summary ===")
    print(f"OK: {ok}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Summary JSON: {summary_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
