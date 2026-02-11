# AVIATOR: Towards AI-Agentic Vulnerability Injection Workflow

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## What is AVIATOR?

**AVIATOR** is an AI-agentic framework for **automated vulnerability injection** in source code. It produces high-fidelity, large-scale code security datasets by orchestrating specialized AI agents, RAG, and tool-based analysis in a multi-step workflow.

---

## Installation

**Prerequisites:** Python ≥ 3.11, [uv](https://github.com/astral-sh/uv)

From the repository root:

```bash
git clone https://github.com/your-username/aviator.git
cd AVIATOR/
./scripts/setup_aviator.sh
```

Options:
- `--skip-esbmc` — Do not install ESBMC
- `--skip-cppcheck` — Do not install Cppcheck
- `--skip-download` — Do not download PrimeVul (use existing data in `./data/PrimeVul_v0.1`)

---

## LLM Configuration

Configure your LLM in the **workflow JSON file** (e.g. `vul_code_gen/AVIATOR_13steps_full_workflow/vul_code_gen_workflow_noFT.json`). The `llms` section defines the models used by the workflow.

### Option 1: Model providers (OpenAI-compatible API)

Use any hosted API (OpenAI, Together, Groq, etc.) or a **local model served via vLLM**.

For hosted APIs or vLLM, set `base_url` and `api_key` in the workflow JSON:

```json
"llm": {
    "type": "OpenAICompatibleLLM",
    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "base_url": "host-url",
    "api_key": "your-api-key"
}
```

**Local models:** We strongly recommend using **vLLM** to run models locally. Example for Qwen2.5-Coder:

```bash
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 18446 --dtype bfloat16 --tensor-parallel-size 2 --max_model_len 32000 --disable-log-requests
```

Then set `base_url` to `http://localhost:18446/v1` (or your host:port) in the workflow JSON.

### Option 2: Hugging Face Transformers pipeline

Run a model directly via the Hugging Face Transformers API (no separate server). This loads the model in-process:

```json
"llm": {
    "type": "HFpipeline",
    "llm_path": "Qwen/Qwen2.5-Coder-32B-Instruct"
}
```

---

## Usage

### Run vulnerability injection

```bash
./scripts/run_injection.sh --dataset-path /path/to/primevul_test.jsonl
```

### Run injection with evaluation

`run_injection_with_eval.sh` runs the injection workflow, then evaluates the generated code against a reference dataset (ground truth):

- **CodeBLEU:** Measures syntactic and lexical similarity between generated and reference vulnerable code.
- **ESBMC** (optional, sard100/formai): Bounded model checking to verify the injected vulnerability is actually exploitable.

```bash
./scripts/run_injection_with_eval.sh --dataset-path validation_dataset/formai_with_benign_37.jsonl
```

---

## CWE selector (beta)

The **14-steps CWE selector** workflow (`vul_code_gen/AVIATOR_14steps_CWEselector/`) adds an extra step to automatically find a suitable vulnerability type (CWE) to inject when your dataset does not include a pre-defined target CWE per example. This is useful for datasets that contain only benign code (e.g. FormAI), where you want the workflow to choose which vulnerability to inject.

**CWE selection modes:**

- **Weighted random selection** (`vulnInjectID_selector_probabilistic`): Samples a CWE using weights from `vulnerability_probabilities.json`. Runs as a single all-in-one workflow.

- **Agentic selection** (`vulnInjectID_selector`): An LLM analyzes the benign code and selects a contextually suitable CWE. Uses a two-step pipeline: first select CWEs, then run injection.

**Weighted random selection**

Single workflow — CWE selection and injection in one run:

```bash
./scripts/run_injection.sh --dataset-path /path/to/benign_only.jsonl \
  --workflow-json vul_code_gen/AVIATOR_14steps_CWEselector/vul_code_gen_workflow_noFT_CWEselector_random.json
```

**Agentic selection**

Two-step pipeline — first obtain CWEs via AI analysis, then run injection:

```bash
# Step 1: Select CWEs (AI agent analyzes code and picks suitable vulnerability types)
./scripts/run_injection.sh --dataset-path /path/to/benign_only.jsonl \
  --workflow-json vul_code_gen/AVIATOR_14steps_CWEselector/vul_code_gen_workflow_noFT_before_CWEselector.json \
  --output-file /path/to/with_cwe_ids.jsonl

# Step 2: Run injection using the CWE-enriched output from step 1
./scripts/run_injection.sh --dataset-path /path/to/with_cwe_ids.jsonl \
  --workflow-json vul_code_gen/AVIATOR_14steps_CWEselector/vul_code_gen_workflow_noFT_after_CWEselector.json
```

The intermediate output from step 1 must include `benign_code`, `vul_inject_id`, `function_purpose`, and the other fields expected by the *after* workflow. You may need to adapt the runner or use a custom script to capture and pass this intermediate output.

> **Beta disclaimer:** The CWE selector is in beta. Results are less robust than the regular 13-steps workflow where the target CWE is provided in the input dataset (e.g. PrimeVul). Use it for exploratory runs or when CWE labels are not available.

---

## Script Arguments

### `./scripts/run_injection.sh`

| Argument | Required | Description |
|----------|----------|-------------|
| `--dataset-path` | **Yes** | Input dataset (JSONL) |
| `--output-file` | No | Output JSONL (default: `injected_vul_code/<input_basename>/aviator_injection.jsonl`) |
| `--workflow-json` | No | Workflow config (default: `vul_code_gen_workflow_noFT.json`) |
| `--percent` | No | Percentage of dataset to process (default: 100.0) |
| `--dataset-type` | No | `primevul`, `sard100`, or `formai` (default: `primevul`) |

### `./scripts/run_injection_with_eval.sh`

| Argument | Required | Description |
|----------|----------|-------------|
| `--dataset-path` | **Yes** | Input dataset (JSONL) |
| `--output-file` | No | Output JSONL |
| `--workflow-json` | No | Workflow config |
| `--percent` | No | Percentage of dataset (default: 100.0) |
| `--dataset-type` | No | `primevul`, `sard100`, or `formai` (default: `primevul`) |
| `--run-codebleu` | No | Compute CodeBLEU (default: on) |
| `--run-esbmc` | No | Run ESBMC (sard100/formai only) |

### `run_AVIATOR.py` (direct Python)

| Argument | Required | Description |
|----------|----------|-------------|
| `--dataset_path` | **Yes** | Path to dataset file |
| `--workflow_json` | **Yes** | Path to workflow JSON |
| `--output_file` | **Yes** | Output JSONL path |
| `--percent` | No | Percentage to process (default: 100.0) |
| `--dataset_type` | No | `primevul`, `sard100`, or `formai` (default: `primevul`) |

### `evaluate_generated_code.py`

| Argument | Required | Description |
|----------|----------|-------------|
| `--data_to_test_path` | **Yes** | Path to generated/injected code (JSONL) |
| `--reference_dataset_path` | **Yes** | Path to reference ground truth |
| `--dataset_type` | **Yes** | `primevul`, `sard100`, or `formai` |
| `--run_codebleu` | No | Compute CodeBLEU |
| `--run_esbmc` | No | Run ESBMC (sard100/formai only) |

### `index_knowledge_base.py`

| Argument | Required | Description |
|----------|----------|-------------|
| `--primevul_paired_path` | **Yes** | Path to `primevul_train_paired.jsonl` |

---

## Repository Structure

| Directory | Description |
|-----------|-------------|
| **awe** | Low-code library for AI agentic workflows |
| **LoRA_FT** | Fine-tuning code (SFT, GRPO, LoRA) |
| **vul_code_gen** | Injection workflow, agents, RAG, scripts |
| **vul_code_gen/AVIATOR_14steps_CWEselector** | Beta CWE-selector workflow (auto-selects vulnerability type) |
| **validation_dataset** | Benchmark data links |
| **scripts/** | Setup and run scripts |

---

## Datasets

- **PrimeVul** (training and RAG): [Google Drive](https://drive.google.com/drive/folders/1cznxGme5o6A_9tT8T47JUh3MPEpRYiKK) — downloaded by setup to `./data/PrimeVul_v0.1`
- **FormAI**: [FormAI Dataset](https://github.com/FormAI-Dataset)
- **SARD100**: [SARD](https://samate.nist.gov/SARD/test-suites/100)

---

## Dependencies

Core dependencies (via `uv sync`): **unsloth**, **pydantic**, **langchain**, **ChromaDB**, **codebleu**, **tree-sitter-cpp**, **openai**, **PyTorch**, **Transformers**. See `pyproject.toml` and `requirements.txt`.

---

## Abstract

The increasing complexity of software systems and the sophistication of cyber-attacks have underscored the critical need for reliable automated software vulnerability detection. Data-driven approaches using deep learning models show promise but critically depend on the availability of large, accurately labeled datasets. Automated vulnerability injection provides a way to address these limitations, but existing techniques remain limited in coverage, contextual fidelity, or injection success.

**AVIATOR** is the first AI-agentic vulnerability injection framework. It decomposes vulnerability injection into a coordinated workflow of specialized AI agents, tool-based analysis, and iterative self-correction, with RAG and LoRA-based fine-tuning to produce realistic, category-specific vulnerabilities.

---

## How to cite

```bibtex
@inproceedings{aviator2025,
  title     = {AVIATOR: Towards AI-Agentic Vulnerability Injection Workflow for High-Fidelity, Large-Scale Code Security Dataset},
  author    = { ... },
  booktitle = { ... },
  year      = {2025},
}
```

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Disclaimer

NIST-developed software is provided by NIST as a public service. You may use, copy and distribute copies of the software in any medium, provided that you keep intact this entire notice. This software is expressly provided "AS IS." NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT OR ARISING BY OPERATION OF LAW. You are solely responsible for determining the appropriateness of using and distributing the software.
