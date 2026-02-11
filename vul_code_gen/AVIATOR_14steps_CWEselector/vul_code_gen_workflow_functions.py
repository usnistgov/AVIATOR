"""Implementation of Agents function
"""

import os
import re
import difflib
import subprocess
import tempfile
import json
import shutil
from pathlib import Path

from openai import OpenAI

# AVIATOR repo root (parent of vul_code_gen)
_AVIATOR_ROOT = Path(__file__).resolve().parent.parent.parent
from vul_code_gen.knowledge_base.vulnerability_categories import load_vul_categories_from_json

def load_vul_info(vul_inject_id: str) -> dict[str: str]:
    """
    Load information about the category of code vulnerability to inject, ready to be used in prompt.

    Args:
        target_vul_id (str): Id of the vulnerability to inject. Must belong to available_vul_categories.
    
    Returns:
        dict[str, str]: Output argument name + formatted description of the requested vulnerability category.
    
    Raises:
        ValueError: When target_vul_id is not in available_vul_categories
    """
    available_vul_categories = load_vul_categories_from_json()
    
    if vul_inject_id in available_vul_categories:
        vulnerability = available_vul_categories[vul_inject_id]
        return {"vul_inject_info": str(vulnerability)}
    else:
        raise ValueError(f"Invalid target_vul_id {vul_inject_id}. Choose from {available_vul_categories.keys()}.")

def check_code_diff(benign_code: str, vulnerable_code: str) -> dict:
    """
    Check if the vulnerable code is actually different from the benign code,
    ignoring whitespace differences and comments.
    
    Args:
        benign_code (str): The original non-vulnerable code.
        vulnerable_code (str): The supposedly modified vulnerable code.
        
    Returns:
        dict: Output with diff and boolean flag indicating if the codes are different.
    """
    # Function to strip comments from a single line
    def strip_line_comments(line):
        # Remove end-of-line comments
        line = re.sub(r'//.*$', '', line)
        # Remove /* */ comments if they're contained within a line
        line = re.sub(r'/\*.*?\*/', '', line)
        return line
    
    # Function to extract just the code part (without comments) for comparison
    def extract_code_part(line):
        # Strip comments
        code_only = strip_line_comments(line)
        # Remove whitespace and tabs
        return ''.join(code_only.replace('\t', '').split())
    
    # Generate a visual diff
    benign_lines = benign_code.splitlines()
    vuln_lines = vulnerable_code.splitlines()
    
    differ = difflib.Differ()
    diff = list(differ.compare(benign_lines, vuln_lines))
    
    formatted_diff = []
    i = 0
    while i < len(diff):
        line = diff[i]
        line_content = line[2:]
        # Check if the line is a removed line
        if line.startswith('- '):  # Line in benign
            # Look ahead for a corresponding vulnerable line
            if (i + 1 < len(diff) and diff[i + 1].startswith('+ ')):
                # Extract code parts (without comments and whitespace) for comparison
                benign_code_part = extract_code_part(line_content)
                vuln_code_part = extract_code_part(diff[i + 1][2:])
                
                # If code parts are identical (ignoring comments and whitespace)
                if benign_code_part == vuln_code_part:
                    # If only whitespace or comments differ, use the benign version
                    formatted_diff.append(f"   {line_content}")
                    i += 2  # Skip the next line since we've handled it
                    continue
            elif (i + 2 < len(diff) and diff[i + 1].startswith('?') and diff[i + 2].startswith('+ ')):
                # Extract code parts (without comments and whitespace) for comparison
                benign_code_part = extract_code_part(line_content)
                vuln_code_part = extract_code_part(diff[i + 2][2:])
                
                # If code parts are identical (ignoring comments and whitespace)
                if benign_code_part == vuln_code_part:
                    # If only whitespace or comments differ, use the benign version
                    formatted_diff.append(f"   {line_content}")
                    i += 3  # Skip the next line since we've handled it
                    continue
            # Check if the line is empty
            if line_content == '':
                formatted_diff.append(f"   {line_content}")
                i += 1
                continue
            formatted_diff.append(f"[REMOVED] {line_content}")
        elif line.startswith('+ '):  # Line in vulnerable
            # Check if the line is empty
            if line_content == '':
                formatted_diff.append(f"   {line_content}")
                i += 1
                continue
            formatted_diff.append(f"[ADDED] {line_content}")
        elif line.startswith('  '):  # Common lines
            formatted_diff.append(f"   {line_content}")
        # Skip the '?' lines from differ
        i += 1
            
    code_diff = '\n'.join(formatted_diff)
    
    # Check if the codes are actually different - do a more sophisticated comparison
    # to ignore both whitespace differences and comments
    def normalize_code(code):
        # Remove comments (both // and /* */)
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Remove whitespace
        code = re.sub(r'\s+', '', code)
        return code
    
    benign_normalized = normalize_code(benign_code)
    vulnerable_normalized = normalize_code(vulnerable_code)
    
    is_different = benign_normalized != vulnerable_normalized
    
    return {
        "code_diff": code_diff,
        "is_different": is_different
    }

