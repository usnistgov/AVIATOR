#########################################################################
# 1) Sign in to Hugging Face by running this command: huggingface-cli login
#
##### 2) RUN #####
### Execute this script:
# PYTHONPATH=/path/to/parent/directory/of/awe python awe/examples/customer_support/customer_support_run.py 
### Alternatively, uncomment code below
# Set project location to be able to call project modules 
import sys
sys.path.append("/path/to/parent/directory/of/awe")
#########################################################################

from awe import load_and_run_workflow
import os
script_dir = os.path.dirname(__file__)
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
