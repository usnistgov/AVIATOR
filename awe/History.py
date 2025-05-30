from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import json
import logging

from awe.Agent import Agent, AgentArguments

# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler()) # Avoid "No handlers could be found" warnings

class HistoryRecord(BaseModel):
    """
    Represents a single record in the execution history.

    Attributes:
        timestamp (str): The UTC timestamp of the action.
        agent (str): The string representation of the agent that was executed.
        input_values (dict): The input arguments passed to the agent.
        output_values (dict): The output arguments returned by the agent.
        nb_retry (int): Number of retries for an agent if it fails due to invalid output.
        error (str): An error message if an exception occurred during execution.
    """
    timestamp: str = Field(description="The UTC timestamp of the action.")
    agent: str = Field(description="The string representation of the agent that was executed.")
    input_values: dict = Field(description="The input arguments passed to the agent.")
    output_values: Optional[dict] = Field(default=None, description="The output arguments returned by the agent.")
    formatted_prompt: Optional[str] = Field(description="LLM prompt with values inserted in placeholder.")
    raw_output: Optional[str] = Field(description="Unparsed LLM output.")
    nb_retry: Optional[int] = Field(default=0, description="Number of retries for an agent if it fails due to invalid output.")
    error: Optional[str] = Field(default=None, description="An error message if an exception occurred during execution.")

    def model_dump(self, **kwargs) -> dict:
        """Returns a dictionary containing only the non-None values from model_dump()."""
        """Overrides model_dump to exclude None values by default."""
        base_dump = super().model_dump(**kwargs)
        return {k: v for k, v in base_dump.items() if (v is not None and v!=0)}

class History(BaseModel):
    """
    Store the execution history of the workflow.
    """
    records: list[HistoryRecord] = Field(default_factory=list, description="The list of history records.")

    def add_record(self, agent: Agent, input_args: AgentArguments, output_args: AgentArguments = None, formatted_prompt: str = None, raw_output: str = None, nb_retry: int = 0, error: str = None):
        """
        Adds a new record to the history.

        Args:
            agent (Agent): The agent executed.
            input_args (dict): The input arguments provided to the agent.
            output_args (dict, optional): The output arguments returned by the agent. Defaults to None.
            formatted_prompt (str, optional): LLM prompt with values inserted in placeholder. 
            raw_output (str: optional): Unparsed LLM output.
            nb_retry (int, optional): Number of retries for an agent if it fails due to invalid output.
            error (str, optional): An error message if an exception occurred. Defaults to None.
        """
        agent_repr = repr(agent)
        input_values = input_args.model_dump()
        output_values = output_args.model_dump() if output_args else None

        record = HistoryRecord(
            timestamp=str(datetime.now()),
            agent=agent_repr,
            input_values=input_values,
            output_values=output_values,
            formatted_prompt=formatted_prompt,
            raw_output=raw_output,
            nb_retry=nb_retry,
            error=error
        )
        self.records.append(record)

    def to_json(self) -> str:
        """
        Serializes the entire history to a JSON string.

        Returns:
            str: The serialized JSON string.
        """
        return json.dumps([record.model_dump() for record in self.records], indent=2)

    def clear(self):
        """
        Clears the history.
        """
        self.records.clear()