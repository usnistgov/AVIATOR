# AVIATOR: Towards AI-Agentic Vulnerability Injection Workflow

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Table of contents

- [What is AVIATOR?](#what-is-aviator)
- [Installation](#installation)
  - [1. Docker (recommended)](#1-docker-recommended)
  - [2. Scripts (manual)](#2-scripts-manual)
- [LLM Configuration](#llm-configuration)
  - [1. .env file (Docker)](#1-env-file-docker)
  - [2. Workflow JSON (manual)](#2-workflow-json-manual)
- [Usage](#usage)
  - [1. With Docker](#1-with-docker)
  - [2. With scripts (manual)](#2-with-scripts-native)
- [CWE selector (beta)](#cwe-selector-beta)
- [Script Arguments](#script-arguments)
- [Repository Structure](#repository-structure)
- [Datasets](#datasets)
- [Downstream Vulnerability Detection](#downstream-vulnerability-detection)
- [Abstract](#abstract)
- [How to cite](#how-to-cite)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## What is AVIATOR?

**AVIATOR** is an AI-agentic framework for **automated vulnerability injection** in source code. It produces high-fidelity, large-scale code security datasets by orchestrating specialized AI agents, RAG, and tool-based analysis in a multi-step workflow.

---

## Installation

### 1. Docker (recommended)

Reproducible runs with no local Python setup. The image includes Python dependencies, ESBMC, cppcheck, PrimeVul data, and the RAG index.

**Prerequisites:** Docker, Docker Compose

```bash
docker compose build
```

Configure the LLM via `.env` before running; see [LLM Configuration → 1. .env file](#1-env-file-docker).

For a lean image without PrimeVul baked in: `docker compose build --build-arg SKIP_PRIMEVUL_DOWNLOAD=1`, then mount `./data` at runtime.

---

### 2. Scripts (manual)

**Prerequisites:** Python ≥ 3.11, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/your-username/aviator.git
cd AVIATOR/
./scripts/setup_aviator.sh
```

Options: `--skip-esbmc`, `--skip-cppcheck`, `--skip-download` (use existing data in `./data/PrimeVul_v0.1`).

---

## LLM Configuration

### 1. .env file (Docker)

Copy `.env.example` to `.env` and set values. Docker Compose loads them automatically. No JSON edits needed.

<table style="border-collapse: collapse;">
<tr><th style="border: 1px solid;">Model source</th><th style="border: 1px solid;">Variable</th><th style="border: 1px solid;">Description</th></tr>
<tr>
<td rowspan="3" style="vertical-align: middle; border: 1px solid;">OpenAI-compatible API (option 1)</td>
<td style="border: 1px solid;"><code>AVIATOR_LLM_BASE_URL</code></td>
<td style="border: 1px solid;">API base URL</td>
</tr>
<tr>
<td style="border: 1px solid;"><code>AVIATOR_LLM_API_KEY</code></td>
<td style="border: 1px solid;">API key</td>
</tr>
<tr>
<td style="border: 1px solid;"><code>AVIATOR_LLM_MODEL</code></td>
<td style="border: 1px solid;">Model name</td>
</tr>
<tr>
<td style="border: 1px solid;">HuggingFace (option 2)</td>
<td style="border: 1px solid;"><code>AVIATOR_LLM_PATH</code></td>
<td style="border: 1px solid;">Model path for in-process HuggingFace model</td>
</tr>
<tr>
<td style="border: 1px solid;">Fine-tuned model (optional)</td>
<td style="border: 1px solid;"><code>AVIATOR_LLM_FINETUNED_PATH</code></td>
<td style="border: 1px solid;">LoRA adapter path (FT workflow <code>vul_inject_SFT</code> agent)</td>
</tr>
</table>

Per-LLM: `AVIATOR_LLM_<ID>_*` (e.g. `AVIATOR_LLM_MAIN_LLM_BASE_URL`, `AVIATOR_LLM_VUL_INJECT_SFT_PATH`).

---

### 2. Workflow JSON (manual)

Edit workflow JSON files in the codebase directly (e.g. `vul_code_gen/AVIATOR_13steps_full_workflow/vul_code_gen_workflow_noFT.json`).

#### Option 1. Model providers (OpenAI-compatible API)

Use any hosted API (OpenAI, Together, Groq, etc.) or a **local model served via vLLM**:

```json
"llm": {
    "type": "OpenAICompatibleLLM",
    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "base_url": "host-url",
    "api_key": "your-api-key"
}
```

Example for local vLLM:

```bash
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 18446 --dtype bfloat16 --tensor-parallel-size 2 --max_model_len 32000 --disable-log-requests
```

Set `base_url` to `http://localhost:18446/v1` in the workflow JSON.

#### Option 2. Hugging Face Transformers pipeline

Run a model in-process (no separate server):

```json
"llm": {
    "type": "HFpipeline",
    "llm_path": "Qwen/Qwen2.5-Coder-32B-Instruct"
}
```

#### Optional: Fine-tuned model (FT workflow)

For the FT workflow, set `llm_path` in the `vul_inject_SFT` LLM section to your LoRA adapter output (e.g. `outputs` or `Qwen2.5-coder-GRPO/full_GRPO`). See [LoRA_FT/README.md](LoRA_FT/README.md).

---

## Usage

### 1. With Docker

Run injection:

```bash
# Quick test (45 samples, always available):
docker compose run aviator scripts/run_injection.sh \
  --dataset-path validation_dataset/primevul_paired_test_45.jsonl

# Full PrimeVul test (requires data/ in image):
docker compose run aviator scripts/run_injection.sh \
  --dataset-path /AVIATOR/data/PrimeVul_v0.1/primevul_test.jsonl
```

Run injection with evaluation (FormAI, SARD100 with CodeBLEU and optional ESBMC):

```bash
docker compose run aviator scripts/run_injection_with_eval.sh \
  --dataset-path validation_dataset/formai_with_benign_37.jsonl --run-esbmc
```

---

### 2. With scripts (manual)

Run vulnerability injection:

```bash
./scripts/run_injection.sh --dataset-path /path/to/primevul_test.jsonl
```

Run injection with evaluation (CodeBLEU; optional ESBMC for sard100/formai):

```bash
./scripts/run_injection_with_eval.sh --dataset-path validation_dataset/formai_with_benign_37.jsonl --run-esbmc
```

---

## CWE selector (beta)

The **14-steps CWE selector** workflow (`vul_code_gen/AVIATOR_14steps_CWEselector/`) adds an extra step to automatically find a suitable vulnerability type (CWE) to inject when your dataset does not include a pre-defined target CWE per example. This is useful for datasets that contain only benign code (e.g. FormAI), where you want the workflow to choose which vulnerability to inject.

**CWE selection modes:**

- **Weighted random selection** (`vulnInjectID_selector_probabilistic`): Samples a CWE using weights from `vulnerability_probabilities.json`. Runs as a single all-in-one workflow.

- **Agentic selection** (`vulnInjectID_selector`): An LLM analyzes the benign code and selects a contextually suitable CWE. Uses a two-step pipeline: first select CWEs, then run injection.

#### Weighted random selection

Single workflow — CWE selection and injection in one run:

```bash
./scripts/run_injection.sh --dataset-path /path/to/benign_only.jsonl \
  --workflow-json vul_code_gen/AVIATOR_14steps_CWEselector/vul_code_gen_workflow_noFT_CWEselector_random.json
```

#### Agentic selection

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

## Downstream Vulnerability Detection

For the experiments evaluating impact on downstream vulnerability detection, we used [VulScribeR](https://github.com/shayandaneshvar/VulScribeR/tree/main), the official repository for the paper *VulScribeR: Exploring RAG-based Vulnerability Augmentation with LLMs*.



---

## Abstract

The increasing complexity of software systems and the sophistication of cyber-attacks have underscored the critical need for reliable automated software vulnerability detection. Data-driven approaches using deep learning models show promise but critically depend on the availability of large, accurately labeled datasets. Automated vulnerability injection provides a way to address these limitations, but existing techniques remain limited in coverage, contextual fidelity, or injection success.

**AVIATOR** is the first AI-agentic vulnerability injection framework. It decomposes vulnerability injection into a coordinated workflow of specialized AI agents, tool-based analysis, and iterative self-correction, with RAG and LoRA-based fine-tuning to produce realistic, category-specific vulnerabilities.

---

## How to cite

```bibtex
@article{aviator2025,
  title     = {AI Agentic Vulnerability Injection And Transformation with Optimized Reasoning},
  author    = {Lbath, Amine and Amini, Massih-Reza and Delaitre, Aurelien and Okun, Vadim},
  year      = {2025},
  eprint    = {2508.20866},
  archivePrefix = {arXiv},
  url       = {https://arxiv.org/abs/2508.20866},
}
```

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Disclaimer

NIST-developed software is provided by NIST as a public service. You may use, copy and distribute copies of the software in any medium, provided that you keep intact this entire notice. You may improve, modify and create derivative works of the software or any portion of the software, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the software and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the software.

NIST-developed software is expressly provided "AS IS." NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT OR ARISING BY OPERATION OF LAW, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. NIST NEITHER REPRESENTS NOR WARRANTS THAT THE OPERATION OF THE SOFTWARE WILL BE UNINTERRUPTED OR ERROR-FREE, OR THAT ANY DEFECTS WILL BE CORRECTED. NIST DOES NOT WARRANT OR MAKE ANY REPRESENTATIONS REGARDING THE USE OF THE SOFTWARE OR THE RESULTS THEREOF, INCLUDING BUT NOT LIMITED TO THE CORRECTNESS, ACCURACY, RELIABILITY, OR USEFULNESS OF THE SOFTWARE.

You are solely responsible for determining the appropriateness of using and distributing the software and you assume all risks associated with its use, including but not limited to the risks and costs of program errors, compliance with applicable laws, damage to or loss of data, programs or equipment, and the unavailability or interruption of operation. This software is not intended to be used in any situation where a failure could cause risk of injury or damage to property. The software developed by NIST employees is not subject to copyright protection within the United States.

