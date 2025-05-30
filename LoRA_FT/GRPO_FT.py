import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

import torch
import argparse
import wandb
from unsloth import FastLanguageModel
from trl import GRPOTrainer, GRPOConfig, apply_chat_template
from datasets import load_dataset
from codebleu import calc_codebleu
from transformers import TrainerCallback, TrainerState, TrainerControl

def parse_args():
    parser = argparse.ArgumentParser(description='GRPO Fine-tuning with LoRA')
    # Model configuration
    parser.add_argument('--model_name', type=str, required=True,
                      help='Name of the pretrained model')
    parser.add_argument('--max_prompt_length', type=int, default=16000,
                      help='Maximum prompt length')
    parser.add_argument('--max_completion_length', type=int, default=16000,
                      help='Maximum completion length')
    parser.add_argument('--load_in_4bit', action='store_true', default=True,
                      help='Whether to load model in 4-bit precision')
    
    # LoRA configuration
    parser.add_argument('--lora_r', type=int, default=32,
                      help='LoRA attention dimension')
    parser.add_argument('--lora_alpha', type=int, default=32,
                      help='LoRA alpha parameter')
    parser.add_argument('--lora_dropout', type=float, default=0.0,
                      help='LoRA dropout value')
    parser.add_argument('--bias', type=str, default="none",
                      help='Bias type')
    
    # Training configuration
    parser.add_argument('--dataset_path', type=str, required=True,
                      help='Path to the training dataset')
    parser.add_argument('--output_dir', type=str, default="Qwen2.5-coder-0.5B-GRPO",
                      help='Output directory for saving model')
    parser.add_argument('--batch_size', type=int, default=2,
                      help='Per device training batch size')
    parser.add_argument('--gradient_accumulation_steps', type=int, default=4,
                      help='Number of gradient accumulation steps')
    parser.add_argument('--num_generations', type=int, default=8,
                      help='Number of generations per prompt')
    parser.add_argument('--learning_rate', type=float, default=2e-4,
                      help='Learning rate')
    parser.add_argument('--beta', type=float, default=0.04,
                      help='Beta parameter for GRPO')
    parser.add_argument('--temperature', type=float, default=0.7,
                      help='Temperature for generation')
    parser.add_argument('--weight_decay', type=float, default=0.01,
                      help='Weight decay')
    parser.add_argument('--seed', type=int, default=42,
                      help='Random seed')
    
    # Logging and saving configuration
    parser.add_argument('--logging_steps', type=int, default=1,
                      help='Logging steps')
    parser.add_argument('--save_steps', type=int, default=100,
                      help='Save steps')
    parser.add_argument('--wandb_project', type=str, default="vul-code-gen",
                      help='Weights & Biases project name')
    parser.add_argument('--wandb_entity', type=str, default=None,
                      help='Weights & Biases entity (username or team name)')
    parser.add_argument('--wandb_run_name', type=str, default=None,
                      help='Weights & Biases run name')
    return parser.parse_args()

def generate_run_name(args):
    """Generate a descriptive run name based on training parameters."""
    model_name_short = args.model_name.split('/')[-1]  # Get the last part of the model name
    run_name = "GRPO_ft_try7"
    run_name += f"{model_name_short}_lr{args.learning_rate}_b{args.batch_size}_numGen{args.num_generations}"
    run_name += f"_lora-r{args.lora_r}_a{args.lora_alpha}"
    run_name += f"_temp{args.temperature}"
    run_name += f"_seed{args.seed}"
    return run_name

