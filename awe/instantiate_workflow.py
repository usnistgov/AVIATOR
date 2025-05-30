import json
from pydantic import Field, create_model
from inspect import signature
from typing import Callable, ForwardRef, Any
import ast
import importlib
import os

from awe.AgenticWorkflow import AgenticWorkflow
from awe.Agent import Agent, AgentArguments
from awe.LLMs import LLM
from awe.RAG import RAG
from awe.Edge import Edge, SimpleEdge
from awe.custom_types import CustomTypeBase


# Helper to collect all subclasses of a given base class.
def get_all_subclasses(base_class: any) -> dict:
    """
    Recursively collect all subclasses of a given base class, including indirect inheritance.
    
    Args:
        base_class (any): The base class to collect subclasses for.
    
    Returns:
        dict: A dictionary of subclass names to subclass objects.
    """
    # Get immediate subclasses
    subclasses = base_class.__subclasses__()
    
    # Dictionary to store all subclasses
    all_subclasses = {}
    
    for subclass in subclasses:
        # Add the immediate subclass
        all_subclasses[subclass.__name__] = subclass
        
        # Recursively get subclasses of this subclass
        nested_subclasses = get_all_subclasses(subclass)
        # Update our dictionary with nested subclasses
        all_subclasses.update(nested_subclasses)
    
    return all_subclasses


# A dictionary for common built-in types.
BUILTIN_TYPES = {
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "Any": Any,
    # Add more built-ins as needed.
}

def parse_type_string(type_str: str) -> ast.AST:
    """Parses a type string into an AST node for safe evaluation."""
    try:
        return ast.parse(type_str, mode='eval').body
    except SyntaxError:
        raise ValueError(f"Invalid type string syntax: {type_str}")

def resolve_type(type_str: str, available_classes: dict) -> any:
    """
    Resolve a type string to a Python type or a custom class, supporting complex types.

    Args:
        type_str (str): The type string to resolve.
        available_classes (dict): A dictionary of available custom classes.

    Returns:
        any: The resolved type.

    Raises:
        ValueError: If the type cannot be resolved.
    """
    # Check available_classes and builtins first.
    if type_str in available_classes:
        return available_classes[type_str]
    if type_str in BUILTIN_TYPES:
        return BUILTIN_TYPES[type_str]

    node = parse_type_string(type_str)

    # If the node is a Name, try to resolve it.
    if isinstance(node, ast.Name):
        name = node.id
        if name in available_classes:
            return available_classes[name]
        if name in BUILTIN_TYPES:
            return BUILTIN_TYPES[name]
        return ForwardRef(name)

    # Handle generic types, e.g., list[tuple[str, str]]
    if isinstance(node, ast.Subscript):
        base_node = node.value
        slice_node = node.slice

        # Get the base type name
        if isinstance(base_node, ast.Name):
            base_name = base_node.id
        else:
            raise ValueError(f"Unsupported base type expression: {ast.unparse(base_node)}")

        # Resolve the base type
        if base_name in available_classes:
            origin = available_classes[base_name]
        elif base_name in BUILTIN_TYPES:
            origin = BUILTIN_TYPES[base_name]
        else:
            # If base type is unknown, wrap it in a ForwardRef.
            origin = ForwardRef(base_name)

        # Handle the slice, which can be a Tuple (for multiple type parameters) or a single type.
        def resolve_from_node(n: ast.AST):
            s = ast.unparse(n)
            return resolve_type(s, available_classes)

        if isinstance(slice_node, ast.Tuple):
            resolved_args = [resolve_from_node(arg) for arg in slice_node.elts]
        else:
            resolved_args = [resolve_from_node(slice_node)]

        # For demonstration purposes, we return a type "hint" using subscription syntax.
        # In Python 3.9+ you can use the built-in generic types directly.
        try:
            # For types like list or dict that expect a single type parameter,
            # we'll support a single element in the resolved_args.
            if origin in (list,):
                return origin[resolved_args[0]]
            elif origin in (dict,):
                if len(resolved_args) != 2:
                    raise ValueError("dict must have two type parameters")
                return origin[tuple(resolved_args)]
            elif origin in (tuple,):
                return origin[tuple(resolved_args)]
            else:
                # For other generic types, we just mimic the subscription.
                return origin[tuple(resolved_args)]
        except TypeError as e:
            # If subscription fails, simply return a tuple of (origin, resolved_args)
            return (origin, resolved_args)

    # Fallback: if we can't figure out the type, return a ForwardRef.
    return ForwardRef(type_str)

