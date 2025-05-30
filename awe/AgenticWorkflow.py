from pydantic import BaseModel
from typing import Callable
import json
import logging

from awe.Agent import Agent, AIAgent, AgentArguments, StartAgent, EndAgent
from awe.Edge import Edge, SimpleEdge, ConditionalEdge
from awe.History import History
from awe.LLMs import LLM
# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler()) # Avoid "No handlers could be found" warnings


class AgenticWorkflow(BaseModel):
    """
    A class to execute a sequence of agents represented as a graph workflow.

    Attributes:
        _start_node (Agent): The dummy START node.
        _end_node (Agent): The dummy END node.
        _nodes (dict[str: Agent]): The agent IDs and agents in the workflow. Agent nodes must be unique.
        _edges (dict[Agent, Edge]): A mapping from source agent IDs to their outgoing edges. There can only be one Edge object for a given source node.
        _llms (list[LLM]): The list of LLMs used by the workflow.
        _history (History): The execution history of the workflow.
    """
    _start_node = StartAgent()
    _end_node = EndAgent()
    _nodes: dict[str: Agent] = {"start": _start_node, "end":_end_node} # Agents in the workflow represent graph nodes.
    _edges: dict[str, Edge] = {} # Maps an agent id to its single outgoing edge.
    _llms: list[LLM] = []
    _history: History = History()

    def add_agent(self, agent: Agent):
        """
        Add a agent node to the workflow.

        Args:
            node (Agent): The agent node to add.
        """
        if agent.name_id in self._nodes:
            raise ValueError(f"Agent {agent} already inserted in the workflow.")
        self._nodes[agent.name_id] = agent

    def add_llm(self, llm: LLM):
        """
        Add an LLM that will be used by the workflow.

        Args:
            llm (LLM): The LLM to add.
        """
        self._llms.append(llm)

    def get_llms(self) -> list[LLM]:
        """
        Get the list of LLMs used by the workflow.
        """
        return self._llms

    def add_simple_edge(self, source_agent_id: str, target_agent_id: str):
        """
        Add a direct transition between agent nodes in the graph workflow.

        Args:
            source_agent_id (str): The ID of the source agent node executed before the transition.
            target_agent_id (str): The ID of the target agent node to be executed after the transition.
        
        Raises:
            ValueError: If source or target node is not in _nodes or another edge has source as a source. 
        """
        if source_agent_id not in self._nodes:
            raise ValueError(f"Source agent node '{source_agent_id}' must already exist in the workflow. Use add_agent(agent) to add an agent.")
        if target_agent_id not in self._nodes:
            raise ValueError(f"Target agent node '{target_agent_id}' must already exist in the workflow. Use add_agent(agent) to add an agent.")
        if source_agent_id in self._edges:
            raise ValueError(f"Agent {source_agent_id} already has an outgoing edge. Each agent can only be an Edge source node once.")
        edge = SimpleEdge(source_agent=self._nodes[source_agent_id], target_agent=self._nodes[target_agent_id])
        self._edges[source_agent_id] = edge
    
    def add_conditional_edge(self, source_agent_id: str, condition_fn: Callable[[AgentArguments], Agent]):
        """
        Add conditional edge for transitioning between agent nodes based on a function. 
        (The first edge from START node must be a SimpleEdge.)

        Args:
            source (Agent): The ID of the source agent node executed before the transition.
            condition_fn (callable[[BaseModel], Agent]): A function that determines the next agent node based on source agent output arguments.
        
        Raises:
            ValueError: If source or target node is not in _nodes or another edge has source as a source. 
        """
        if source_agent_id not in self._nodes:
            raise ValueError(f"Source agent node '{source_agent_id}' must already exist in the workflow. Use add_agent(agent) to add an agent.")
        elif source_agent_id in self._edges:
            raise ValueError(f"Agent '{source_agent_id}' already has an outgoing edge. Each agent can only be an Edge source node once.")
        elif source_agent_id == "start": # Ensure the edge going from the start node is a SimpleEdge
            raise ValueError("The first edge from START node must be a SimpleEdge.")
        edge = ConditionalEdge(source_agent=self._nodes[source_agent_id], condition_fn=condition_fn)
        self._edges[source_agent_id] = edge

    def _run_current_agent(self, current_agent: Agent, current_args: AgentArguments, max_retries: int) -> AgentArguments:
        """
        Execute the current agent and retries in case of invalid output.
        Catch ValueError: If an agent fails after the maximum number of retries or encounters a non-retryable error.

        Args:
            current_agent (Agent): The current agent to execute.
            current_args (AgentArguments): Input arguments values, to execute the current agent.
            max_retries (int): Maximum number of retries for an agent if it fails due to invalid output.

        Returns:
            AgentArguments: Output arguments values, after executing the current agent (None in case of execution failure).
        
        Raises:
            RuntimeError: In case an error occurred during the agent execution.
        """

        output_args = None
        retries = 0
        execution_successful = False

        while retries <= max_retries and not execution_successful:
            if current_agent.name_id != self._start_node.name_id:
                logger.info(f"🤖  Running Agent {current_agent.name_id}{f', attempt #{retries}/{max_retries},' if retries>0 else ''}.")
            try:
                # Execute the current agent
                output_args = current_agent(current_args)

                # Mark execution as successful and proceed to the next agent
                execution_successful = True
                
                # Add the successful execution to history
                if isinstance(current_agent, AIAgent):
                    self._history.add_record(
                        agent=current_agent,
                        input_args=current_args,
                        output_args=output_args,
                        formatted_prompt=current_agent._formatted_prompt,
                        raw_output=current_agent._raw_output,
                        nb_retry=retries
                    )
                else:
                    self._history.add_record(
                        agent=current_agent,
                        input_args=current_args,
                        output_args=output_args,
                        nb_retry=retries
                    )

            except Exception as e:
                error_message = str(e)

                # Log the error
                if isinstance(current_agent, AIAgent):
                    self._history.add_record(
                        agent=current_agent,
                        input_args=current_args,
                        output_args=output_args,
                        nb_retry=retries,
                        error=error_message
                    )
                else:
                    self._history.add_record(
                        agent=current_agent,
                        input_args=current_args,
                        output_args=output_args,
                        nb_retry=retries,
                        error=error_message
                    )

                # Retry if the error is retryable and retries are available
                if "Output is not valid" in error_message:
                    # Reattempt due to invalid output
                    if  retries < max_retries:
                        retries += 1
                        logging.warning(f"Reattempting to execute agent {current_agent.name_id} ({retries}/{max_retries}), due to invalid output: {e}.")
                    # Fatal error: no new attempts
                    else:
                        # Halt execution after failing to execute the Agent
                        raise RuntimeError(f"Failed to execute agent {current_agent.name_id} due to invalid output: {e}.")
                else:
                    # Halt execution after failing to execute the Agent
                    raise RuntimeError(f"Unexpected error while running Agent {current_agent.name_id}: {e}.")

        return output_args

    def _get_next_agent(self, current_agent: Agent, current_args: AgentArguments, output_args: AgentArguments) -> tuple[Agent, AgentArguments]:
        """
        Determine the next agent to execute. Maps output to the expected next input format.
        Catch RuntimeError: If no valid transition.

        Args:
            current_agent (Agent): The current agent to execute.
            current_args (AgentArguments): Input arguments values, used to execute the current agent.
            output_args (AgentArguments): Output arguments values from the current agent.

        Returns:
            Agent: Agent to execute next (None if no transition found).
            AgentArguments: Output arguments mapped to the input format for the next agent.
        
        Raises:
            RuntimeError: In case an error occurred while retrieving the next agent.
        """

        next_agent = None
        next_args = None
        try:
            # Retrieve the outgoing edge
            edge = self._edges.get(current_agent.name_id)
            if not edge:
                raise RuntimeError(f"No outgoing edge from agent {current_agent}.")

            # Determine the next agent
            next_agent_id = edge.get_next_node(output_args)
            if next_agent_id and (next_agent_id in self._nodes):
                next_agent = self._nodes[next_agent_id]
            else:
                raise RuntimeError(f"No valid transition from agent {current_agent}.")
            
            # Maps the output arguments of the source agent to the input arguments of the target agent.
            next_args = edge.map_args_to_next_agent(output_args, next_agent)

            return next_agent, next_args

        except Exception as e:
            self._history.add_record(
                agent=current_agent,
                input_args=current_args,
                output_args=output_args if output_args else None,
                error=str(e)
            )
            # Halt execution after no transition found
            raise RuntimeError(f"Failed to find a valid transition from agent {current_agent.name_id}: {e}")
    
    # def _dict_pydantic_to_json_indent(self, dict_pydantic: dict[str, BaseModel]) -> json:
    #     """
    #     Transforms a dictionary of Pydantic objects to a JSON object ready for display.

    #     Arguments:
    #         dict_pydantic (dict[str, BaseModel]): Dictionary of string key and Pydantic object value.

    #     Returns:
    #         json: JSON representation of the input ready for display with indentation.
    #     """
    #     serializable_dict = {}
        
    #     for key, pydantic_obj in dict_pydantic.items():
    #         if isinstance(pydantic_obj, type) and issubclass(pydantic_obj, BaseModel):
    #             raise TypeError(f"Expected an instance of a Pydantic model, but got a class: {pydantic_obj}")
            
    #         serializable_dict[key] = repr(pydantic_obj)
        
    #     for key, value in serializable_dict.items():
    #         print(f"Key: {key}, value: {value}")

    #     return json.dumps(serializable_dict, indent=2)




    def _AgentArguments_class_def_to_json(self, model_class: AgentArguments) -> dict[str, str]:
        """
        Parse AgentArgument class definitions to JSON.
        
        Args:
            model_class (AgentArguments): An AgentArguments class definition
            
        Returns:
            dict[str, str]: Parsed AgentArgument class definitions to JSON.
        """
        # Get model fields
        model_fields = model_class.model_fields
        
        # Initialize schema
        schema = {
            "type": model_class.__name__,
            "fields": {}
        }
        
        # Process each field
        for field_name, field_info in model_fields.items():
            field_type = field_info.annotation
            
            # Convert Python types to string representations
            type_str = str(field_type)
            # Clean up type string (remove 'typing.' prefixes, etc.)
            type_str = type_str.replace('typing.', '')
            type_str = type_str.replace('NoneType', 'None')
            type_str = type_str.replace('<class ', '').replace('>', '').replace("'", "")
            
            # Get field description from the field's description attribute or docstring
            description = field_info.description or ""
            
            schema["fields"][field_name] = {
                "type": type_str,
                "description": description
            }
        
        return schema

    def get_json_representation(self):
        """
        String representation of the workflow.
        """

        workflow_json_config = {}

        # Get all AgentArgument classes
        agent_arg_classes_name = set()
        json_agent_arg_classes = []
        json_agents = []
        for id, agent in self._nodes.items():
            if not id in {"start", "end"}:
                in_class_args = agent.input_schema
                if not in_class_args.__name__ in agent_arg_classes_name:
                    agent_arg_classes_name.add(in_class_args.__name__)
                    json_agent_arg_classes.append(self._AgentArguments_class_def_to_json(in_class_args))
                out_class_args = agent.output_schema
                if not out_class_args.__name__ in agent_arg_classes_name:
                    agent_arg_classes_name.add(out_class_args.__name__)
                    json_agent_arg_classes.append(self._AgentArguments_class_def_to_json(out_class_args))
            
                json_agents.append(agent.model_dump())
        
        workflow_json_config["agent_arguments"] = json_agent_arg_classes
        print("///////////////////")
        print(json_agents)
        workflow_json_config["agents"] = json_agents
        print("///////////////////")
        print(workflow_json_config)
        return json.dumps(workflow_json_config, indent=2)
        # Parse AgentArgument class definitions to JSON 

        # return f"""AgenticWorkflow{{
        #     nodes: {self._dict_pydantic_to_json_indent(self._nodes)}
        #     edges: {self._dict_pydantic_to_json_indent(self._edges)}
        # }}
        # """


    def run(self, initial_args: AgentArguments, max_retries: int = 0) -> AgentArguments:
        """
        Execute the workflow starting from the START node to the END node.

        Args:
            initial_args (AgentArguments): Initial arguments for the workflow.
            max_retries (int): Maximum number of retries for an agent if it fails due to invalid output.

        Returns:
            AgentArguments: Final output after traversing the workflow.

        Raises:
            RuntimeError: When error occurs in the the execution fo the workflow.
        """
        
        logger.info("🚀  Launching the workflow.")

        current_agent = self._start_node
        current_args = initial_args
        no_errors = True

        while current_agent != self._end_node and no_errors:
            try:

                # Executes current agent
                output_args = self._run_current_agent(current_agent, current_args, max_retries)              

                # Determine the next agent to execute and prepare its input
                next_agent, next_args = self._get_next_agent(current_agent, current_args, output_args)

                # Move to the next agent
                current_agent = next_agent
                current_args = next_args
            except Exception as e:
                logger.error(f"❌  Interrupted workflow execution: {e}")
                no_errors = False

        # Log run successful status.
        if no_errors:
            logger.info("✅  Successful workflow execution.")

        return current_args
    
    def getRunHistory(self) -> str:
        """
        Returns the full history of the execution as a Json string.
        """
        return self._history.to_json()
    
    def clearRunHistory(self):
        """
        Clears the run history of the workflow.
        """
        self._history = History()