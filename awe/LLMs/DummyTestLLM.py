from awe.LLMs.LLM import LLM
from pydantic import Field
from typing import Callable

class DummyTestLLM(LLM):
    """
    Dummy LLM model for quick test purposes.

    Attributes:
        dummy_function (Callable[[any], any]): Function that will be executed instead of the LLM.
    """
    dummy_function: Callable[[str], str] = Field(description="Function that will be executed instead of the LLM.")

    def _create_message(self, user_prompt: str) -> str:
        return user_prompt

    def _send_message(self, messages: str, max_tokens: int) -> str:
        return self.dummy_function(messages)
    
    def _get_response(self, response: str) -> any:
        return response