def _build_categories_text_short() -> str:
    categories = load_vul_categories_from_json()
    lines = [f"- {vul_id}: {getattr(v, 'name', vul_id)}" for vul_id, v in categories.items()]
    return "Available Vulnerability Categories:\n" + "\n".join(lines)

def _compose_prompt_for_selector(code: str, categories_block: str) -> str:
    return (
        "You are a classifier. Given the code and its description, select the most suitable vulnerability category to inject.\n\n"
        f"Code Description:\n\n\n"
        f"Code:\n{code}\n\n"
        f"{categories_block}\n\n"
        "Answer with the single best category ID only."
    )

def _normalize_vul_id(raw: str, available: dict) -> str | None:
    """Extract and normalize vulnerability ID from model response (e.g. '79', 'CWE-79', 'CWE-476')."""
    raw = str(raw).strip()
    # Strip CWE- prefix
    if raw.upper().startswith("CWE-"):
        raw = raw[4:].strip()
    # Take first token in case of extra text
    tok = raw.split()[0] if raw else ""
    if tok in available:
        return tok
    # Try extracting CWE number from anywhere in the response
    match = re.search(r"CWE-?(\d+)", raw, re.IGNORECASE)
    if match and match.group(1) in available:
        return match.group(1)
    match = re.search(r"\b(\d+)\b", raw)
    if match and match.group(1) in available:
        return match.group(1)
    return None


