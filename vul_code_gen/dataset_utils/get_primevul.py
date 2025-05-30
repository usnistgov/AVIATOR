import pandas as pd
import logging

from vul_code_gen.dataset_utils.load_jsonl_to_dataframe import load_jsonl_to_dataframe

# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler()) # Avoid "No handlers could be found" warnings

def extract_cwe_id(cwe_list):
    """
    Extracts the CWE ID from a list of strings containing the pattern 'CWE-ID'.

    Args:
        cwe_list (list): A list of strings where one might match the pattern 'CWE-ID'.
                         Example: ['CWE-79'].

    Returns:
        int: The extracted ID as an integer if the pattern is valid.
             Returns None if the list is empty or the ID cannot be extracted.
    """
    if not cwe_list:  # Check if the list is empty
        return None
    try:
        # Extract ID from the pattern 'CWE-ID'
        for item in cwe_list:
            if item.startswith('CWE-'):
                return int(item.split('-')[1])
    except (IndexError, ValueError):
        return None
    return None  # If no valid ID is found


def load_primevul_to_dataframe(primevul_data_path: str) -> pd.DataFrame:
    """
    Returns the content of a primevul dataset as a pandas DataFrame.
    
    Parameters:
        primevul_data_path (str): The path to the input primevul file.
    
    Returns:
        pd.DataFrame: A DataFrame containing the data from the primevul file.
    """
    logger.info(f"Loading primevul dataset {primevul_data_path} to dataframe.")
    df = load_jsonl_to_dataframe(primevul_data_path)
   
    # Apply the function to the 'cwe' column
    df['vul_id'] = df['cwe'].apply(extract_cwe_id).astype('Int64')

    return df[['func', 'vul_id', 'target', 'func_hash']]


def load_primevul_vul_pairs(primevul_data_path: str) -> pd.DataFrame:
    """
    Load vulnerable/benign source code pairs from the dataset.
    The pairs are stored in adjacent rows, with the first being vulnerable and the following benign.

    Args:
        primevul_data_path (str): Path to the dataset file.

    Returns:
        pd.DataFrame: DataFrame containing columns "benign", "vulnerable", and "vul_id".
    """
    df = load_primevul_to_dataframe(primevul_data_path)
    return pd.DataFrame({
        "vulnerable": df.loc[::2, "func"].values,
        "benign": df.loc[1::2, "func"].values,
        "vul_id": df.loc[::2, "vul_id"].values.astype(str),
        "benign_hash": df.loc[1::2, "func_hash"].values.astype(str),
        "vulnerable_hash": df.loc[::2, "func_hash"].values.astype(str),
    })


def load_primevul_benign_code_list(primevul_data_path: str) -> pd.DataFrame:
    """
    Returns a list of benign code samples extracted from a PrimeVul dataset.
    
    Parameters:
        primevul_data_path (str): The path to the input PrimeVul dataset file.
    
    Returns:
        pd.DataFrame: List of benign code samples.
    """
    logger.info(f"Extracting list of benign code samples from a PrimeVul dataset {primevul_data_path}.")
    df = load_jsonl_to_dataframe(primevul_data_path)
    
    # Apply the function to the 'cwe' column
    df['vul_id'] = df['cwe'].apply(extract_cwe_id).astype('Int64')

    # Extract list of benign code samples
    return df[df['target'] == 0][['vul_id', 'func']]
