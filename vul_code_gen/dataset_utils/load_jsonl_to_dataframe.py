import json
import pandas as pd

def load_jsonl_to_dataframe(file_path: str) -> pd.DataFrame:
    """
    Reads a JSONL file and returns its contents as a pandas DataFrame.
    
    Args:
        file_path (str): The path to the input file (JSONL).
    
    Returns:
        pd.DataFrame: A DataFrame containing the data from the file.
    """
    with open(file_path) as f:
        file_lines = f.read().splitlines()

    df_tmp = pd.DataFrame(file_lines)
    df_tmp.columns = ['json_element']
    df_tmp['json_element'].apply(json.loads)
    return pd.json_normalize(df_tmp['json_element'].apply(json.loads))