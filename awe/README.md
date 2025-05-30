# Awe (Agentic-AI Workflow Engine)

<p align="center">
  <picture>
    <img alt="Awe Logo" src="https://github.com/user-attachments/assets/8ca4a31a-041c-4908-9c17-4358ca3e0a92" style="max-width: 100%;">
  </picture>
  <br/>
  <br/>
</p>


## Overview
Awe (Agentic-AI Workflow Engine) is a low-code python library to build and execute AI agentic workflows out of the box. Each agent performs a specific task and conditionally triggers subsequent agents based on its output. Currently, it supports both AI agents and tool agents that execute Python code.

## Highlights
- ▶️ Low-code/No-code: Easily create and run complex workflows without extensive coding.
- 🤖 AI & Tool Agents: Support for intelligent AI agents and tool agents.
- 📋 Comprehensive Logging: Monitor and analyze workflow execution through detailed logging.
- 💾 Experiment Reproducibility: Automatically save execution history and outputs for easy replication.
- 🔄 Error Recovery: Support for re-execution of failed agents.
- ⚙️ Extensible & Customizable: Easily extend and adapt workflows to meet specific requirements.
- 🐍 Build with Python and pydantic: modular and robust library architecture.

## Installation

1) Clone this repository:
```console
git clone https://github.com/AmL-Dev/vul-code-gen/tree/main/awe.git
```

2) Install Dependencies

To create a conda environment:
```console
conda env create -f environment.yml
```