# Example usage
if __name__ == '__main__':
    available_classes = {"MyClass": object}  # Example custom classes
    resolved = resolve_type("list[tuple[str, str]]", available_classes)
    print(resolved)


# Helper method to resolve importing from a module written as a string.
def resolve_import_from_module(reference: str) -> any:
    """
    Dynamically imports a variable, function or class from a module.

    Args:
        reference (str): The module and variable reference in the format 'module.var_name'.

    Returns:
        Any: The imported variable or function.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the variable cannot be found in the module.
    """
    try:
        module_path, var_name = reference.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, var_name)
    except (ImportError, AttributeError, ValueError) as e:
        raise ValueError(f"Could not resolve name '{var_name}' in module '{module_path}': {e}")

# Helper to resolve and import functions
def resolve_callable(callable_str: str) -> Callable:
    """
    Resolves a callable string to an actual function or lambda.
    Supports inline lambdas or module.function_name strings.

    Arguments:
        callable_str (str): function path (module.function_name) or lambda function.

    Returns:
        Callable: Resolved python function.

    Raises:
        ValueError: Could not resolve callable_str to a python Callable.
    """
    # Resolves a string lambda function to an actual lambda
    if callable_str.startswith("lambda"):
        try:
            lambda_func = eval(callable_str)
            return lambda_func
        except Exception as e:
            raise ValueError(f"Could not resolve lambda function '{callable_str}': {e}")  
    # Resolve a fully qualified function name (e.g., 'module.submodule.function') into a callable.
    else:
        return resolve_import_from_module(callable_str)



def load_agent_argument_classes_from_json(agent_arguments_class_defs: list[dict[str, any]]) -> dict[str, any]:
    """
    Load agent argument classes from a JSON data structure.

    Args:
        agent_arguments_class_defs (list[dict[str, any]]): List of dictionaries defining agent argument classes.

    Returns:
        dict[str, any]: A dictionary mapping class names to dynamically created Pydantic classes.
    """

    # Dynamically get all available custom types
    available_classes = get_all_subclasses(CustomTypeBase)

    created_classes = {}

    for class_def in agent_arguments_class_defs:
        class_name = class_def.pop("type")
        # Extract fields and their definitions
        fields = {}
        for field_name, field_info in class_def["fields"].items():
            # Resolve the type (can handle custom types inheriting from CustomTypeBase)
            field_type = resolve_type(field_info["type"], available_classes) 
            description = field_info.get("description", None)

            # Use Field() to properly register metadata
            fields[field_name] = (field_type, Field(..., description=description) if description else Field(...))
        
        # Dynamically create the Pydantic model
        new_class = create_model(
            class_name,  # Class name
            __base__=AgentArguments,  # Base class
            **fields  # Field definitions
        )
        created_classes[class_name] = new_class

    return created_classes


# Load LLMs
def load_llm(llm_data: dict, available_classes: dict[str, type[LLM]]) -> LLM:
    """
    Load an LLM instance from its configuration.

    Args:
        llm_data (dict): LLM configuration data.
        available_classes (dict[str, type[LLM]]): Dictionary of available LLM classes.

    Returns:
        LLM: Loaded LLM instance.
    """

    llm_type = llm_data["type"]
    llm_class = available_classes.get(llm_type)
    if not llm_class or not issubclass(llm_class, LLM):
        raise ValueError(f"Invalid LLM type: {llm_type}")

    # Check if the class expects a callable and resolve it
    
    # Retrieve the signature of the class or function
    llm_params = signature(llm_class).parameters
    resolved_data = {}
    for param, value in llm_data.items():
        if param in llm_params:
            # Check if the param is of type Callable
            param_type = llm_params[param].annotation
            if "Callable" in str(param_type):
                value = resolve_callable(value)
            resolved_data[param] = value
    return llm_class(**resolved_data)

