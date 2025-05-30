# https://www.kaggle.com/code/ksmooi/fine-tuning-qwen-2-5-coder-14b-llm-sft-peft

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

import argparse
from unsloth import FastLanguageModel
import torch

# Argument parsing
parser = argparse.ArgumentParser(description='Fine-tune Qwen2.5-Coder-32B with LoRA')
parser.add_argument('--model_name', type=str, default="unsloth/Qwen2.5-Coder-32B-Instruct", help='Model name')
parser.add_argument('--max_seq_length', type=int, default=18000, help='Maximum sequence length')
parser.add_argument('--load_in_4bit', type=bool, default=True, help='Use 4bit quantization')
parser.add_argument('--lora_r', type=int, default=32, help='LoRA rank')
parser.add_argument('--lora_alpha', type=int, default=32, help='LoRA alpha')
parser.add_argument('--lora_dropout', type=float, default=0, help='LoRA dropout')
parser.add_argument('--bias', type=str, default="none", help='Bias')
parser.add_argument('--num_train_epochs', type=int, default=5, help='Number of training epochs')
parser.add_argument('--learning_rate', type=float, default=2e-4, help='Learning rate')
parser.add_argument('--gradient_accumulation_steps', type=int, default=4, help='Gradient accumulation steps')
parser.add_argument('--per_device_train_batch_size', type=int, default=1, help='Batch size per device')
parser.add_argument('--output_dir', type=str, default='outputs', help='Output directory')
parser.add_argument('--dataset_path', type=str, required=True, help='Path to the dataset JSONL file')

args = parser.parse_args()

### Model configuration
max_seq_length = args.max_seq_length
dtype = None           # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
load_in_4bit = args.load_in_4bit

# Load the model and tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=args.model_name,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
    # token = "hf_...", # use one if using gated models like meta-llama/Llama-2-7b-hf
)

# Configure LoRA for efficient fine-tuning.
model = FastLanguageModel.get_peft_model(
    model,
    r=args.lora_r,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=args.lora_alpha,
    lora_dropout=args.lora_dropout,
    bias=args.bias,     # Supports any, but = "none" is optimized
    # [NEW] "unsloth" uses 30% less VRAM, fits 2x larger batch sizes!
    use_gradient_checkpointing="unsloth",  # True or "unsloth" for very long context
    random_state=3407,
    use_rslora=False,  # We support rank stabilized LoRA
    loftq_config=None, # And LoftQ
)

### Data preprocessing
from datasets import load_dataset
from unsloth.chat_templates import get_chat_template, standardize_sharegpt

tokenizer = get_chat_template(
    tokenizer,
    chat_template="qwen-2.5",
    system_message="You are a cybersecurity and code analysis expert with deep knowledge in vulnerability detection, secure coding practices, and static code analysis."
)

def formatting_prompts_func(examples):
    convos = examples["conversations"]
    texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
    return {"text": texts}

dataset = load_dataset("json", data_files=args.dataset_path, split="train")
dataset = standardize_sharegpt(dataset)
dataset = dataset.map(formatting_prompts_func, batched=True)

### Training
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
    dataset_num_proc=4,
    packing=False,  # Can make training 5x faster for short sequences.
    args=TrainingArguments(
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        warmup_steps=5,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=1,
        optim="paged_adamw_8bit",  # Save more memory
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=args.output_dir,
        report_to="none",  # Use this for WandB etc
    ),
)

# Only train on responses
from unsloth.chat_templates import train_on_responses_only
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

# Show current memory stats
gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
logging.info(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
logging.info(f"{start_gpu_memory} GB of memory reserved.")

# Train the model
trainer_stats = trainer.train()

# Show final memory and time stats
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory / max_memory * 100, 3)
lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)

logging.info(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
logging.info(f"{round(trainer_stats.metrics['train_runtime'] / 60, 2)} minutes used for training.")
logging.info(f"Peak reserved memory = {used_memory} GB.")
logging.info(f"Peak reserved memory for training = {used_memory_for_lora} GB.")
logging.info(f"Peak reserved memory % of max memory = {used_percentage} %.")
logging.info(f"Peak reserved memory for training % of max memory = {lora_percentage} %.")

# Save the model
model.save_pretrained(args.output_dir)
tokenizer.save_pretrained(args.output_dir)