#!/usr/bin/env python3
import json
import pandas as pd
import logging

# Add logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_formai_pairs(formai_paired_data_path: str) -> pd.DataFrame:
    """
    Load vulnerable/benign source code pairs from the FormAI dataset.

    Args:
        formai_paired_data_path (str): Path to the FormAI paired dataset file.

    Returns:
        pd.DataFrame: DataFrame containing columns "benign", "vulnerable", and "vul_id".
    """
    logging.info(f"Loading FormAI paired dataset {formai_paired_data_path} to dataframe.")
    
    # Read JSONL file line by line
    data = []
    with open(formai_paired_data_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    
    df = pd.DataFrame(data)
    
    return pd.DataFrame({
        "benign": df["benign_code"].values,
        "vulnerable": df["vulnerable_code"].values,
        "vul_id": df["cwe_id"].values,
        "benign_hash": df["file_name"].values,
        "vulnerable_hash": df["file_name"].values,
    })