# Load LLMs
def load_rag(rag_config: dict) -> RAG:
    """
    Load a RAG object instance from its configuration.

    Args:
        rag_config (dict): RAG configuration data.

    Returns:
        RAG: Loaded RAG instance.
    """

    rag_class_name = rag_config.pop("type")
    rag_class = resolve_import_from_module(rag_class_name)
    
    if not rag_class or not issubclass(rag_class, RAG):
        raise TypeError(f"Class {rag_class_name} must inherit from RAG")
    
    try:
        return rag_class(**rag_config)
    except Exception as e:
        raise ValueError(f"Error instantiating RAG class {rag_class_name}: {e}")  

# Extract prompt from external module if necessary
def extract_prompt_value(prompt_value: str) -> str:
    """
    Extracts the value of the extract_prompt_value.
    Resolves it either as a direct string or a reference
    to a variable in the format "module.var_name".

    Args:
        extract_prompt_value (str): The prompt or or a reference to a variable in the format "module.var_name".

    Returns:
        str: The resolved value of the prompt.
    """
    if "." in prompt_value and not ' ' in prompt_value:  # Potential module.variable reference
        try:
            return resolve_import_from_module(prompt_value)
        except ImportError:
            # Treat as plain string if the module cannot be imported
            return prompt_value
    else:  # Direct string
        return prompt_value

def load_agents_to_workflow_from_json(
    agent_defs: list[dict[str, any]],
    agent_argument_classes: dict[str, type[AgentArguments]],
    workflow: AgenticWorkflow,
    llm_instances: dict[str, LLM] = None
) -> None:
    """
    Load agents from a JSON data structure and add them to the AgenticWorkflow.

    Args:
        agent_defs (list[dict[str, any]]): List of dictionaries defining agents.
        agent_argument_classes (dict): Dictionary of preloaded agent argument classes.
        workflow (AgenticWorkflow): The AgenticWorkflow instance to which agents will be added.
        llm_instances (dict[str, LLM], optional): Dictionary of pre-loaded LLM instances.

    Raises:
        ValueError: If any referenced agent is invalid or duplicate.
    """
    
    agent_classes = get_all_subclasses(Agent)
    llm_classes = get_all_subclasses(LLM)

    for agent_def in agent_defs:
        try:
            agent_type = agent_def.pop("type")
            agent_class = agent_classes.get(agent_type)
            if not agent_class:
                raise ValueError(f"Unsupported agent type: {agent_type}")

            # Extract Input and Output argument schema
            input_schema = agent_argument_classes.get(agent_def.pop("input_schema"))
            output_schema = agent_argument_classes.get(agent_def.pop("output_schema"))
            if not input_schema or not output_schema:
                raise ValueError(f"Missing schema definition for {agent_def['name_id']}.")
            else:
                agent_def.update({"input_schema":input_schema})
                agent_def.update({"output_schema":output_schema})

            # Extract Agent type specific attributes
            if agent_type == "AIAgent" or agent_type == "RAGAgent":
                # Check if LLM is referenced by ID first
                if "llm_id" in agent_def:
                    llm_id = agent_def.pop("llm_id")
                    if not llm_instances or llm_id not in llm_instances:
                        raise ValueError(f"Referenced LLM ID '{llm_id}' not found in pre-loaded LLMs")
                    llm = llm_instances[llm_id]
                else:
                    # Fall back to inline LLM definition
                    llm = load_llm(agent_def.pop("llm"), llm_classes)
                
                prompt = extract_prompt_value(agent_def.pop("prompt"))
                agent_def.update({"llm": llm, "prompt": prompt})

                if agent_type == "RAGAgent":
                    rag = load_rag(agent_def.pop("rag"))
                    agent_def.update({"rag": rag})
                
            elif agent_type == "FunctionAgent":
                call_function = resolve_callable(agent_def["call_function"])
                agent_def.update({"call_function": call_function})

            # Instantiate the agent and add to workflow
            agent = agent_class(**agent_def)
            workflow.add_agent(agent)
    
        except Exception as e:
            agent_name_id = agent_def.get("name_id")
            raise ValueError(f"Error while loading Agent {agent_name_id if agent_name_id else ''}: {e}")


