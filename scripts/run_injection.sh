#!/usr/bin/env bash
# Run AVIATOR vulnerability injection workflow on a dataset.
# Run from AVIATOR repo root.
set -e

AVIATOR_ROOT="${AVIATOR_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKFLOW_JSON_DEFAULT="$AVIATOR_ROOT/vul_code_gen/AVIATOR_13steps_full_workflow/vul_code_gen_workflow_noFT.json"

usage() {
  echo "Usage: $0 --dataset-path FILE [OPTIONS]"
  echo ""
  echo "Required:"
  echo "  --dataset-path FILE   Input dataset (e.g. primevul_test_paired.jsonl)"
  echo ""
  echo "Options:"
  echo "  --output-file FILE   Output JSONL (default: injected_vul_code/<input_basename>/aviator_injection.jsonl)"
  echo "  --workflow-json FILE Workflow config (default: vul_code_gen_workflow_noFT.json)"
  echo "  --percent N          Percentage of dataset to process (default: 100.0)"
  echo "  --dataset-type TYPE  primevul|sard100|formai (default: primevul)"
  exit 0
}

DATASET_PATH=
OUTPUT_FILE=
WORKFLOW_JSON="$WORKFLOW_JSON_DEFAULT"
PERCENT=100.0
DATASET_TYPE=primevul

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-path)   DATASET_PATH="$2"; shift 2 ;;
    --output-file)    OUTPUT_FILE="$2"; shift 2 ;;
    --workflow-json)  WORKFLOW_JSON="$2"; shift 2 ;;
    --percent)        PERCENT="$2"; shift 2 ;;
    --dataset-type)   DATASET_TYPE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ -z "$DATASET_PATH" ]]; then
  echo "Error: --dataset-path is required." >&2
  usage
fi

DATA_NAME=$(basename "$DATASET_PATH" .jsonl)
LOG_FILE="$AVIATOR_ROOT/injected_vul_code/$DATA_NAME/run.log"
mkdir -p "$AVIATOR_ROOT/injected_vul_code/$DATA_NAME"
exec > >(tee "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"

# Default output: injected_vul_code/<data_name>/aviator_injection.jsonl
if [[ -z "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE="$AVIATOR_ROOT/injected_vul_code/$DATA_NAME/aviator_injection.jsonl"
  echo "Output file (default): $OUTPUT_FILE"
fi

cd "$AVIATOR_ROOT"

echo "=== Run workflow ==="
uv run python vul_code_gen/run_AVIATOR.py \
  --dataset_path "$DATASET_PATH" \
  --workflow_json "$WORKFLOW_JSON" \
  --output_file "$OUTPUT_FILE" \
  --percent "$PERCENT" \
  --dataset_type "$DATASET_TYPE"

echo "=== Done ==="
