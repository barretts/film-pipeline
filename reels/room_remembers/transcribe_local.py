"""Transcribe local speech on CPU with word timestamps; no cloud service."""
import argparse
import json
from pathlib import Path

import whisper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--model", default="base.en")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    model = whisper.load_model(args.model, device="cpu", download_root=str(args.model_dir))
    for audio in args.audio:
        result = model.transcribe(str(audio), language="en", word_timestamps=True,
                                  fp16=False, temperature=0, verbose=False)
        words = [word for segment in result["segments"] for word in segment.get("words", [])]
        destination = args.out_dir / (audio.stem + ".json")
        destination.write_text(json.dumps({"audio": str(audio), "text": result["text"], "words": words},
                                          indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Transcribed {audio} -> {destination}: {result['text'].strip()}", flush=True)


if __name__ == "__main__":
    main()