*In case of issues, please refer to the list of dependencies [below](#dependencies).*

## Quick Start

### Create a workflow

Here is a guide on how to create a workflow using configuration files:

In a single `workflow_name.json` file, define the following:
```python
    {
        "llms": [
            ...
        ],
        "agent_arguments": [
            ...
        ],  
        "agents": [
            ...
        ],
        "edges": [
            ...
        ]
    }
```

- ✨ **LLMs** to be used by agents:
```python

    "llms": [
        {
            "id": "unique llm id",
            "llm": {
                "type": "LLM wrapper type:
                - HFpipeline (transformers pipeline)
                - DummyTestLLM (dummy LLM for testing purposes)",
                "llm_path": "Path to the LLM model",
                "system_prompt": "System prompt for the LLM"
            }
        }
    ]
```
- ⤵️ **Input** and **output** argument **schemas** used by agents:
```python
    "agent_arguments": [
        {
            "type": "Name your class",
            "fields": {
                "custom_field_name": {"type": "field type (custom type must inherit from awe.CustomTypeBase and implement __str__ method)", "description": "Field description"},
                "custom_field_name": {"type": "field type", "description": "Field description"}
            }
        }
    ]
```
- 🤖 **Agents** to be used:
```python
    "agents": [
        {
            "type": "Type of agent:
            - AIAgent (for AI agents)
            - RAGAgent (for RAG agents)
            - FunctionAgent (for tool agents)",
            "name_id": "Unique id for the agent",
            "input_schema": "Name of the input schema",
            "output_schema": "Name of the output schema",
            "propagate_input_args": true|false (wether the input arguments should be propagated to the next agent),
            **kwargs for the agent type
        }
    ]
```

→ ✨ **AIAgent** executes an LLM with a given prompt:
```python
    {
        "type": "AIAgent",
        ...
        "llm_id": "id of the LLM to be used",
        "prompt": "LLM prompt (string or path.to.python.file.PROMPT_TEMPLATE_NAME). Can hold placeholders for the input arguments. (Ensure expected placeholders are included in the input_schema)",
        "max_output_tokens": nb of tokens to generate
    },
```
→ 🛢✨ **RAGAgent** executes a RAG call:
```python
    {
        "type": "RAGAgent",
        ...
        "llm_id": "id of the LLM to be used",
        "prompt": "LLM prompt (string or path.to.python.file.PROMPT_TEMPLATE_NAME). Can hold placeholders for the input arguments. (Ensure expected placeholders are included in the input_schema and retrieval_placeholder_key)",
        "rag": {
            "type": "path.to.module.implementing.RAG (must inherit from awe.RAG)",
            "embedding_model_path": "Path to the embedding model",
            "embedder_cache_path": "Path to the embedder cache",
            "knowledge_base_path": "Path to the indexed knowledge base"
        },
        "retrieval_param_mapping": {"retrieval_query": "name of the input argument to be used in the retrieval query"},
        "retrieval_placeholder_key": " name of the placeholder in the prompt where to insert retrieved context.",
        "top_k": nb of results to retrieve,
        "max_output_tokens": nb of tokens to generate
    }
```

→ 🔧 **FunctionAgent** executes a function call:
```python
    {
        "type": "FunctionAgent",
        ...
        "call_function": "path.to.module.function_name which returns a dictionary of attributes (Ensure that the required parameters are included in the input_schema)"
    }
```

- 🔀 **Transitions** between agents (always start with "start" and end with "end"):
```python
    "edges": [
        {
            "type": "SimpleEdge",
            "sourceAgent": "Name of the current agent to be executed",
            "targetAgent": "Name of the next agent to be executed"
        },
        {
            "type": "ConditionalEdge",
            "sourceAgent": "Name of the current agent to be executed",
            "condition_fn": "path.to.condition_function which returns the name of the next agent to be executed or 'end' if the workflow is finished (Ensure that the required parameters are included in the output_schema of the current agent)"
        }
    ]
```

### Execute a workflow

```python
from awe import load_and_run_workflow

workflow_path = "path/to/workflow.json"
workflow_input = {"input_argument_1": "value_1", "input_argument_2": "value_2"}

final_output = load_and_run_workflow(
    json_path=workflow_path, 
    initial_args=workflow_input, 
    max_retries=nb retry on failed agents,
    save_run_path="path/to/save/run/history")
```

### Quick Start Example

For quick start you can use the example workflow in the `examples/customer_support` folder.
It represent a toy customer support workflow that:
1. Classifies a ticket into a category
2. Generates a response using a RAG agent
3. Checks if the ticket needs to be escalated
4. Adds a timestamp to the response

<p align="center">
  <img src="https://github.com/user-attachments/assets/da9d12f5-c809-46e3-881d-fe6d1f66af02" alt="Customer Support Ticket Workflow Illustration." width=150/>
</p>

To run the workflow in `examples/customer_support`:
1. Install dependencies and connect to Hugging Face:
```console
pip install -r requirements.txt
huggingface-cli login
```

2. Create the knowledge base:
Update the path to the parent directory of awe at the top of the `create_knowledge_base.py` file:
```console
python create_knowledge_base.py
```
3. Run the workflow using the Awe engine:
```console
python customer_support_run.py
```

*Disclaimer: This example workflow is provided solely for demonstration purposes. It does not reflect any actual business implementation and should not be deployed in a production environment without appropriate modifications and testing.*

## Library Structure

The library is organized into the following main modules:

- `instantiate_workflow.py`: Contains functions for loading and running workflows.
- `AgenticWorkflow.py`: Defines the `AgenticWorkflow` class for managing and executing workflows. It contains the following attributes:
    - `_start_node`: The starting node of the workflow.
    - `_end_node`: The ending node of the workflow.
    - `_nodes`: A dictionary of all the nodes in the workflow.
    - `_edges`: A dictionary of all the edges in the workflow.
    - `_llms`: A list of all the LLMs in the workflow.
    - `_history`: The history of the workflow execution.

    It also contains the following methods:
    - `add_agent`: Add an agent to the workflow.
    - `add_simple_edge`: Add a simple edge to the workflow.
    - `add_conditional_edge`: Add a conditional edge to the workflow.
    - `run`: Run the entire workflow from the start node to the end node.
    - `add_llm`: Add an LLM to the workflow.
    - `get_llms`: Get the list of LLMs in the workflow.
    - `getRunHistory`: Get the history of the workflow execution.
    - `clearRunHistory`: Clear the history of the workflow execution.
    
- `Agent.py`: Defines the abstract `Agent` class for managing and executing agents. An agent is an entity that takes an input and returns an output. All types of agents inherit from the `Agent` class.

    It contains the following attributes:
    - `name_id`: The unique identifier for the agent.
    - `input_schema`: The input schema for the agent.
    - `output_schema`: The output schema for the agent.
    - `propagate_input_args`: Whether to propagate the input arguments to the next agent.
    
    To execute an agent, it must implement the `__call__` method.<br>
    The following agents are available:
    - `AIAgent`: An AI agent that uses an LLM to generate an output.
    - `RAGAgent`: A RAG (Retrieval-Augmented Generation) agent that inherits from `AIAgent` and uses a RAG to generate an output.
    - `FunctionAgent`: A tool agent that uses a python function to generate an output.

- `RAG.py`: Defines the abstract `RAG` class for managing and executing RAGs.
    It contains the following attributes:
    - `embedding_model_path`: The path to the embedding model.
    - `embedder_cache_path`: The path to the embedder cache.
    - `knowledge_base_path`: The path to the knowledge base.
    - `top_k`: The number of results to retrieve.
    - `retrieval_param_mapping`: The mapping of the retrieval parameters to the input arguments.
    - `retrieval_placeholder_key`: The placeholder key for the retrieved context.

    Child classes must implement the following methods:
    - `retrieve_relevant`: Retrieve the top k results from the knowledge base.
    - `index`: Index the knowledge base.
    - `_load_embedding_model`: Load the embedding model.
    - `_load_db`: Load the knowledge base.

- `LLM.py`: Defines the `LLM` class as wrapper around different LLM providers.
    It contains the following attributes:
    - `system_prompt`: The system prompt for the LLM.

    Child classes must implement the following methods:
    - `chat`: Full logic to get the LLM's response for a given user prompt.
    - `_create_message`: Create the message for the LLM.
    - `_send_message`: Send the message to the LLM.
    - `_get_response`: Get the response from the LLM.

    The following LLM providers are available:
    - `HFpipeline`: Use a pipeline from the HuggingFace transformers library.
    - `DummyTestLLM`: A dummy LLM for testing purposes.

- `Edge.py`: Defines the abstract `Edge` class for managing and executing edges.
    It contains the following attributes:
    - `source_agent`: The source agent of the edge.

    Child classes must implement the following methods:
    - `get_next_node`: Get the next node of the edge.

    The following edge types are available:
    - `SimpleEdge`: A simple edge that transitions to the next node.
    - `ConditionalEdge`: A conditional edge that transitions to the next node based on a function.

- `History.py`: Defines the `History` class for storing the history of the workflow execution.
    It contains the following attributes:
    - `records`: The list of history records.

    It also contains the following methods:
    - `add_record`: Add a record to the history.
    - `to_json`: Convert the history to a JSON string.
    - `clear`: Clear the history.

- `custom_types.py`: Defines the abstract `CustomTypeBase` helper class to handle custom types in the input and output arguments (useful for JSON configuration files).


## Built With
- [Python (3.13.1)](https://www.python.org/)

### Dependencies
- [transformers (4.50.1)](https://pypi.org/project/transformers/)
- [accelerate (1.5.2)](https://pypi.org/project/accelerate/)
- [pydantic (2.10.6)](https://docs.pydantic.dev/latest/)
- [openai (1.68.2)](https://pypi.org/project/openai/)