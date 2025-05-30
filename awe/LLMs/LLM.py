from pydantic import BaseModel, Field
from abc import ABC, abstractmethod

import logging

# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler()) # Avoid "No handlers could be found" warnings

class LLM(BaseModel, ABC):
    """
    Base LLM class to handle common LLM functionalities.

    Attributes:
        system_prompt (str): LLM system prompt that will be used for all prompts of this LLM.
    """
    system_prompt: str = Field(default="", description="LLM system prompt that will be used for all prompts of this LLM.")

    # def _log_response(self, response: dict[str, Any]) -> None:
    #     usage_info = response.usage.__dict__
    #     log.debug("Received chat response", extra={"usage": usage_info})

    @abstractmethod
    def _create_message(self, user_prompt: str):
        """
        Format user prompt to construct a message in the expected format.
        
        Args:
            user_prompt (str): Raw user prompt.
        
        Returns:
            Formatted prompt messages.
        """
        pass

    @abstractmethod
    def _send_message(self, messages: list[dict[str, str]], max_tokens: int) -> dict[str, any]:
        """
        LLM's response to the formatted input prompt message.

        Args:
            messages (list[dict[str, str]]): Formatted full prompt messages.
            max_tokens (int): Maximum number of output tokens.

        Returns:
            Raw response from the model.
        """
        pass

    @abstractmethod
    def _get_response(self, response: dict[str, any]) -> str:
        """
        Extract textual answer from LLM's raw response

        Args:
            response (dict[str, any]): LLM's raw response
        
        Returns:
            Extracted textual response.
        """
        pass

    def chat(self, user_prompt: str, max_tokens: int = 4096) -> str:
        """
        Full logic to get the LLM's response for a given user prompt. Stores model prompt and response to the conversation history. 

        Args:
            user_prompt (str): Raw user prompt.
            max_tokens (int): Maximum number of output tokens.

        Returns:
            : 
        """
        messages = self._create_message(user_prompt)
        response = self._send_message(messages, max_tokens) #, response_format_model
        # self._log_response(response)

        response_text = self._get_response(response)

        logger.info(f"⤵️  LLM raw output:\n{response_text}")
        return response_text
