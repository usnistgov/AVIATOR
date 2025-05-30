from awe.LLMs import LLM
from pydantic import Field
from typing import Optional, Dict, Any, List, Union
import openai
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class OpenAICompatibleLLM(LLM):
    """
    LLM wrapper for OpenAI API and compatible endpoints.
    
    This class uses the OpenAI client to interact with OpenAI-compatible APIs,
    supporting both official OpenAI endpoints and custom API endpoints.

    Attributes:
        base_url (Optional[str]): Base URL of the API endpoint (e.g., "https://api.openai.com/v1" or custom endpoint).
        api_key (str): API key for authentication.
        model (str): Model identifier to use for generating completions.
        temperature (float): Controls randomness in responses. Lower is more deterministic.
        top_p (float): Controls diversity via nucleus sampling. 1.0 means no filtering.
        timeout (int): Request timeout in seconds.
    """
    base_url: Optional[str] = Field(description="Base URL of the API endpoint")
    api_key: str = Field(description="API key for authentication")
    model: str = Field(description="Model identifier to use for generating completions")
    temperature: float = Field(default=1.0, description="Controls randomness in responses")
    top_p: float = Field(default=1.0, description="Controls diversity via nucleus sampling")
    
    def model_post_init(self, __context: any) -> None:
        load_dotenv()
        
        # Initialize the OpenAI client with custom configuration
        try:
            self._client = openai.OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                http_client=httpx.Client(verify=False)
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise Exception(f"Failed to initialize OpenAI client: {str(e)}")

    def _create_message(self, user_prompt: str) -> List[Dict[str, str]]:
        """
        Format user prompt to construct a message in the OpenAI format.
        
        Args:
            user_prompt (str): Raw user prompt.
        
        Returns:
            List[Dict[str, str]]: Formatted prompt messages.
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _send_message(self, messages: List[Dict[str, str]], max_tokens: int) -> Dict[str, Any]:
        """
        Send a request to the API using the OpenAI client.

        Args:
            messages (List[Dict[str, str]]): Formatted full prompt messages.
            max_tokens (int): Maximum number of output tokens.

        Returns:
            Dict[str, Any]: Raw response from the API.
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                stream=False,
                messages=messages,
            )
            return response
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise Exception(f"Failed to communicate with API: {str(e)}")

    def _get_response(self, response: Dict[str, Any]) -> str:
        """
        Extract textual answer from the API's response.

        Args:
            response: API's response object.
        
        Returns:
            str: Extracted textual response.
        """
        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError) as e:
            logger.error(f"Failed to parse API response: {str(e)}")
            logger.debug(f"Received response: {response}")
            raise Exception(f"Failed to parse API response: {str(e)}") 