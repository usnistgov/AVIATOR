from pydantic import BaseModel, Field, ValidationError
from abc import ABC, abstractmethod
from typing import Callable

from awe.Agent import Agent, EndAgent
from awe.Agent import AgentArguments

class Edge(BaseModel, ABC):
    """
    Abstract base class for edges in the agentic graph workflow.
    Transition between agents are represented as edges (can be conditional edge).
    
    Attributes:
        source_agent (Agent): The source agent node executed before the transition.
    """
    source_agent: Agent = Field(description="Agent executed before the transition.")

    def map_args_to_next_agent(self, src_output_args: AgentArguments, target_agent: Agent) -> AgentArguments:
        """
        Maps the output arguments of the source agent to the input arguments of the target agent.

        Args:
            src_output_args (AgentArguments): The output arguments of the source agent.
            target_agent (Agent): The next agent node to transition to.

        Returns:
            AgentArguments: The input arguments for the target agent.

        Raises:
            ValueError: If the mapping fails due to invalid arguments.
        """
        # The output is not formatted when reaching the end
        if target_agent == EndAgent():
            return src_output_args
        
        try:
            # Filter src_output_args to include only fields relevant to the target_agent's input_model
            filtered_args = {
                field: value
                for field, value in src_output_args.model_dump().items()
                if field in target_agent.input_schema.model_fields
            }
            
            # Validate and adapt the filtered arguments to the target input model
            return target_agent.input_schema.model_validate(filtered_args)
        except ValidationError as e:
            raise ValueError(
                f"Failed to map output arguments from agent {self.sourceAgent.name_id} "
                f"to input arguments of agent {target_agent.name_id}: {e}"
            )


    @abstractmethod
    def get_next_node(self, src_output_args: AgentArguments) -> str:
        """
        Determine the next agent node to transition to.

        Args:
            src_output_args (dict): The output arguments of the source agent.
        
        Returns:
            str: The ID of the next agent node to transition to.
        """
        pass


class SimpleEdge(Edge):
    """
    A simple edge representing a direct transition between agent nodes.

    Attributes:
        target (Agent): The target agent node to be executed after the transition.
    """
    target_agent: Agent = Field(description="Target agent node to be executed after the transition.")

    def get_next_node(self, src_output_args: AgentArguments) -> str:
        # Always return the target agent node.
        return self.target_agent.name_id


class ConditionalEdge(Edge):
    """
    A conditional edge for transitioning between agent nodes based on a function.

    Attributes:
        condition_fn (Callable[[BaseModel], str]): A function that determines the next Agent's id based on the source Agent's output arguments.
    """
    condition_fn: Callable[[AgentArguments], str] = Field(description="A function that determines the next Agent's id based on the source Agent's output arguments.")

    def get_next_node(self, src_output_args: AgentArguments) -> str:
        # Use the condition function to determine the next agent node.
        target_agent_id = self.condition_fn(src_output_args)
        return target_agent_id