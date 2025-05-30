import json
from pydantic import BaseModel, Field, ValidationError
from abc import ABC, abstractmethod
from typing import Optional, Callable, get_type_hints
from inspect import signature, Parameter
from string import Formatter
import inspect
import types
import textwrap
import re
import logging

from awe.LLMs import LLM
from awe.RAG import RAG


# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler()) # Avoid "No handlers could be found" warnings


class AgentArguments(BaseModel, ABC):
    """
    Abstract base class for agent input arguments.
    Each agent must implement concrete argument classes.
    """
    pass


class Agent(BaseModel, ABC):
    """
    Abstract class to represent an agent that executes a specific task.
    To execute the agent, it takes specific inputs and returns specific outputs. 

    Attributes:
        name_id (str): Unique name for the agent.
        input_schema (type[AgentArguments]): The expected input model for the agent.
        output_schema (type[AgentArguments]): The expected output model for the agent.
        propagate_input_args (bool): Whether to propagate the input arguments to the output.
    """
    name_id: str = Field(description="Unique name for the agent.")
    input_schema: type[AgentArguments] = Field(description="The expected input model for the agent.")
    output_schema: type[AgentArguments] = Field(description="The expected output model for the agent.")
    propagate_input_args: bool = Field(default=True, description="Whether to propagate the input arguments to the output.")

    def _validate_input(self, input_args: AgentArguments) -> None:
        """
        Validate that input_args respect input_schema.

        Args:
            input_args (AgentArguments): Input arguments for the agent.

        Raises:
            TypeError: If the input arguments do not match the expected input schema.            
        """
        logger.info(f"➡️  {self.name_id} Inputs: {json.dumps(input_args.model_dump(), indent=2)}")

        # Check that the input does match the expected schema.
        if not isinstance(input_args, self.input_schema):
            raise TypeError(
                f"Expected input of type {self.input_schema.__name__}, "
                f"but got {type(input_args).__name__}."
            )

    def extract_function_args(
        self,
        func: Callable, 
        input_args: dict[str, any], 
        param_mapping: Optional[dict[str, str]] = None
    ) -> dict[str, any]:
        """
        Extract and validate arguments required for a function from a dictionary of inputs,
        with support for parameter name mapping.
        
        Args:
            func (Callable[..., T]): The function whose arguments need to be extracted
            input_args (dict[str, any]): Dictionary containing potential argument values
            param_mapping (Optional[dict[str, str]]): Mapping from function parameter names to input_args keys.
                e.g., {"query": "input_query"} maps func(query=...) to input_args["input_query"]
        
        Returns:
            dict[str, any]: Dictionary containing the required and optional arguments for the function
            
        Raises:
            ValueError: If required arguments are missing from input_args
            TypeError: If provided argument types don't match function's type hints
        
        Example:
            >>> def example_func(query: str, limit: int = 10) -> None:
            ...     pass
            >>> input_args = {"input_query": "search", "max_results": 5}
            >>> mapping = {"query": "input_query", "limit": "max_results"}
            >>> extracted = extract_function_args(example_func, input_args, mapping)
            >>> print(extracted)
            {'query': 'search', 'limit': 5}
        """
        sig = signature(func)
        type_hints = get_type_hints(func)
        extracted_args = {}
        missing_args = []
        param_mapping = param_mapping or {}

        # Process each parameter in the function signature
        for param_name, param in sig.parameters.items():
            # Skip *args and **kwargs
            if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
                continue
            
            # Get the corresponding input argument name
            input_name = param_mapping.get(param_name, param_name)
            
            if input_name in input_args:
                value = input_args[input_name]
                
                # Validate type if type hint exists
                if param_name in type_hints:
                    expected_type = type_hints[param_name]
                    if not isinstance(value, expected_type):
                        raise TypeError(
                            f"Argument '{input_name}' (for parameter '{param_name}') must be of type "
                            f"{expected_type.__name__}, got {type(value).__name__}"
                        )
                
                extracted_args[param_name] = value
            elif param.default == Parameter.empty:  # Required argument
                missing_args.append(f"{param_name} (expected in input as: {input_name})")
        
        if missing_args:
            raise ValueError(
                f"Missing required arguments for {func.__name__}: {', '.join(missing_args)}"
            )
        
        return extracted_args

    def _propagate_args(self, input_args: AgentArguments, output_dict: dict[str: any]) -> dict[str: any]:
        """
        Add the Agent's input arguments to the output dictionary, so that the next agent have access.

        Args:
            input_args (AgentArguments): Input arguments for the agent.
            output_dict (dict[str: any]): The output dictionary after executing the Agent.

        Returns:
            dict[str: any]: The Agent's output arguments concatenated with the input arguments.
        """
        # Convert the Pydantic object to a dictionary
        input_dict = input_args.model_dump()

        # Merge dictionaries, prioritizing values from output_dict
        for key, value in input_dict.items():
            output_dict.setdefault(key, value)
        
        return output_dict
    
    def _validate_dict_output(self, output_dict: dict[str: any]) -> AgentArguments:
        """
        Parse and validate the output dictionary from the Agent.

        Args:
            output_dict (dict[str: any]): The output dictionary after executing the Agent.

        Returns:
            AgentArguments: The validated output as an instance of output_schema.

        Raises:
            ValueError: If the output cannot be parsed or is invalid.
        """

        try:
            # Validate the parsed output against the output model
            validated_output = self.output_schema.model_validate(output_dict)
            logger.info(f"⤵️  {self.name_id} Outputs: {json.dumps(validated_output.model_dump(), indent=2)}.")
            return validated_output
        except ValidationError as e:
            logger.warning(f"Invalid outputs: {json.dumps(output_dict, indent=2)}.")
            raise ValueError(f"Output is not valid, does not match the expected schema {self.output_schema.model_fields}: {e}")


    def model_dump(self, **kwargs) -> dict[str: any]:
        """
        Overrides default model_dump function.
        Converts class to dictionary. 
        
        Returns:
            dict[str: any]: Dictionary of class arguments.
        """
        base_dump = super().model_dump(**kwargs)
        if self.input_schema != None:
            base_dump["input_schema"] = self.input_schema.__name__
        if self.output_schema != None:
            base_dump["output_schema"] = self.output_schema.__name__
        base_dump["type"] = self.__class__.__name__
        return base_dump

    def __hash__(self):
        """
        Hash function to allow usage as dictionary keys.
        """
        return hash(self.name_id)

    def __eq__(self, other):
        """
        Equality function to compare agents based on their unique name_id.
        """
        if isinstance(other, Agent):
            return self.name_id == other.name_id
        return False

    @abstractmethod
    def __call__(self, input_args: AgentArguments) -> AgentArguments:
        """
        Executes the task of the agent and return results in the output_schema.
        Propagates input to output if needed.

        Args:
            input_args (AgentArguments): Input arguments for the agent.
        
        Returns:
            AgentArguments: Validated output arguments after running the task.
        
        Raises:
            TypeError: If the input arguments do not match the expected input schema.
            ValueError: If the output does not match the expected schema.
        """
        pass

    