def main():
    args = parse_args()
    
    # Generate custom run name if not provided
    if args.wandb_run_name is None:
        args.wandb_run_name = generate_run_name(args)
    
    logging.info(f"********** Run name: {args.wandb_run_name} **********")

    # Initialize wandb
    wandb.init(
        project=args.wandb_project,
        entity=args.wandb_entity,
        name=args.wandb_run_name,
        config={
            "model_name": args.model_name,
            "max_prompt_length": args.max_prompt_length,
            "max_completion_length": args.max_completion_length,
            "load_in_4bit": args.load_in_4bit,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "batch_size": args.batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "num_generations": args.num_generations,
            "learning_rate": args.learning_rate,
            "beta": args.beta,
            "temperature": args.temperature,
            "weight_decay": args.weight_decay,
            "seed": args.seed,
        }
    )
    
    ### 1. Load the model
    # Model configuration
    dtype = None  # None for auto detection
    
    # Load the model and tokenizer
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_prompt_length,
        dtype=dtype,
        load_in_4bit=args.load_in_4bit,
    )

    # Configure LoRA for efficient fine-tuning
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias=args.bias,
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
        use_rslora=False,
        loftq_config=None,
    )

    ### 2. Load the dataset
    dataset = load_dataset("json", data_files=args.dataset_path, split="train")

    def format_conversation(example):
        system = example['system']
        conversations = example['conversations']
        
        # Extract user and assistant messages
        user_message = None
        assistant_message = None
        
        for msg in conversations:
            if msg['from'] == 'human':
                user_message = msg['value']
            elif msg['from'] == 'gpt':
                assistant_message = msg['value']
        
        # Create formatted conversation
        formatted_conversation = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_message}
        ]
        
        return {
            'prompt': formatted_conversation,
            'completion': [{'role': 'assistant', 'content': assistant_message}]
        }

    # Apply formatting to dataset
    dataset = dataset.map(format_conversation)
    # Remove the original columns and keep only the formatted prompt and ground_truth
    dataset = dataset.remove_columns(['system', 'conversations'])

    # Apply chat template
    dataset = dataset.map(
        apply_chat_template,
        fn_kwargs={"tokenizer": tokenizer}
    )
    # Rename completion to ground_truth
    dataset = dataset.rename_column('completion', 'ground_truth')


    ### 3. Configure Training

    # Define CodeBleu reward function
    def compute_codebleu_reward(completions, ground_truth, **kwargs):
        """Compute reward using codeBLEU score."""
        rewards = []
        for pred_code, ref_code in zip(completions, ground_truth):
            # Calculate codeBLEU score
            score = calc_codebleu(
                [ref_code],
                [pred_code],
                lang="cpp",
                weights=(0.25, 0.25, 0.25, 0.25),
            )
            rewards.append(score['codebleu'])
        return rewards

    class WandbGRPOCallback(TrainerCallback):
        def __init__(self):
            super().__init__()
            self.current_step = 0

        def on_init_end(self, args, state: TrainerState, control: TrainerControl, **kwargs):
            """Called when the trainer initialization is complete."""
            pass

        def on_step_end(self, args, state: TrainerState, control: TrainerControl, **kwargs):
            """Called after each training step."""
            if state.log_history:
                latest_log = state.log_history[-1]
                metrics = {}
                
                # Log training metrics
                if "loss" in latest_log:
                    metrics["loss"] = latest_log["loss"]
                if "reward" in latest_log:
                    metrics["reward"] = latest_log["reward"]
                if "kl" in latest_log:
                    metrics["kl"] = latest_log["kl"]
                
                if metrics:
                    wandb.log(metrics, step=self.current_step)
                self.current_step += 1

        def on_train_begin(self, args, state: TrainerState, control: TrainerControl, **kwargs):
            """Called at the beginning of training."""
            pass

        def on_train_end(self, args, state: TrainerState, control: TrainerControl, **kwargs):
            """Called at the end of training."""
            pass

    training_args = GRPOConfig(
        output_dir=args.output_dir,
        logging_steps=args.logging_steps,
        log_completions=True,
        gradient_checkpointing=True,
        save_steps=args.save_steps,
        max_completion_length=args.max_completion_length,
        max_prompt_length=args.max_prompt_length,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        beta=args.beta,
        temperature=args.temperature,
        num_generations=args.num_generations,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        seed=args.seed,
    )

    # Create wandb callback
    wandb_callback = WandbGRPOCallback()

    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        reward_funcs=compute_codebleu_reward,
        callbacks=[wandb_callback],  # Add wandb callback
    )

    ### 4. Train the model
    trainer_stats = trainer.train()
    logging.info(f"Trainer stats: {trainer_stats}")

    ### 5. Save the model
    model.save_pretrained(args.output_dir + "/full_GRPO")
    tokenizer.save_pretrained(args.output_dir + "/full_GRPO")
if __name__ == "__main__":
    main()