def load_edges_to_workflow_from_json(
    edge_defs: list[dict[str, any]], 
    workflow: AgenticWorkflow
) -> None:
    """
    Load edges from a JSON data structure and add them directly to the AgenticWorkflow.

    Args:
        edge_defs (list[dict[str, any]]): List of dictionaries defining edges.
        workflow (AgenticWorkflow): The AgenticWorkflow instance to which edges will be added.

    Raises:
        ValueError: If any referenced agent or callable is invalid.
    """

    edge_classes = get_all_subclasses(Edge)

    for edge_def in edge_defs:
        edge_type = edge_def["type"]

        if edge_type not in edge_classes:
            raise ValueError(f"Unsupported edge type: {edge_type}")

        source_agent_id = edge_def["sourceAgent"]

        if edge_type == "SimpleEdge":
            # Resolve target agent in O(1) time
            target_agent_id = edge_def["targetAgent"]
            
            # Add simple edge
            workflow.add_simple_edge(source_agent_id, target_agent_id)

        elif edge_type == "ConditionalEdge":
            # Resolve condition function
            condition_fn_path = edge_def["condition_fn"]
            condition_fn = resolve_callable(condition_fn_path)
            if not condition_fn:
                raise ValueError(f"Could not resolve condition function: {condition_fn_path}")
            
            # Add conditional edge
            workflow.add_conditional_edge(source_agent_id, condition_fn=condition_fn)

        else:
            raise ValueError(f"Unknown edge type: {edge_type}")



import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_workflow_from_json(json_path: str) -> AgenticWorkflow:
    """
    Load an entire workflow, including AgentArguments, Agents, and Edges, from a single JSON file.

    Args:
        json_path (str): Path to the JSON file defining the workflow.

    Returns:
        AgenticWorkflow: The fully initialized workflow.

    Raises:
        ValueError: If the JSON file is invalid or any part of the workflow fails to load.
    """
    try:
        logger.info(f"⚙️  Loading workflow from JSON file: {json_path}")
        # Load the JSON data
        with open(json_path, "r") as f:
            workflow_data = json.load(f)

        # Validate required sections in the JSON
        required_sections = ["agent_arguments", "agents", "edges"]
        for section in required_sections:
            if section not in workflow_data:
                raise ValueError(f"Missing required section '{section}' in the workflow JSON.")

        # Step 1: Initialize the Workflow
        workflow = AgenticWorkflow()

        # Optional Step: Load LLMs if present
        llm_instances = {}
        if "llms" in workflow_data:
            logger.info("Loading LLMs...")
            llm_classes = get_all_subclasses(LLM)
            for llm_def in workflow_data["llms"]:
                llm_id = llm_def["id"]
                llm_config = llm_def["llm"]
                llm = load_llm(llm_config, llm_classes)
                llm_instances[llm_id] = llm
            # Store list of LLMs used in the workflow
            for llm in llm_instances.values():
                workflow.add_llm(llm)
            logger.info("☑️  LLMs loaded successfully.")

        # Step 2: Load AgentArguments
        logger.info("Loading AgentArguments...")
        agent_argument_classes = load_agent_argument_classes_from_json(workflow_data["agent_arguments"])
        logger.info("☑️  AgentArguments loaded successfully.")

        # Step 3: Load Agents
        logger.info("Loading Agents...")
        load_agents_to_workflow_from_json(workflow_data["agents"], agent_argument_classes, workflow, llm_instances)
        logger.info(f"☑️  Agents loaded successfully.")

        # Step 4: Load Edges
        logger.info("Loading Edges...")
        load_edges_to_workflow_from_json(workflow_data["edges"], workflow)
        logger.info("☑️  Edges loaded successfully.")

        logger.info("✅  Workflow loaded successfully.")
        return workflow

    except Exception as e:
        logger.error(f"Error loading workflow: {e}")
        raise ValueError(f"❌  Failed to load workflow from JSON: {e}")