class AIAgent(Agent):
    """
    AI Agent that runs an LMM.

    Attributes:
        llm (LLM): The language model to execute for this agent.
        prompt (str): The prompt template for the agent. The prompt must be properly formatted to handle the input arguments.
    """
    llm: LLM = Field(description="The language model to execute for this agent.")
    prompt: str  = Field(description="The prompt template for the agent. The prompt must be properly formatted to handle the input arguments.")
    max_output_tokens: int = Field(default=4096, description="Maximum number of output tokens.")
    _formatted_prompt: str = None
    _raw_output: str = None

    def _format_prompt(self, prompt: str, args_dict: dict[str, any]) -> str:
        """
        Formats the prompt using input arguments and additional arguments.

        Args:
            prompt (str): The prompt template with placeholders.
            args_dict (dict[str, any]): Arguments to use in the prompt.

        Returns:
            str: The formatted prompt.

        Raises:
            ValueError: If the prompt contains a placeholder not in input_args or additional_args.
        """
        # Extract all placeholders from the prompt
        formatter = Formatter()
        placeholders = [field_name for _, field_name, _, _ in formatter.parse(prompt) if field_name]
        
        # Validate that all placeholders exist in the combined dictionary
        for placeholder in placeholders:
            if placeholder not in args_dict:
                raise ValueError(f"Placeholder '{placeholder}' in the prompt is not found in input_args.")

        # Format the prompt with the merged arguments
        self._formatted_prompt = prompt.format(**args_dict)
        logger.info(f"📝  {self.name_id} Prompt: {self._formatted_prompt}")
        return self._formatted_prompt


    def _extract_json_from_text(self, text: str) -> dict:
        """
        Extracts the first JSON object from the given text, preprocessing any <raw> ... </raw> tags.
        
        This function handles <raw> tags in two ways:
        1. If the <raw> block appears inside an already quoted JSON string, it normalizes
            the raw content (decoding any existing escapes) and then re‑escapes it without
            adding extra outer quotes.
        2. Otherwise, it replaces the block with a properly escaped and quoted JSON string.
        
        Args:
            text (str): The input text containing a JSON object possibly with <raw> tags.
        
        Returns:
            dict: The parsed JSON object if found and valid.
        
        Raises:
            ValueError: If no JSON object is found or the JSON cannot be parsed.
        """
        def normalize_raw(raw_content: str) -> str:
            """
            Decodes already escaped sequences in raw_content and returns the normalized string.
            If decoding fails, returns the original raw_content.
            """
            try:
                # The 'unicode_escape' codec decodes backslash escapes.
                return bytes(raw_content, "utf-8").decode("unicode_escape")
            except Exception:
                return raw_content

        # Pass 1: Replace <raw>...</raw> blocks that are inside an already quoted JSON string.
        # The regex uses lookbehind and lookahead to ensure it is between double quotes.
        def replace_raw_inside(match):
            raw_content = match.group(1)
            normalized = normalize_raw(raw_content)
            # json.dumps will return a properly escaped JSON string literal (with quotes).
            escaped = json.dumps(normalized)
            # Remove the outer quotes so as not to double-quote an already quoted string.
            return escaped[1:-1]

        text = re.sub(r'(?<=")\s*<raw>(.*?)</raw>\s*(?=")', replace_raw_inside, text, flags=re.DOTALL)

        # Pass 2: Replace any remaining <raw>...</raw> blocks (outside quoted strings)
        def replace_raw(match):
            raw_content = match.group(1)
            normalized = normalize_raw(raw_content)
            return json.dumps(normalized)

        text = re.sub(r"<raw>(.*?)</raw>", replace_raw, text, flags=re.DOTALL)

        # Step 1: Look for JSON enclosed in triple backticks (```json ... ```)
        backtick_json_pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(backtick_json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1), strict=False)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid outputs: {text}")
                raise ValueError(f"Invalid JSON object found within backticks: {e}") from e

        # Step 2: Fallback to extracting JSON based on braces {} using regex.
        braces_json_pattern = r"(\{.*?\})"
        match = re.search(braces_json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid outputs: {text}")
                raise ValueError(f"Invalid JSON object found: {e}") from e

        logger.warning(f"Invalid outputs: {text}")
        raise ValueError("No JSON object found in the provided text.")



    def _AgentArguments_to_dict(self, args: AgentArguments) -> dict[str, any]:
        """
        Convert arguments to a dictionary and serialize the input_args to JSON-compatible format

        Args:
            args (AgentArguments): Arguments to convert to a dictionary and serialize.
        """
        # Serialize input_args to JSON-compatible format
        model_data_json = json.dumps(args.model_dump())

        # Convert the JSON string back to a dictionary for `format()` usage
        model_data = json.loads(model_data_json)
        return model_data

    def _raw_output_to_validated_output(self, input_args: AgentArguments, json_str_output: str) -> AgentArguments:
        """
        Parse and validate the raw JSON string output from the LLM to the output_schema object.
        
        Args:
            json_str_output (str): The raw JSON string output from the LLM.
            input_args (AgentArguments): Input arguments for the agent.
            
        Returns:
            dict[str: any]: Validated output arguments following the output_schema.

        Raises:
            ValueError: If the output cannot be parsed or is invalid.
        """
        # Transform the output JSON string to a dictionary
        output_dict = self._extract_json_from_text(json_str_output)
        # Propagate the input arguments to the output
        if self.propagate_input_args:
            output_dict = self._propagate_args(input_args, output_dict)

        # Validate and transforms the output to output_schema
        validated_output = self._validate_dict_output(output_dict)

        return validated_output

    def __call__(self, input_args: AgentArguments) -> AgentArguments:
        # Check that the input does match the expected schema.
        self._validate_input(input_args)
        
        # Format the prompt with input arguments
        input_args_dict = self._AgentArguments_to_dict(input_args)
        self._formatted_prompt = self._format_prompt(self.prompt, input_args_dict)

        # Execute the LLM
        self._raw_output = self.llm.chat(self._formatted_prompt, self.max_output_tokens)
        
        # Parse and validate the output JSON string to output_schema
        validated_output = self._raw_output_to_validated_output(input_args, self._raw_output)

        return validated_output

    def __repr__(self):
        """
        Representation for debugging purposes.
        """
        return f"AIAgent(name={repr(self.name_id)}, input_schema={repr(self.input_schema.__name__)}, output_schema={repr(self.output_schema.__name__)}, propagate_input_args={self.propagate_input_args}, LLM={repr(self.llm)}, max_output_tokens={self.max_output_tokens}, prompt={repr(self.prompt)})"


class RAGAgent(AIAgent):
    """
    AI Agent that runs an LLM using Retrieval-Augmented Generation (RAG).

    Attributes:
        llm (LLM): The language model to execute for this agent.
        rag (RAG): The class that handles the RAG logic for indexing and retrieval.
        prompt (str): The prompt template for the agent. Must include placeholders for input arguments and 'rag_context'.
        max_output_tokens (int): Maximum number of output tokens.
        retrieval_param_mapping (dict[str,str]): The key to the arguments in input_args used for retrieval.
        retrieval_placeholder_key (str): The name of the placeholder in the prompt where to insert retrieved context.
        top_k (int): The number of top results to retrieve during RAG.
    """
    llm: LLM = Field(description="The language model to execute for this agent.")
    rag: RAG = Field(description="The class that handles the RAG logic for indexing and retrieval.")
    prompt: str = Field(description="The prompt template for the agent. Must include placeholders for input arguments and 'rag_context'.")
    max_output_tokens: int = Field(default=4096, description="Maximum number of output tokens.")
    retrieval_param_mapping: dict[str,str] = Field(description="The key to the arguments in input_args used for retrieval.")
    retrieval_placeholder_key: str = Field(default="retrieved_context", description="The name of the placeholder in the prompt where to insert retrieved context.")
    top_k: int = Field(default=5, description="The number of top results to retrieve during RAG.")

    def __call__(self, input_args: AgentArguments) -> AgentArguments:
        """
        Execute the RAG agent.

        Args:
            input_args (AgentArguments): Input arguments for the agent.

        Returns:
            AgentArguments: Output arguments generated by the agent.
        """
        # Check that the input does match the expected schema.
        self._validate_input(input_args)
        input_args_dict = self._AgentArguments_to_dict(args=input_args)

        ### Step 1: Perform retrieval
        # Load arguments to run the retrieval
        retrieval_args = self.extract_function_args(
            func=self.rag.retrieve_relevant,
            input_args=input_args_dict,
            param_mapping=self.retrieval_param_mapping
        )
        retrieval_args["top_k"]=self.top_k
        # Retrieve relevant context
        retrieved_context = self.rag.retrieve_relevant(**retrieval_args)
        # Concatenate retrieved results
        rag_context = "\n\n".join(str(result) for result in retrieved_context)

        ### Step 2: Format the prompt with retrieved context input arguments
        input_args_dict.update({self.retrieval_placeholder_key: rag_context})
        self._formatted_prompt = self._format_prompt(self.prompt, input_args_dict)

        ### Step 3: Perform the augmented generation using the LLM
        self._raw_output = self.llm.chat(self._formatted_prompt, self.max_output_tokens)

        # Parse and validate the output JSON string to output_schema
        validated_output = self._raw_output_to_validated_output(input_args, self._raw_output)

        return validated_output

    def __repr__(self):
        """
        Representation for debugging purposes.
        """
        return f"RAGAgent(name={repr(self.name_id)}, input_schema={repr(self.input_schema.__name__)}, output_schema={repr(self.output_schema.__name__)}, propagate_input_args={self.propagate_input_args}, LLM={repr(self.llm)}, max_output_tokens={self.max_output_tokens}, rag={repr(self.rag)}, retrieval_param_mapping={repr(self.retrieval_param_mapping)}, retrieval_placeholder_key={repr(self.retrieval_placeholder_key)}, prompt={repr(self.prompt)})"

class FunctionAgent(Agent):
    """
    Agent that executes a specific function.

    Attributes:
        call_function (Callable[[AgentArguments], any]): Function that will be executed. The function must take an object of type input_schema as input, and output a dictionary of attributes.
    """
    call_function: Callable[[AgentArguments], dict[str: any]] = Field(description="Function that will be executed. The function must take an object of type input_schema as input, and output a dictionary of attributes.")

    def model_post_init(self, __context: any) -> None:
        """
        Pydantic class initialization.
        """
        # Get the parameter names of the function
        self._func_params = signature(self.call_function).parameters
    
    def model_dump(self, **kwargs):
        base_dump = super().model_dump(**kwargs)

        if isinstance(self.call_function, types.LambdaType) and self.call_function.__name__ == "<lambda>":
            try:
                # Extract source code safely (handling indentation issues)
                source_lines = inspect.getsource(self.call_function).split("\n")
                lambda_code = textwrap.dedent("\n".join(source_lines)).strip()
            except OSError:
                lambda_code = " (unable to extract source)"

            base_dump["call_function"] = f"lambda:{lambda_code}"
        else:
            base_dump["call_function"] = f"{self.call_function.__module__}.{self.call_function.__name__}"

        return base_dump


    def __call__(self, input_args: AgentArguments) -> AgentArguments:
        # Check that the input does match the expected schema.
        self._validate_input(input_args)
        
        # Filter input_args to include only the arguments required by the function
        filtered_args = {key: value for key, value in input_args.model_dump().items() if key in self._func_params}

        # Execute the Agent's logic
        output_dict = self.call_function(**filtered_args)

        # Propagate the input arguments to the output
        if self.propagate_input_args:
            output_dict = self._propagate_args(input_args, output_dict)

        # Validate and transforms the output to output_schema
        validated_output = self._validate_dict_output(output_dict)
        
        return validated_output

    def __repr__(self):
        """
        Representation for debugging purposes.
        """
        return f"FunctionAgent(name={repr(self.name_id)}, input_schema={repr(self.input_schema.__name__)}, output_schema={repr(self.output_schema.__name__)}, propagate_input_args={self.propagate_input_args}, call_function={repr(self.call_function)})"


class StartAgent(Agent):
    """
    A dummy START agent for initializing the workflow.
    """
    
    name_id: str = "start"
    input_schema: type[AgentArguments] = None
    output_schema: type[AgentArguments] = None
    
    def __call__(self, args: AgentArguments) -> AgentArguments:
        """
        Pass through the input arguments.

        Args:
            args (AgentArguments): The initial arguments for the workflow.

        Returns:
            AgentArguments: The same input arguments.
        """
        return args

    def __repr__(self):
        """
        Representation for debugging purposes.
        """
        return f"StartAgent(name={repr(self.name_id)})"


class EndAgent(Agent):
    """
    A dummy END agent for terminating the workflow.
    """
    name_id: str = "end"
    input_schema: type[AgentArguments] = None
    output_schema: type[AgentArguments] = None
    
    def __call__(self, args: AgentArguments) -> AgentArguments:
        """
        Pass through the final arguments.

        Args:
            args (AgentArguments): The final arguments from the workflow.

        Returns:
            AgentArguments: The same input arguments.
        """
        return args
    
    def __repr__(self):
        """
        Representation for debugging purposes.
        """
        return f"EndAgent(name={repr(self.name_id)})"