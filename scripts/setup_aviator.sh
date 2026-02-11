#!/usr/bin/env bash
# Setup AVIATOR: uv sync, ESBMC, cppcheck, download PrimeVul (for RAG), index RAG.
# Run from AVIATOR repo root, or set AVIATOR_ROOT.
set -e

AVIATOR_ROOT="${AVIATOR_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="$AVIATOR_ROOT/data/PrimeVul_v0.1"

usage() {
  echo "Usage: $0 [--skip-esbmc] [--skip-cppcheck] [--skip-download]"
  echo "  --skip-esbmc      Do not install ESBMC"
  echo "  --skip-cppcheck   Do not install cppcheck"
  echo "  --skip-download   Do not download PrimeVul (use existing data in $DATA_DIR)"
  exit 0
}

SKIP_ESBMC=
SKIP_CPPCHECK=
SKIP_DOWNLOAD=

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-esbmc) SKIP_ESBMC=1; shift ;;
    --skip-cppcheck) SKIP_CPPCHECK=1; shift ;;
    --skip-download) SKIP_DOWNLOAD=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

cd "$AVIATOR_ROOT"
echo "=== AVIATOR root: $AVIATOR_ROOT ==="

echo "=== 1) uv sync ==="
uv sync

STATIC_TOOLS="$AVIATOR_ROOT/static_tools"
mkdir -p "$STATIC_TOOLS"

if [[ -z "$SKIP_ESBMC" ]]; then
  echo "=== 2) Install ESBMC into $STATIC_TOOLS/esbmc ==="
  wget -q https://github.com/esbmc/esbmc/releases/download/v7.5/ESBMC-Linux.zip -O "$STATIC_TOOLS/ESBMC-Linux.zip"
  unzip -o -d "$STATIC_TOOLS/esbmc" "$STATIC_TOOLS/ESBMC-Linux.zip" && rm -f "$STATIC_TOOLS/ESBMC-Linux.zip"
  # Zip typically extracts to esbmc/bin/esbmc
  if [[ -f "$STATIC_TOOLS/esbmc/bin/esbmc" ]]; then
    chmod +x "$STATIC_TOOLS/esbmc/bin/esbmc"
  else
    ESBMC_BIN=$(find "$STATIC_TOOLS" -name esbmc -type f 2>/dev/null | head -1)
    [[ -n "$ESBMC_BIN" ]] && chmod +x "$ESBMC_BIN"
  fi
else
  echo "=== 2) Skip ESBMC ==="
fi

if [[ -z "$SKIP_CPPCHECK" ]]; then
  echo "=== 3) Install cppcheck into $STATIC_TOOLS/cppcheck ==="
  mkdir -p "$STATIC_TOOLS/cppcheck"
  (cd "$STATIC_TOOLS/cppcheck" && git clone --depth 1 https://github.com/danmar/cppcheck.git 2>/dev/null || true)
  (cd "$STATIC_TOOLS/cppcheck/cppcheck" && make -j"$(nproc 2>/dev/null || echo 2)")
  mkdir -p "$STATIC_TOOLS/cppcheck/bin"
  cp "$STATIC_TOOLS/cppcheck/cppcheck/cppcheck" "$STATIC_TOOLS/cppcheck/bin/cppcheck"
  chmod +x "$STATIC_TOOLS/cppcheck/bin/cppcheck"
  "$STATIC_TOOLS/cppcheck/bin/cppcheck" --version
else
  echo "=== 3) Skip cppcheck ==="
fi

echo "=== 4) Install gdown ==="
if [[ -z "$SKIP_DOWNLOAD" ]]; then
  echo "=== 5) Download PrimeVul (6 *.jsonl files) to $DATA_DIR ==="
  mkdir -p "$DATA_DIR"

  if ! command -v gdown &> /dev/null; then
    echo "gdown is not installed. Installing now..."
    pip install gdown
    echo ""
  fi

  declare -A files=(
    ["1yv-lTCbcwRmmYFzkk6PSnJNpxR9KxA0z"]="primevul_test_paired.jsonl"
    ["1ABV5cIdtyNAzKlGxjW_BsFZOp9MFd-AH"]="primevul_test.jsonl"
    ["1yqMzbjB7Apo3E1lOmLbhQxvSkpS8r-hk"]="primevul_train_paired.jsonl"
    ["12b1QkCwW0SC6l9KvxSmMe4jHF7VhjwCa"]="primevul_train.jsonl"
    ["1aI7pGuMOgq3dn9w6g_QAv7cjDmWU1vKt"]="primevul_valid_paired.jsonl"
    ["1490USYtUtb5n3i3m3n2LaSfjTCiKhPoO"]="primevul_valid.jsonl"
  )

  for file_id in "${!files[@]}"; do
    filename="${files[$file_id]}"
    output_path="$DATA_DIR/$filename"
    echo "Downloading $filename..."
    gdown "https://drive.google.com/uc?id=$file_id" -O "$output_path" && echo "✓ $filename" || echo "✗ Failed $filename"
  done

  echo "Download complete. Files in $DATA_DIR:"
  ls -lh "$DATA_DIR"
else
  echo "=== 5) Skip download (using existing data dir) ==="
fi

PAIRED_PATH="$DATA_DIR/primevul_train_paired.jsonl"
if [[ ! -f "$PAIRED_PATH" ]]; then
  echo "Error: $PAIRED_PATH not found. Run without --skip-download or place primevul_train_paired.jsonl in $DATA_DIR" >&2
  exit 1
fi

echo "=== 6) Index RAG (primevul_train_paired.jsonl) ==="
uv run python vul_code_gen/index_knowledge_base.py --primevul_paired_path "$PAIRED_PATH"

echo "=== Setup complete ==="
