from awe.LLMs import LLM
from pydantic import Field
from typing import Optional
import torch

# Import from submodules to avoid lazy-loader issues (e.g. pipeline not exposed in some envs)
from transformers.pipelines import pipeline
from transformers.generation import GenerationConfig

class HFpipeline(LLM):
    """
    LLM using HuggingFace pipeline library.

    Attributes:
        llm_path (str): The path of the LLM to use.
        FP16 (Optional[bool]): Enable FP16 precision inference optimization.
    """
    llm_path: str = Field(description="The path of the LLM to use.")
    FP16: Optional[bool] = Field(default=True, description="Enable FP16 precision inference optimization.")
    device: Optional[str] = Field(default="auto", description="Device to run the model on.")
    def model_post_init(self, __context: any) -> None:
        """
        Pydantic class initialization: load the HuggingFace pipeline.
        """
        self._llm = pipeline(
            'text-generation', 
            model=self.llm_path,
            torch_dtype=torch.bfloat16 if self.FP16 else None,
            device_map=self.device,
            trust_remote_code=True
        )
    
    @property
    def model(self):
        return self._llm.model

    @model.setter 
    def model(self, new_model):
        self._llm.model = new_model

    @property
    def tokenizer(self):
        return self._llm.tokenizer

    def _create_message(self, user_prompt: str) -> list[dict[str, str]]:
        messages = []
        if self.system_prompt != "": messages.append({"role": "system", "content": self.system_prompt}) 
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _send_message(self, messages: list[dict[str, str]], max_tokens: int) -> dict[str, any]:
        # Use GenerationConfig with only max_new_tokens to avoid conflict warning when the
        # model's default config sets max_length (e.g. 262144); see Hugging Face text generation docs.
        generation_config = GenerationConfig(
            max_new_tokens=max_tokens,
            max_length=None,  # avoid "max_new_tokens and max_length both set" warning
            pad_token_id=self._llm.tokenizer.eos_token_id,
        )
        response = self._llm(
            messages,
            generation_config=generation_config,
        )
        return response
    
    def _get_response(self, response: dict[str, any]) -> str:
        # Extract content where role is 'assistant'
        response = next(
            (item['content'] for item in response[0]['generated_text'] if item['role'] == 'assistant'),
            None  # Default value if no 'assistant' role is found
        )
        return response
