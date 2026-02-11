#########################################################################
# Sign in to Hugging Face by running this command: hf auth login
#########################################################################
import os
import shutil
import sys
from pathlib import Path

# Makes the project root importable (awe, vul_code_gen)
_src = Path(__file__).resolve().parent.parent
# AVIATOR repo root (parent of vul_code_gen)
_AVIATOR_ROOT = _src
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import subprocess
import tempfile
import json
import re
from typing import List, Tuple
from codebleu import calc_codebleu
import pandas as pd
import argparse
import logging
import html

from vul_code_gen.dataset_utils import load_primevul_vul_pairs, load_sard100_vul_pairs, load_formai_pairs

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

### ESBMC Functions

def extract_violation_details(text):
    """
    Extracts the violated property details from ESBMC output.

    Args:
        text (str): The ESBMC output containing violation details
        
    Returns:
        dict: A dictionary containing the extracted details
    """
    # Define the regular expression pattern
    pattern = re.compile(
        r'Violated property:\s*\n'
        r'\s*file\s+(?P<file>\S+)\s+line\s+(?P<line>\d+)\s+column\s+(?P<column>\d+)\s+function\s+(?P<function>\w+)\s*\n'
        r'\s*(?P<violation_type>[^\n]+)\s*\n'
        r'\s*(?P<description>[^\n]+)',
        re.MULTILINE
    )

    # Search for the pattern in the provided text
    match = pattern.search(text)
    if match:
        # Extract details using named groups
        details = match.groupdict()
        return details
    else:
        return None

# Mapping of keywords to vulnerability categories
vulnerability_mapping = {
    r"Division by zero": "DZ",
    r"Arithmetic overflow": "AO",
    r"\bscanf\("  : "BO",  # Buffer overflow on scanf()/fscanf()
    r"\bfscanf\(" : "BO",
    r"array bounds": "ABV",
    r"NULL pointer": "DFN",
    r"forgotten memory": "DFF",
    r"invalid pointer": "DFI",
    r"dereference.*array bounds": "DFA",
}

def classify_vulnerability(esbmc_output):
    vulnerability_classes = set()
    # Iterate over mapping items
    for pattern, vuln_class in vulnerability_mapping.items():
        if re.search(pattern, esbmc_output, re.IGNORECASE):
            vulnerability_classes.add(vuln_class)
    # If no known patterns matched, classify as Other (O)
    if not vulnerability_classes:
        vulnerability_classes.add("O")
    return vulnerability_classes

def run_esbmc_on_code(code: str, unwind: int = 101, timeout: int = 120) -> tuple[bool, str, bool, dict]:
    """
    Runs ESBMC on a given C++ code snippet and returns vulnerability status and output.

    Args:
        code (str): The C++ code to verify.
        unwind (int): Number of loop unwindings (default is 10).

    Returns:
        tuple[bool, str, bool]: A tuple containing:
            - bool: True if code is vulnerable (VERIFICATION SUCCESSFUL not found), False otherwise
            - str: The complete output from ESBMC
            - bool: True if there is a parsing error, False otherwise
            - dict: A dictionary containing the extracted details
    """
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w+", delete=False) as tmp_file:
        tmp_file.write(code)
        tmp_file.flush()
        tmp_file_name = tmp_file.name

    # Resolve ESBMC path: relative to AVIATOR root or from PATH
    esbmc_path = _AVIATOR_ROOT / "static_tools" / "esbmc" / "bin" / "esbmc"
    if not esbmc_path.is_file():
        fallback = shutil.which("esbmc")
        esbmc_path = Path(fallback) if fallback else esbmc_path
    if not esbmc_path.is_file():
        raise FileNotFoundError(
            f"ESBMC not found. Install via: ./scripts/setup_aviator.sh or add esbmc to PATH."
        )
    cmd = [str(esbmc_path)]
    if "#include <mysql/mysql.h>" in code:
        mysql_include = Path.home() / "mysql" / "include"
        if mysql_include.is_dir():
            cmd.append(f"-I{mysql_include}")
        else:
            logger.warning(f"Install MySQL for ESBMC to work correctly on all test cases. Include directory not found: {mysql_include}")
    cmd.extend([tmp_file_name, "--overflow", "--memory-leak-check", "--timeout", str(timeout), "--unwind", str(unwind), "--multi-property", "--no-unwinding-assertions"])
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        output = result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        output = e.stdout + e.stderr

    is_parsing_error = "ERROR: PARSING ERROR" in output
    is_timeout = "ERROR: Timed out" in output
    violation_details = extract_violation_details(output)

    is_vulnerable = "VERIFICATION FAILED" in output
    if not is_vulnerable and is_timeout and violation_details != None:
        is_vulnerable = violation_details["violation_type"] != None

    return output, is_vulnerable, is_parsing_error, is_timeout, violation_details


