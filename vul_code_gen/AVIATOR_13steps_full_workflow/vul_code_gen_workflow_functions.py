"""Implementation of Agents function
"""

import re
import difflib
import subprocess
import tempfile
import json
import os
import shutil
from pathlib import Path

from vul_code_gen.knowledge_base.vulnerability_categories import load_vul_categories_from_json

# AVIATOR repo root (parent of vul_code_gen)
_AVIATOR_ROOT = Path(__file__).resolve().parent.parent.parent

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