# LoRA Fine-Tuning for AVIATOR

Fine-tuning scripts for adapting language models to the AVIATOR vulnerability injection workflow. Uses **unsloth** and **LoRA** for efficient parameter-efficient training.

> **Environment:** These scripts use the virtual environment from the **AVIATOR root**. Run them from the repo root with `uv run` or activate the root venv first.

---

## Setup

From the **AVIATOR root**:

```bash
cd AVIATOR/
./scripts/setup_aviator.sh
```

The LoRA scripts require **unsloth** and **trl** in addition to the core AVIATOR dependencies. If they are not installed:

```bash
uv add unsloth trl wandb
```

---

## Scripts

| Script | Method | Description |
|--------|--------|-------------|
| `LoRA_FT.py` | SFT (Supervised Fine-Tuning) | LoRA-based SFT with response-only training |
| `GRPO_FT.py` | GRPO (Group Relative Policy Optimization) | Reinforcement learning with CodeBLEU reward |

---

## LoRA_FT.py — SFT

Supervised fine-tuning of Qwen2.5-Coder with LoRA. Uses ShareGPT-style conversations and trains only on assistant responses.

**Run from repo root:**

```bash
uv run python LoRA_FT/LoRA_FT.py --dataset_path data/PrimeVul_v0.1/primevul_train_paired.jsonl --output_dir outputs
```

**Dataset format:** JSONL with ShareGPT-style `conversations` (e.g. `{"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}`).

### Key arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--dataset_path` | **Required** | Path to training JSONL |
| `--output_dir` | `outputs` | Save directory for model and tokenizer |
| `--model_name` | `unsloth/Qwen2.5-Coder-32B-Instruct` | Base model |
| `--max_seq_length` | `18000` | Max sequence length |
| `--load_in_4bit` | `True` | 4-bit quantization |
| `--lora_r` | `32` | LoRA rank |
| `--lora_alpha` | `32` | LoRA alpha |
| `--num_train_epochs` | `5` | Number of epochs |
| `--learning_rate` | `2e-4` | Learning rate |
| `--per_device_train_batch_size` | `1` | Batch size per device |
| `--gradient_accumulation_steps` | `4` | Gradient accumulation |

---

## GRPO_FT.py — GRPO

Group Relative Policy Optimization with CodeBLEU as the reward signal. Uses Weights & Biases for logging.

**Run from repo root:**

```bash
uv run python LoRA_FT/GRPO_FT.py \
  --model_name unsloth/Qwen2.5-Coder-32B-Instruct \
  --dataset_path data/PrimeVul_v0.1/primevul_train_paired.jsonl \
  --output_dir Qwen2.5-coder-GRPO
```

**Dataset format:** JSONL with `system`, `conversations` (human/gpt), e.g.:

```json
{
  "system": "You are a cybersecurity expert...",
  "conversations": [
    {"from": "human", "value": "..."},
    {"from": "gpt", "value": "..."}
  ]
}
```

### Key arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--model_name` | **Required** | Base model name |
| `--dataset_path` | **Required** | Path to training JSONL |
| `--output_dir` | `Qwen2.5-coder-0.5B-GRPO` | Save directory |
| `--max_prompt_length` | `16000` | Max prompt length |
| `--max_completion_length` | `16000` | Max completion length |
| `--num_generations` | `8` | Samples per prompt for GRPO |
| `--batch_size` | `2` | Per-device batch size |
| `--learning_rate` | `2e-4` | Learning rate |
| `--beta` | `0.04` | GRPO beta |
| `--temperature` | `0.7` | Generation temperature |
| `--wandb_project` | `vul-code-gen` | W&B project name |
| `--wandb_entity` | — | W&B entity (user/team) |

---

## Hardware

Both scripts use 4-bit quantization and LoRA for reduced VRAM. A GPU with ≥24 GB VRAM is recommended for Qwen2.5-Coder-32B.

---

## Fine-tuned workflow

After fine-tuning, use the LoRA adapter with the **FT workflow**:

```bash
./scripts/run_injection.sh \
  --dataset-path validation_dataset/formai_with_benign_37.jsonl \
  --workflow-json vul_code_gen/AVIATOR_13steps_full_workflow/vul_code_gen_workflow_FT.json
```

In `vul_code_gen_workflow_FT.json`, set `llm_path` in the `vul_inject_SFT` LLM section to your output directory (e.g. `outputs` or `Qwen2.5-coder-GRPO/full_GRPO` for GRPO).