def check_vulnerable_esbmc(code: str, max_unwind: int = 21, timeout: int = 120):
    """
    Runs ESBMC on a given C++ code snippet to check if it is vulnerable. 
    Progressively increases the depth of search if the code is not vulnerable.

    Args:
        code (str): The C++ code to verify.
        max_unwind (int): Maximum number of loop unwindings (default is 21).
    """
    unwind = 1
    while unwind <= max_unwind:
        output, is_vulnerable, is_parsing_error, is_timeout, violation_details = run_esbmc_on_code(code, unwind=unwind, timeout=timeout)
        if (is_vulnerable and violation_details != None) or is_parsing_error or is_timeout:
            return output, is_vulnerable, is_parsing_error, is_timeout, violation_details
        unwind += 10
    return output, is_vulnerable, is_parsing_error, is_timeout, violation_details

### CodeBLEU Functions

def fix_missing_define_hash(code: str) -> str:
    """Fixes missing # in #define statements that don't have the # prefix."""
    # Pattern to match standalone 'define' word that is not preceded by #
    # This handles cases like: define, \ndefine, \tdefine, define\n, define\t, etc.
    # Uses word boundaries to ensure we only match standalone "define", not parts of other words like "redefined"
    pattern = r'(?<!#)\bdefine\b'
    return re.sub(pattern, '#define', code)

def fix_missing_include_hash(code: str) -> str:
    """Adds missing # for include directives like 'include <stdlib.h>'. Preserves indentation."""
    pattern = re.compile(r'(?m)^(?P<indent>\s*)include\b')
    return pattern.sub(r'\g<indent>#include', code)

def replace_unicode_spaces(code: str) -> str:
    """Replaces Unicode non-breaking space (\u00a0) and zero-width space (\u200b) with regular whitespace."""
    return code.replace('\u00a0', ' ').replace('\u200b', ' ')

def process_html_entities(code: str) -> str:
    """Processes HTML entities: removes backslashes before &, unescapes HTML, then escapes HTML."""
    # 1. Remove any leading backslashes before & characters
    # This handles cases like \& → &, \\\& → &, \\\\\& → &, etc.
    code = re.sub(r'\\+&', '&', code)
    
    # 2. Unescape HTML entities (e.g., &lt; → <, &amp; → &)
    code = html.unescape(code)
    
    return code

def fix_missing_includes(code: str) -> str:
    """Adds missing standard includes when necessary based on function usage in the code."""
    # Check if malloc, free, calloc, realloc are used (need stdlib.h)
    stdlib_functions = ['malloc', 'free', 'calloc', 'realloc', 'exit', 'abort', 'atoi', 'atol', 'atof', 'NULL']
    needs_stdlib = any(func in code for func in stdlib_functions)
    
    # Check if printf, scanf, fprintf, fscanf, sprintf, sscanf are used (need stdio.h)
    stdio_functions = ['printf', 'scanf', 'fprintf', 'fscanf', 'sprintf', 'sscanf', 'getchar', 'putchar', 'gets', 'puts']
    needs_stdio = any(func in code for func in stdio_functions)
    
    # Add includes if needed and not already present
    includes_to_add = []
    
    if needs_stdlib and '#include <stdlib.h>' not in code:
        includes_to_add.append('#include <stdlib.h>')
    
    if needs_stdio and '#include <stdio.h>' not in code:
        includes_to_add.append('#include <stdio.h>')
    
    # If we need to add includes, find the best place to insert them
    if includes_to_add:
        # Look for existing includes to place new ones after them
        lines = code.split('\n')
        insert_index = 0
        
        # Find the last include statement
        for i, line in enumerate(lines):
            if line.strip().startswith('#include'):
                insert_index = i + 1
        
        # Insert the new includes after existing includes
        for include in includes_to_add:
            lines.insert(insert_index, include)
            insert_index += 1
        
        return '\n'.join(lines)
    
    return code

