#########################################################################
# 1) Sign in to Hugging Face by running this command: hf auth login
import os
import sys
from pathlib import Path

# Ensure awe package is importable (no PYTHONPATH needed when run from repo)
_src = Path(__file__).resolve().parent.parent.parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
#########################################################################

from awe import load_and_run_workflow

script_dir = os.path.dirname(os.path.abspath(__file__))
# Sample support ticket
ticket = {
    "ticket_id": "T12345",
    "customer_name": "Jane Smith",
    "ticket_content": "I've been trying to login to my account for the past 2 days, but keep getting an 'Invalid credentials' error even though I'm sure my password is correct. I've tried resetting my password twice with no success."
}

# Run the workflow
result = load_and_run_workflow(
    json_path=os.path.join(script_dir, "customer_support_workflow.json"),
    initial_args=ticket,
    max_retries=2,
    save_run_path=os.path.join(script_dir, "saved_run/"),
    run_name="customer_support_test.out"
)

print(result)
