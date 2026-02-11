#!/usr/bin/env bash
# Run AVIATOR injection workflow and evaluate against ground truth.
# Run from AVIATOR repo root.
set -e

AVIATOR_ROOT="${AVIATOR_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
RUN_INJECTION="$AVIATOR_ROOT/scripts/run_injection.sh"

usage() {
  echo "Usage: $0 --dataset-path FILE [OPTIONS]"
  echo ""
  echo "Runs injection via run_injection.sh, then evaluate_generated_code.py."
  echo ""
  echo "Required:"
  echo "  --dataset-path FILE   Input dataset (e.g. primevul_test_paired.jsonl)"
  echo ""
  echo "Options:"
  echo "  --output-file FILE   Output JSONL (default: injected_vul_code/<input_basename>/aviator_injection.jsonl)"
  echo "  --workflow-json FILE Workflow config (default: vul_code_gen_workflow_noFT.json)"
  echo "  --percent N          Percentage of dataset to process (default: 100.0)"
  echo "  --dataset-type TYPE  primevul|sard100|formai (default: primevul)"
  echo "  --run-codebleu       Compute CodeBLEU (default: on)"
  echo "  --run-esbmc          Run ESBMC (sard100/formai only; ignored for primevul)"
  exit 0
}

DATASET_PATH=
OUTPUT_FILE=
WORKFLOW_JSON=
PERCENT=100.0
DATASET_TYPE=primevul
RUN_CODEBLEU=1
RUN_ESBMC=

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-path)   DATASET_PATH="$2"; shift 2 ;;
    --output-file)    OUTPUT_FILE="$2"; shift 2 ;;
    --workflow-json)  WORKFLOW_JSON="$2"; shift 2 ;;
    --percent)        PERCENT="$2"; shift 2 ;;
    --dataset-type)   DATASET_TYPE="$2"; shift 2 ;;
    --run-codebleu)   RUN_CODEBLEU=1; shift ;;
    --run-esbmc)      RUN_ESBMC=1; shift ;;
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

# Build args for run_injection
INJECTION_ARGS=(--dataset-path "$DATASET_PATH" --percent "$PERCENT" --dataset-type "$DATASET_TYPE")
[[ -n "$OUTPUT_FILE" ]] && INJECTION_ARGS+=(--output-file "$OUTPUT_FILE")
[[ -n "$WORKFLOW_JSON" ]] && INJECTION_ARGS+=(--workflow-json "$WORKFLOW_JSON")

# Run injection
"$RUN_INJECTION" "${INJECTION_ARGS[@]}"

# Compute output path for evaluation (same logic as run_injection)
if [[ -z "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE="$AVIATOR_ROOT/injected_vul_code/$DATA_NAME/aviator_injection.jsonl"
fi

# Run evaluation
cd "$AVIATOR_ROOT"
echo "=== Run evaluation ==="
EVAL_OPTS=(
  --reference_dataset_path "$DATASET_PATH"
  --data_to_test_path "$OUTPUT_FILE"
  --dataset_type "$DATASET_TYPE"
  --run_codebleu
)
[[ -n "$RUN_ESBMC" ]] && EVAL_OPTS+=(--run_esbmc)
uv run python vul_code_gen/evaluate_generated_code.py "${EVAL_OPTS[@]}"

echo "=== Done ==="