def run_workflow(workflow: AgenticWorkflow, initial_args: dict, max_retries: int = 0, save_run_path: str ="", run_name: str ="awe.out") -> AgentArguments:
    """
    Execute the workflow starting from the START node to the END node.

    Args:
        workflow (AgenticWorkflow): Workflow that needs to be run.
        initial_args (dict): Dictionary containing the initial arguments for the workflow.
        max_retries (int): Maximum number of retries for an agent if it fails due to invalid output.
        save_run_path (str): Path to where to save the history of the run (if not specified will be saved in current directory).
        run_name (str): Name of the run (if not specified will be saved as awe.out).
    Returns:
        AgentArguments: Final output after traversing the workflow.

    Raises:
        ValueError: If the dictionary cannot be converted into the appropriate AgentArguments instance.
    """
    # Determine the first agent to execute after the START node
    start_edge = workflow._edges.get("start")
    if not start_edge:
        raise ValueError("No edge found starting from the START node.")

    # Ensure the edge is a SimpleEdge
    if not isinstance(start_edge, SimpleEdge):
        raise ValueError("The first edge from START node must be a SimpleEdge.")

    # Get the first agent to execute
    first_agent = start_edge.target_agent

    # Convert initial_args dictionary to the required AgentArguments instance
    input_schema = first_agent.input_schema
    if not issubclass(input_schema, AgentArguments):
        raise ValueError("The input schema for the first agent is not a valid AgentArguments subclass.")

    try:
        initial_args_obj = input_schema(**initial_args)
    except Exception as e:
        raise ValueError(f"Error converting dictionary to {input_schema.__name__}: {e}")

    # Call the existing run method
    workflow_output = workflow.run(initial_args=initial_args_obj, max_retries=max_retries) 
    
    if save_run_path != "":
        file = os.path.join(save_run_path, run_name)
        try:
            os.makedirs(os.path.dirname(file), exist_ok=True)
            with open(file, "w") as f:
                f.write(workflow.getRunHistory())
            logger.info(f"Run history saved at {file}.")
        except Exception as e:
            logger.error(f"❌  Failed to save the run history at {file}: {e}")
    
    # Clear the run history after the workflow is run
    workflow.clearRunHistory()

    return workflow_output



def load_and_run_workflow(json_path: str, initial_args: dict, max_retries: int = 0, save_run_path: str ="", run_name: str ="awe.out", ) -> AgentArguments:
    """
    Load an entire workflow, including AgentArguments, Agents, and Edges, from a single JSON file.
    Execute the workflow starting from the START node to the END node.

    Args:
        json_path (str): Path to the JSON file defining the workflow.
        initial_args (dict): Dictionary containing the initial arguments for the workflow.
        max_retries (int): Maximum number of retries for an agent if it fails due to invalid output.
        save_run_path (str): Path to where to save the history of the run (if not specified will be saved in current directory).
        run_name (str): Name of the run (if not specified will be saved as awe.out).
    Returns:
        AgentArguments: Final output after traversing the workflow.

    Raises:
        ValueError: If the dictionary cannot be converted into the appropriate AgentArguments instance.
    """
    workflow = load_workflow_from_json(json_path)
    return run_workflow(workflow, initial_args, max_retries, save_run_path, run_name)