def escape_escapes_in_strings(code: str) -> str:
    """
    Escape unescaped newline, carriage return, and tab characters and their escape sequences
    inside single- or double-quoted string literals by replacing them with '\\n', '\\r', '\\t'
    (or double-escaped for backslash sequences). Other parts of the code remain unchanged.

    Supports C-style single-line (//...) and multi-line (/*...*/) comments.
    Inside comment regions, no escaping is performed.
    """
    def _is_escaped(buffer: list[str]) -> bool:
        """Return True if the last backslash in buffer is itself escaped."""
        count = 0
        for ch in reversed(buffer):
            if ch == "\\":
                count += 1
            else:
                break
        return (count % 2) == 1

    out: List[str] = []
    in_str = False
    in_block_comment = False
    delim = ""
    i = 0
    n = len(code)

    while i < n:
        # Inside a block comment: copy until '*/'
        if in_block_comment:
            if code.startswith("*/", i):
                out.extend(["*", "/"])
                i += 2
                in_block_comment = False
            else:
                out.append(code[i])
                i += 1
            continue

        # Not in block comment or string
        if not in_str:
            # Single-line comment
            if code.startswith("//", i):
                out.extend(["/", "/"])
                i += 2
                while i < n and code[i] != "\n":
                    out.append(code[i])
                    i += 1
                continue
            # Block comment start
            if code.startswith("/*", i):
                out.extend(["/", "*"])
                i += 2
                in_block_comment = True
                continue
            # String literal start
            ch = code[i]
            if ch in ('"', "'"):
                in_str = True
                delim = ch
                out.append(ch)
                i += 1
                continue
            # Default: copy
            out.append(ch)
            i += 1
            continue

        # Inside a string literal
        ch = code[i]

        # Handle CRLF inside the literal: \r\n -> \\r\\n
        if ch == "\r" and i + 1 < n and code[i + 1] == "\n":
            out.extend(["\\", "r", "\\", "n"])
            i += 2
            continue

        # Raw carriage return -> \\r
        if ch == "\r":
            out.extend(["\\", "r"])
            i += 1
            continue

        # Raw newline -> \\n
        if ch == "\n":
            out.extend(["\\", "n"])
            i += 1
            continue

        # Raw tab -> \\t
        if ch == "\t":
            out.extend(["\\", "t"])
            i += 1
            continue

        # End of string literal
        if ch == delim:
            in_str = False
            out.append(ch)
            i += 1
            continue

        # Unescaped backslash-escape for n, r, t -> double-escape
        if ch == "\\" and i + 1 < n and code[i + 1] in ("n", "r", "t"):
            if not _is_escaped(out):
                out.extend(["\\", "\\", code[i + 1]])
                i += 2
                continue

        # Other backslash-escape -> copy verbatim
        if ch == "\\" and i + 1 < n:
            out.append(ch)
            out.append(code[i + 1])
            i += 2
            continue

        # Anything else inside string
        out.append(ch)
        i += 1

    return "".join(out)

def apply_all_syntax_fixes(code: str) -> str:
    """Applies all syntactic fixes to the code in the correct order."""
    # 1. Process HTML entities (remove backslashes before &, unescape, then escape)
    code = process_html_entities(code)
    # 2. Unicode space replacement
    code = replace_unicode_spaces(code)
    # 3. Fix missing # for include directives
    code = fix_missing_include_hash(code)
    # 4. Fix missing # for define directives
    code = fix_missing_define_hash(code)
    # 5. Add missing includes when necessary
    code = fix_missing_includes(code)
    # 6. Escape escapes in string
    code = escape_escapes_in_strings(code)
    return code


def format_cpp_code(code: str, style: str = "llvm") -> str:
    """Formats C++ code using clang-format."""
    process = subprocess.run(
        ["clang-format", f"--style={style}"],
        input=code,
        text=True,
        capture_output=True,
        check=True
    )
    return process.stdout

def measure_codebleu_score(generated_vuln_code: str, expected_vuln_code: str) -> float:
    """Measures CodeBLEU score between generated and expected vulnerable code."""
    generated_vuln_code = format_cpp_code(generated_vuln_code)
    expected_vuln_code = format_cpp_code(expected_vuln_code)
    score = calc_codebleu(
        [expected_vuln_code],
        [generated_vuln_code],
        lang="cpp", 
        weights=(0.25, 0.25, 0.25, 0.25),
        tokenizer=None  
    )
    return score['codebleu']

