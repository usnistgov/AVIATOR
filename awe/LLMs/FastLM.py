from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template

from awe.LLMs import LLM

from pydantic import Field
from typing import Optional

class FastLM(LLM):
    """
    LLM using unsloth FastLanguageModel.

    Attributes:
        llm_path (str): The path of the LLM to use.
        max_seq_length (int): Maximum sequence length for the model.
        load_in_4bit (bool): Whether to load the model in 4-bit mode.
        dtype (Optional[str]): Data type for model weights (e.g. 'bfloat16'). Automatically finds the best dtype if not specified.
    """
    llm_path: str = Field(..., description="The name or path of the model to load.")
    max_seq_length: int = Field(default=2048, description="Maximum sequence length for the model.")
    load_in_4bit: bool = Field(default=False, description="Whether to load the model in 4-bit mode.")
    dtype: Optional[str] = Field(default=None, description="Data type for model weights (e.g. 'bfloat16').")
    # Internal attributes to hold the loaded model and tokenizer
    _model: any = None
    _tokenizer: any = None

    def model_post_init(self, __context: any = None) -> None:
        """
        Load the model and tokenizer using FastLanguageModel.from_pretrained,
        then set up fast inference mode and update the tokenizer with a chat template.
        """
        self._model, self._tokenizer = FastLanguageModel.from_pretrained(
            model_name=self.llm_path,
            max_seq_length=self.max_seq_length,
            dtype=self.dtype,
            load_in_4bit=self.load_in_4bit,
        )
        # Update the tokenizer with a chat template (e.g., "chatml")
        self._tokenizer.eos_token = "<|im_end|>"
        self._tokenizer = get_chat_template(
            self._tokenizer,
            chat_template = "qwen-2.5",
        )

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    @property
    def tokenizer(self):
        return self._tokenizer

    def _create_message(self, user_prompt: str) -> list[dict[str, str]]:
        messages = []
        if self.system_prompt != "":
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _send_message(self, messages: list[dict[str, str]], max_tokens: int) -> any:
        # First get the text template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Then tokenize separately
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_seq_length
        ).to("cuda")
        
        # Check if input length exceeds max_seq_length
        if inputs['input_ids'].shape[1] > self.max_seq_length:
            raise ValueError(f"Input length ({inputs['input_ids'].shape[1]} tokens) exceeds maximum sequence length ({self.max_seq_length} tokens)")
        
        outputs = self.model.generate(**inputs, max_new_tokens=max_tokens)
        # Record the length of the prompt (number of tokens)
        prompt_token_count = inputs["input_ids"].shape[1]
        # full_generated_ids includes both prompt and new tokens; extract the new token IDs only
        full_generated_ids = outputs[0]
        new_token_ids = full_generated_ids[prompt_token_count:]
        return new_token_ids

    def _get_response(self, response: any) -> dict[str, any]:
        raw_output = self.tokenizer.decode(response, skip_special_tokens=True)
        assistant_response = raw_output
        return assistant_response