def vulnInjectID_selector(
    benign_code: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Selects the most suitable vulnerability category via an OpenAI-compatible API.

    Configure via environment variables or kwargs:
    - VUL_SELECTOR_API_BASE_URL / base_url: API base URL (default: https://api.openai.com/v1)
    - VUL_SELECTOR_API_KEY / api_key: API key (falls back to OPENAI_API_KEY)
    - VUL_SELECTOR_MODEL / model: Model name (default: gpt-4o-mini)
    """
    try:
        available = load_vul_categories_from_json()
        categories_block = _build_categories_text_short()
        prompt = _compose_prompt_for_selector(benign_code, categories_block)

        client = OpenAI(
            base_url=base_url or os.environ.get("VUL_SELECTOR_API_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key or os.environ.get("VUL_SELECTOR_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
        )
        model_name = model or os.environ.get("VUL_SELECTOR_MODEL", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
            temperature=0,
        )
        content = response.choices[0].message.content
        vul_id = _normalize_vul_id(content, available)

        if vul_id is None:
            # Fallback: pick first available if parse failed
            vul_id = next(iter(available.keys()))

        return {"vul_inject_id": vul_id}
    except Exception as e:
        raise RuntimeError(f"vulnInjectID_selector failed: {e}")

def vulnInjectID_selector_probabilistic(benign_code: str, probabilities_path: str = "./vulnerability_probabilities.json") -> dict:
    """
    Select a vulnerability category ID at random using probabilities defined in a JSON file.

    The JSON file must map string CWE keys (e.g., "CWE-79") to float probabilities.
    This function strips the "CWE-" prefix to return the raw ID used by the knowledge base.

    Args:
        benign_code (str): Unused; kept for interface compatibility.
        probabilities_path (str): Absolute path to the JSON file with probabilities.

    Returns:
        dict: {"vul_inject_id": <ID>} sampled according to the provided probabilities.
    """
    import random

    # Load available categories and probability map
    available_vul_categories = load_vul_categories_from_json()

    try:
        with open(probabilities_path, "r", encoding="utf-8") as f:
            prob_map = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load probabilities file '{probabilities_path}': {e}")

    # Build aligned lists of IDs (without CWE- prefix) and weights, keeping only known categories
    ids = []
    weights = []
    for cwe_key, weight in prob_map.items():
        if not isinstance(weight, (int, float)) or weight <= 0:
            continue
        cwe_id = str(cwe_key)
        if cwe_id.startswith("CWE-"):
            cwe_id = cwe_id.replace("CWE-", "")
        if cwe_id in available_vul_categories:
            ids.append(cwe_id)
            weights.append(float(weight))

    # Fallback to uniform over available categories if nothing usable
    if not ids or sum(weights) <= 0:
        ids = list(available_vul_categories.keys())
        weights = [1.0] * len(ids)

    # Sample one ID using weights
    choice = random.choices(ids, weights=weights, k=1)[0]
    return {
        "vul_inject_id": choice
    }


def route_from_diff_checker(args):
    """
    Routes to the appropriate next agent based on whether the vulnerable code is different from benign code.
    
    Args:
        args: The output from the CodeDiffChecker agent
        
    Returns:
        str: The name of the next agent to execute
    """
    if args.is_different:
        return "CriticalAnalyzer"
    else:
        return "VulInjector"  # Go back and try again

def route_from_critical_analyzer(args):
    """
    Routes to the appropriate next agent based on whether the code modifications validly introduce
    the intended vulnerability.
    
    Args:
        args: The output from the CriticalAnalyzer agent
        
    Returns:
        str: The name of the next agent to execute
    """
    if args.modification_valid:
        return "end"  # End the workflow
    else:
        return "VulInjector"  # Go back and try again

def route_from_benign_code_analyzer(args):
    """
    Routes to the appropriate next agent based on whether the input vulnerability category is available.
    
    Args:
        args: The output from the BenignCodeAnalyzer agent
        
    Returns:
        str: The name of the next agent to execute
    """
    available_vul_categories = load_vul_categories_from_json()
    if not args.vul_inject_id in available_vul_categories:
        return "VulnInjectIDSlector" # Go to the VulnInjectIDSlector to select a new vulnerability category
    else:
        return "VulInfoLoader" # Go to the VulInfoLoader to load the vulnerability information

def run_cpp_check_analysis(vulnerable_code: str, vul_inject_id: str, cppcheck_path: str = "static_tools/cppcheck/bin/cppcheck") -> dict:
    """
    Run static analysis on the code using cppcheck to identify potential vulnerabilities.

    Args:
        vulnerable_code (str): The code to analyze
        vul_inject_id (str): The vulnerability ID to check for
        cppcheck_path (str): Path to the cppcheck executable (relative to AVIATOR root or absolute)

    Returns:
        dict: Results of the static analysis including any detected CWE IDs
    """
    # Resolve cppcheck path: relative paths are from AVIATOR root
    resolved = Path(cppcheck_path)
    if not resolved.is_absolute():
        resolved = _AVIATOR_ROOT / resolved
    if not resolved.is_file():
        fallback = shutil.which("cppcheck")
        resolved = Path(fallback) if fallback else resolved
    if not resolved.is_file():
        raise FileNotFoundError(
            f"cppcheck not found at '{cppcheck_path}' (resolved: {resolved}). "
            "Install via: ./scripts/setup_aviator.sh or add cppcheck to PATH."
        )
    cppcheck_path = str(resolved)

    # Create a temporary file to hold the code
    with tempfile.NamedTemporaryFile(suffix='.cpp', delete=False) as temp_file:
        temp_file.write(vulnerable_code.encode('utf-8'))
        temp_file_path = temp_file.name

    try:
        # Run cppcheck with all checks enabled and output as JSON
        cmd = [
            cppcheck_path,
            '--enable=all',
            '--xml',
            '--template="{file}:{line}:{message} [{id}]"',
            temp_file_path
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # Parse the output to extract CWE IDs and error messages
        static_analysis_errors = []
        cwe_ids = []

        # Parse the output line by line
        output = stderr.decode('utf-8')
        for line in output.split('\n'):
            if line.strip():
                # Extract CWE IDs
                cwe_match = re.search(r'\[CWE-(\d+)\]', line)
                if cwe_match:
                    cwe_id = f"CWE-{cwe_match.group(1)}"
                    if cwe_id not in cwe_ids:
                        cwe_ids.append(cwe_id)

                # Extract error details
                error_match = re.search(r'(\w+\.cpp):(\d+):(.+) \[(.+)\]', line)
                if error_match:
                    file_path, line_num, message, error_id = error_match.groups()
                    static_analysis_errors.append({
                        'file': os.path.basename(file_path),
                        'line': int(line_num),
                        'message': message.strip(),
                        'error_id': error_id
                    })

        return {
            "cwe_ids": cwe_ids,
            "static_analysis_errors": static_analysis_errors
        }

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

def route_from_vulnerability_verifier(args):
    """
    Routes to the appropriate next agent based on whether the vulnerability was correctly introduced
    according to the VulnerabilityVerifier.
    
    Args:
        args: The output from the VulnerabilityVerifier agent
        
    Returns:
        str: The name of the next agent to execute
    """
    if args.is_correctly_vulnerable:
        return "end"  # End the workflow with successful validation
    else:
        return "VulnerabilityFixer"  # Go back and try to fix the vulnerability

def route_from_vulnerability_verifier2(args):
    """
    Routes to the appropriate next agent based on whether the vulnerability was correctly introduced
    according to the VulnerabilityVerifier.
    
    Args:
        args: The output from the VulnerabilityVerifier agent
        
    Returns:
        str: The name of the next agent to execute
    """
    if args.is_correctly_vulnerable:
        return "end"  # End the workflow with successful validation
    else:
        return "VulInjector"  # Go back and try again with vulnerability injection

def route_from_diff_checker_v2(args):
    """
    Enhanced routing after CodeDiffChecker:
    - If is_different is False, go to IdenticalCodeVulInjector.
    - If is_different is True, go to VulDiffChecker.
    """
    if hasattr(args, 'is_different'):
        if args.is_different:
            return "VulDiffChecker"
        else:
            return "IdenticalCodeVulInjector"
    # Fallback to old behavior if attribute missing
    return route_from_diff_checker(args)