def evaluate_generated_code(data_to_test_path: str, reference_code_pair_df: pd.DataFrame, 
                          run_esbmc: bool = True, run_codebleu: bool = True) -> Tuple[float, int, int]:
    """
    Process JSONL file to compute CodeBLEU scores and/or vulnerability statistics.
    
    Args:
        data_to_test_path: Path to the JSONL file
        reference_code_pair_df: DataFrame containing reference code pairs
        run_esbmc: Whether to run ESBMC vulnerability detection
        run_codebleu: Whether to compute CodeBLEU scores
        
    Returns:
        Tuple containing:
        - Average CodeBLEU score (or 0 if not computed)
        - Count of vulnerable cases (or 0 if not computed)
        - Total number of cases
    """
    total_score = 0
    vulnerable_count = 0
    parsing_error_count = 0
    timeout_count = 0
    total_count = 0

    with open(data_to_test_path, 'r') as f:
        for line in f:
            data = json.loads(line)
            generated_vuln_code = data['vulnerable_code']
            # Apply all syntactic fixes
            generated_vuln_code = apply_all_syntax_fixes(generated_vuln_code)
            
            if run_codebleu:
                expected_vuln_code = reference_code_pair_df[
                    reference_code_pair_df['vulnerable_hash'] == data['vulnerable_hash']
                ]['vulnerable'].iloc[0]
                expected_vuln_code = apply_all_syntax_fixes(expected_vuln_code)
                score = measure_codebleu_score(generated_vuln_code, expected_vuln_code)
                total_score += score
            else:
                score = None
            
            if run_esbmc:
                output, is_vulnerable, is_parsing_error, is_timeout, violation_details = check_vulnerable_esbmc(generated_vuln_code, max_unwind=101, timeout=180)
                if is_vulnerable and not is_parsing_error:
                    vulnerable_count += 1
                elif is_parsing_error:
                    parsing_error_count += 1
                if is_timeout:
                    timeout_count += 1
            else:
                is_vulnerable = is_parsing_error = violation_details = is_timeout = None
            
            # Log results for this case
            logger.info(f"CWE-{data['cwe_id']} (Hash: {data['vulnerable_hash']}):")
            if run_codebleu:
                logger.info(f"  CodeBLEU Score: {score:.4f}")
            if run_esbmc:
                logger.info(f"  Is Vulnerable: {is_vulnerable}")
                if is_parsing_error: logger.info(f"  Has Parsing Error: {is_parsing_error} \n    -> {output}")
                if is_timeout: logger.info(f"  Is Timeout: {is_timeout}")
                logger.info(f"  Violation Details: {violation_details}")
            logger.info("---")
            
            total_count += 1
    
    # Calculate average score
    avg_score = (total_score-parsing_error_count-timeout_count) / (total_count-parsing_error_count-timeout_count) if (total_count > 0 and run_codebleu) else 0
    
    # Log final statistics
    logger.info("\nFinal Statistics:")
    if run_codebleu:
        logger.info(f"Average CodeBLEU Score: {avg_score:.4f}")
        logger.info(f"Total Parsing Errors: {parsing_error_count}")
        logger.info(f"Total Timeouts: {timeout_count}")
    if run_esbmc:
        logger.info(f"Vulnerable Cases: {vulnerable_count}/{total_count} ({(vulnerable_count/total_count)*100:.2f}%)")
    
    return avg_score, vulnerable_count, total_count

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run vulnerability code generation workflow')
    parser.add_argument('--data_to_test_path', type=str, required=True,
                        help='Path to the PrimeVul dataset file')
    parser.add_argument('--reference_dataset_path', type=str, required=True,
                        help='Path to the PrimeVul dataset file')
    parser.add_argument('--dataset_type', type=str, choices=['sard100', 'primevul', 'formai'],
                    help='Type of dataset to load (sard100 or primevul)')
    parser.add_argument('--run_esbmc', action='store_true',
                       help='Run ESBMC vulnerability detection')
    parser.add_argument('--run_codebleu', action='store_true',
                       help='Compute CodeBLEU scores')
    args = parser.parse_args()

    # Load the dataset
    if args.dataset_type == 'primevul':
        reference_code_pair_df = load_primevul_vul_pairs(args.reference_dataset_path)
        if args.run_esbmc:
            args.run_esbmc = False
            logger.warning("ESBMC is not supported for PrimeVul dataset")
    elif args.dataset_type == 'sard100':
        reference_code_pair_df = load_sard100_vul_pairs(args.reference_dataset_path)
    elif args.dataset_type == 'formai':
        reference_code_pair_df = load_formai_pairs(args.reference_dataset_path)

    evaluate_generated_code(args.data_to_test_path, reference_code_pair_df, 
                          run_esbmc=args.run_esbmc, run_codebleu=args.run_codebleu)