#!/usr/bin/env python3
import os
import json
import argparse
import pandas as pd
import re
import logging

# Add logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_sard100_vul_pairs(sard100_data_path: str) -> pd.DataFrame:
    """
    Load vulnerable/benign source code pairs from the SARD100 dataset.

    Args:
        sard100_data_path (str): Path to the SARD100 dataset file.

    Returns:
        pd.DataFrame: DataFrame containing columns "benign", "vulnerable", and "vul_id".
    """
    logging.info(f"Loading SARD100 dataset {sard100_data_path} to dataframe.")
    
    # Read JSONL file line by line
    data = []
    with open(sard100_data_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    
    df = pd.DataFrame(data)
    
    return pd.DataFrame({
        "benign": df["benign_code"].values,
        "vulnerable": df["vuln_code"].values,
        "vul_id": df["cwe_id"].values,
        "benign_hash": df["secure_folder"].values,
        "vulnerable_hash": df["vuln_folder"].values,
    })



def remove_header_comments(code: str) -> str:
    """
    Removes leading header comments (both single-line // and multi-line /* */)
    from the provided C/C++ code. Assumes the header comments are at the very beginning.
    """
    pattern = r'^(?:\s*(?://[^\n]*|/\*[\s\S]*?\*/)\s*)+'
    return re.sub(pattern, '', code, count=1)

def load_code_from_src(folder_path):
    """
    Loads the first C file found in the src/ subfolder in the given folder.
    Removes header comments and returns the code as a string.
    """
    src_path = os.path.join(folder_path, "src")
    if not os.path.exists(src_path):
        logging.warning(f"{src_path} does not exist.")
        return None
    for file in os.listdir(src_path):
        if file.endswith(".c"):
            file_path = os.path.join(src_path, file)
            with open(file_path, "r", encoding='cp1252') as f:
                code = f.read()
            # Transform the condition
            code = code.replace('if(argc > 1)', 'if(argc > 1 && argc < 2)')
            code = code.replace('if (argc > 1)', 'if (argc > 1 && argc < 2)')
            return remove_header_comments(code)
    logging.warning(f"No C file found in {src_path}.")
    return None
 
def load_manifest(manifest_path):
    """
    Loads the manifest.sarif file and extracts the CWE-ID, description, and status.
    It expects the file to follow SARIF v2.1.0 format where the first run contains:
    - The CWE-ID in the first result's "ruleId".
    - The description and status in the "properties" dictionary.
    """
    import json
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    run = data.get("runs", [{}])[0]
    properties = run.get("properties", {})
    description = properties.get("description", "")
    status = properties.get("status", "").lower()
    results = run.get("results", [])
    cwe_id = results[0].get("ruleId", "").split("-")[1] if results else ""
    return cwe_id, description, status


def pair_folders(vuln_dir, secure_dir):
    """
    Matches vulnerable and secure folders based on the naming convention, keeping only the highest version.
    For a vulnerable folder with an id (e.g. '149045-v3.0.0'), the corresponding secure folder is assumed
    to start with str(int(id) + 1) (e.g. '149046-v4.0.0').
    Returns a list of tuples: (vuln_folder_path, secure_folder_path).
    """
    # Group vulnerable folders by their base ID
    vuln_folders_by_id = {}
    for vuln_folder in os.listdir(vuln_dir):
        if not os.path.isdir(os.path.join(vuln_dir, vuln_folder)):
            continue
            
        parts = vuln_folder.split("-v")
        if len(parts) != 2:
            continue
            
        base_id = parts[0]
        version = parts[1]
        if base_id not in vuln_folders_by_id:
            vuln_folders_by_id[base_id] = []
        vuln_folders_by_id[base_id].append((version, vuln_folder))
    
    # Group secure folders by their base ID
    secure_folders_by_id = {}
    for secure_folder in os.listdir(secure_dir):
        parts = secure_folder.split("-v")
        if len(parts) != 2:
            continue
            
        base_id = parts[0]
        version = parts[1]
        if base_id not in secure_folders_by_id:
            secure_folders_by_id[base_id] = []
        secure_folders_by_id[base_id].append((version, secure_folder))
    
    pairs = []
    for vuln_id, vuln_versions in vuln_folders_by_id.items():
        try:
            secure_id = str(int(vuln_id) + 1)
        except ValueError:
            logging.warning(f"Skipping ID {vuln_id}: cannot parse numeric id.")
            continue
            
        if secure_id not in secure_folders_by_id:
            continue
            
        # Get highest version for both vulnerable and secure folders
        highest_vuln = max(vuln_versions, key=lambda x: x[0])
        highest_secure = max(secure_folders_by_id[secure_id], key=lambda x: x[0])
        
        vuln_folder_path = os.path.join(vuln_dir, highest_vuln[1])
        secure_folder_path = os.path.join(secure_dir, highest_secure[1])
        pairs.append((vuln_folder_path, secure_folder_path))
    
    return pairs

def load_sard100_dataset(sar100_dir):
    """
    Loads the dataset by pairing vulnerable and secure folders,
    extracting manifest information, and loading the C code.
    Returns a pandas DataFrame with the following columns:
    - vuln_folder: path to the vulnerable folder.
    - secure_folder: path to the secure folder.
    - cwe_id: extracted CWE ID from the manifest.
    - description: vulnerability description from the manifest.
    - benign_code: the secure (benign) C code.
    - vuln_code: the expected vulnerable C code.
    """
    vuln_dir = os.path.join(sar100_dir, "2015-03-15-c-test-suite-for-source-code-analyzer-v2-vulnerable")
    secure_dir = os.path.join(sar100_dir, "2015-03-15-c-test-suite-for-source-code-analyzer-secure-vv2")
    pairs = pair_folders(vuln_dir, secure_dir)
    data = []
    for vuln_folder, secure_folder in pairs:
        manifest_path = os.path.join(vuln_folder, "manifest.sarif")
        cwe_id, description, status = load_manifest(manifest_path)
        vuln_folder_name = os.path.basename(vuln_folder)
        secure_folder_name = os.path.basename(secure_folder)
        
        if cwe_id is None:
            logging.warning(f"Skipping pair {vuln_folder_name} - {secure_folder_name}: cwe id missing")
            continue
        if status is None:
            logging.warning(f"Skipping pair {vuln_folder_name} - {secure_folder_name}: status missing")
            continue

        if status == "deprecated":
            logging.warning(f"Skipping pair {vuln_folder_name} - {secure_folder_name}: status deprecated")
            continue

        vuln_code = load_code_from_src(vuln_folder)
        benign_code = load_code_from_src(secure_folder)
        if vuln_code is None or benign_code is None:
            logging.warning(f"Skipping pair {vuln_folder_name} - {secure_folder_name}: missing code.")
            continue

        data.append({
            "vuln_folder": vuln_folder_name,
            "secure_folder": secure_folder_name,
            "cwe_id": cwe_id,
            "description": description,
            "benign_code": benign_code,
            "vuln_code": vuln_code
        })

    df = pd.DataFrame(data)
    return df
