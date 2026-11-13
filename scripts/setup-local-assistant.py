"""Install pinned public inference artifacts inside an existing project directory."""
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

MODEL_REVISION = "90862c4b9d2787eaed51d12237eafdfe7c5f6077"
ARTIFACTS = (
    ("llama-b12110-bin-ubuntu-x64.tar.gz", "https://github.com/ggml-org/llama.cpp/releases/download/b12110/llama-b12110-bin-ubuntu-x64.tar.gz",
     "368227edcc229be5f9bed16a2223d79b5e41d0ac2e19bcf5825e82291c060e55", 23051958),
    ("Qwen3-1.7B-Q8_0.gguf", f"https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/{MODEL_REVISION}/Qwen3-1.7B-Q8_0.gguf",
     "061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a", 1834426016),
)
CUDA_ENGINE = (
    "llama-b12110-bin-ubuntu-cuda-12.8-x64.tar.gz",
    "https://github.com/ggml-org/llama.cpp/releases/download/b12110/llama-b12110-bin-ubuntu-cuda-12.8-x64.tar.gz",
    "4af1e1da23661db4a5b84b29aae16ebc053df689c5b8b1427c4670f2c6406d8c", 187314621,
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--accelerator", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir() or not (root / ".runtime").is_dir():
        raise SystemExit("Use an existing approved project root with .runtime.")
    destination = root / ".runtime" / "assistant-model"
    destination.mkdir(parents=True, exist_ok=True)
    receipts = []
    artifacts = (CUDA_ENGINE, ARTIFACTS[1]) if args.accelerator == "cuda" else ARTIFACTS
    for filename, url, expected, size in artifacts:
        target = destination / filename
        if not (target.exists() and target.stat().st_size == size and digest(target) == expected):
            partial = target.with_suffix(target.suffix + ".part")
            request = urllib.request.Request(url, headers={"User-Agent": "ModuYuga-local-runtime/1.0"})
            print(f"Downloading {filename}", flush=True)
            with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, 1024 * 1024)
            if partial.stat().st_size != size or digest(partial) != expected:
                raise SystemExit(f"Artifact verification failed: {filename}; partial preserved.")
            partial.replace(target)
        receipts.append({"file": filename, "source": url, "sha256": expected, "bytes": size})
        print(f"Verified {filename}", flush=True)
    engine = destination / args.accelerator
    engine.mkdir(exist_ok=True)
    with tarfile.open(destination / artifacts[0][0]) as archive:
        archive.extractall(engine, filter="data")
    license_url = f"https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/{MODEL_REVISION}/LICENSE"
    with urllib.request.urlopen(license_url, timeout=30) as response:
        (destination / "MODEL-LICENSE").write_bytes(response.read())
    provenance = {
        "model": "Qwen/Qwen3-1.7B-GGUF", "revision": MODEL_REVISION, "license": "Apache-2.0",
        "engine": "ggml-org/llama.cpp", "engine_version": "b12110", "artifacts": receipts,
        "usage": "Local inference; public approved evidence; no hosted model API.",
        "accelerator": args.accelerator,
    }
    (destination / f"provenance-{args.accelerator}.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print("Pinned inference artifacts ready.", flush=True)


if __name__ == "__main__":
    main()
