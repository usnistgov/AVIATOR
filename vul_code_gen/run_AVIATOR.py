#########################################################################
# 1) Sign in to Hugging Face by running this command: hf auth login
#########################################################################
import os
import sys
from pathlib import Path
# Makes the project root importable (awe, vul_code_gen)
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def _patch_transformers_cache_for_gte_qwen():
    """Compatibility for Alibaba-NLP/gte-Qwen2: model code calls get_usable_length, removed in transformers 4.56+."""
    try:
        from transformers import cache_utils
        if not hasattr(cache_utils.DynamicCache, "get_usable_length"):
            def get_usable_length(self, new_seq_length=None, layer_idx=0):
                return self.get_seq_length(layer_idx)
            cache_utils.DynamicCache.get_usable_length = get_usable_length
    except Exception:
        pass

_patch_transformers_cache_for_gte_qwen()

import pandas as pd

from vul_code_gen.dataset_utils import load_primevul_vul_pairs, load_sard100_vul_pairs, load_formai_pairs
from codebleu import calc_codebleu
from awe import load_workflow_from_json, run_workflow
import logging  
import json
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_vul_code_gen_workflow(code_pair_df, workflow_json=None, output_file=None, percent=100.0):
    """
    Tests the generate_vul function on a percentage of the provided dataset.

    Parameters:
      code_pair_df (pd.DataFrame): DataFrame containing the paired dataset.
      workflow_json (str): The path to the workflow JSON file.
      output_file (str): The path to the output file.
      percent (float): The percentage of the dataset to evaluate (0 to 100).

    For each sampled row, the function:
      1. Calls generate_vul with input {"benign_code": benign_code, "vul_inject_id": cwe_id}.
      2. Stores the output in a file.

    Returns:
      float: The average CodeBLEU score over the evaluated samples.
    """
    # Sample the dataset
    sample_size = max(1, int(len(code_pair_df) * percent / 100))
    sample_df = code_pair_df.sample(n=sample_size, random_state=1)

    # Load the workflow
    workflow = load_workflow_from_json(workflow_json)

    dataset_vuln_benign_codebleu_scores = []
    generated_vuln_benign_codebleu_scores = []
    expected_vuln_generated_vuln_codebleu_scores = []

    for i, (_, row) in enumerate(sample_df.iterrows()):
        benign_code = row["benign"]
        expected_vuln_code = row["vulnerable"]
        cwe_id = row["vul_id"]
        vuln_func_hash = row["vulnerable_hash"]
        benign_func_hash = row["benign_hash"]

        # Execute generate_vul using the benign code and the CWE-ID
        input_data = {"benign_code": benign_code, "vul_inject_id": str(cwe_id)}
        logger.info("--------------------------------")
        logger.info(f"🧰  Processing input {i+1}/{sample_size}")
        logger.info(f"Pair {vuln_func_hash} - {benign_func_hash}, CWE-ID: {cwe_id}")
        output = run_workflow(workflow, input_data, max_retries=2)
        if hasattr(output, "vulnerable_code"):
            generated_vuln_code = output.vulnerable_code

            # Calculate CodeBLEU score for the expected vulnerable code against the benign code
            dataset_vuln_benign_codebleu_score = calc_codebleu([expected_vuln_code], [benign_code], lang="cpp", weights=(0.25, 0.25, 0.25, 0.25), tokenizer=None)
            dataset_vuln_benign_codebleu_scores.append(dataset_vuln_benign_codebleu_score['codebleu'])
            
            # Calculate CodeBLEU score for the generated vulnerable code against the benign code
            generated_vuln_benign_codebleu_score = calc_codebleu([generated_vuln_code], [benign_code], lang="cpp", weights=(0.25, 0.25, 0.25, 0.25), tokenizer=None)
            generated_vuln_benign_codebleu_scores.append(generated_vuln_benign_codebleu_score['codebleu'])

            # Calculate CodeBLEU score for the generated code against the expected vulnerable code
            expected_vuln_generated_vuln_codebleu_score = calc_codebleu([expected_vuln_code], [generated_vuln_code], lang="cpp", weights=(0.25, 0.25, 0.25, 0.25), tokenizer=None)
            expected_vuln_generated_vuln_codebleu_scores.append(expected_vuln_generated_vuln_codebleu_score['codebleu'])

            logger.info(f"Pair {vuln_func_hash} - {benign_func_hash}, CWE-ID: {cwe_id}")
            logger.info(f"CodeBLEU for dataset pair {cwe_id}: {dataset_vuln_benign_codebleu_score['codebleu'] * 100:.2f}%")
            logger.info(f"CodeBLEU for generated vulnerable code against benign code {cwe_id}: {generated_vuln_benign_codebleu_score['codebleu'] * 100:.2f}%")
            logger.info(f"CodeBLEU for expected vulnerable code against generated vulnerable code {cwe_id}: {expected_vuln_generated_vuln_codebleu_score['codebleu'] * 100:.2f}%")

            # Save the output to a file
            with open(output_file, "a") as f:
                output_data = {
                    "cwe_id": str(cwe_id),
                    "vulnerable_hash": vuln_func_hash,
                    "benign_hash": benign_func_hash,
                    "benign_code": benign_code,
                    **output.__dict__
                }
                f.write(json.dumps(output_data) + "\n")

    logger.info("--------------------------------")

    avg_dataset_vuln_benign_codebleu_score = sum(dataset_vuln_benign_codebleu_scores) / len(dataset_vuln_benign_codebleu_scores) if dataset_vuln_benign_codebleu_scores else 0
    logger.info(f"Dataset Vulnerable / Benign Average CodeBLEU Score over {len(dataset_vuln_benign_codebleu_scores)} samples: {avg_dataset_vuln_benign_codebleu_score * 100:.2f}%")

    avg_generated_vuln_benign_codebleu_score = sum(generated_vuln_benign_codebleu_scores) / len(generated_vuln_benign_codebleu_scores) if generated_vuln_benign_codebleu_scores else 0
    logger.info(f"Generated Vulnerable / Benign Average CodeBLEU Score over {len(generated_vuln_benign_codebleu_scores)} samples: {avg_generated_vuln_benign_codebleu_score * 100:.2f}%")

    avg_expected_vuln_generated_vuln_codebleu_score = sum(expected_vuln_generated_vuln_codebleu_scores) / len(expected_vuln_generated_vuln_codebleu_scores) if expected_vuln_generated_vuln_codebleu_scores else 0
    logger.info(f"Expected Vulnerable / Generated Vulnerable Average CodeBLEU Score over {len(expected_vuln_generated_vuln_codebleu_scores)} samples: {avg_expected_vuln_generated_vuln_codebleu_score * 100:.2f}%")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run vulnerability code generation workflow')
    parser.add_argument('--dataset_path', type=str, required=True,
                       help='Path to the dataset file')
    parser.add_argument('--workflow_json', type=str, required=True,
                       help='Path to the workflow JSON configuration file')
    parser.add_argument('--output_file', type=str, required=True,
                       help='Path to save the output results (JSONL file)')
    parser.add_argument('--percent', type=float, default=100.0,
                       help='Percentage of dataset to process (default: 100.0)')
    parser.add_argument('--dataset_type', type=str, default='primevul',
                       choices=['primevul', 'sard100', 'formai'],
                       help='Type of dataset to load (default: primevul)')

    args = parser.parse_args()
    logger.info("*"*50)
    logger.info(f"Validating {args.dataset_path} with {args.workflow_json} and saving results to {args.output_file}")
    logger.info("*"*50)
    
    # Load the dataset based on type
    if args.dataset_type == 'sard100':
        code_pair_df = load_sard100_vul_pairs(args.dataset_path)
    elif args.dataset_type == 'formai':
        code_pair_df = load_formai_pairs(args.dataset_path)
    elif args.dataset_type == 'primevul':
        code_pair_df = load_primevul_vul_pairs(args.dataset_path)
    else:
        logger.warning("Invalid dataset type. Please choose from: primevul, sard100, formai")
        return
    
    if code_pair_df.empty:
        logger.warning("Dataset is empty. Nothing to test.")
        return

    run_vul_code_gen_workflow(code_pair_df, args.workflow_json, args.output_file, args.percent)

if __name__ == "__main__":
    main()