import torch
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any

class CustomTypeBase(BaseModel, ABC):
    """
    Abstract base class for all custom types.
    """

    @abstractmethod
    def __str__(self) -> str:
        """
        Get a string representation of the new data type. 
        """
        pass

class TensorEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that can handle PyTorch tensors.
    """
    def default(self, obj):
        if isinstance(obj, torch.Tensor):
            return obj.detach().cpu().tolist()
        # Let the base class default method handle other types
        return super().default(obj)

class TensorType(CustomTypeBase):
    """
    Custom type for torch.Tensor.
    """
    class Config:
        arbitrary_types_allowed = True

    tensor: Any = Field(description="The tensor to be serialized.")

    def __str__(self) -> str:
        """
        Get a string representation of the tensor.
        """
        return str(self.tensor)

    def model_dump(self, **kwargs) -> dict:
        """
        Serialize the model to a dictionary.

        Returns:
            dict: A dictionary representation of the model.
        """
        data = super().model_dump(**kwargs)
        if hasattr(self, 'tensor'):
            # Keep tensor as is - it will be handled by TensorEncoder
            data['tensor'] = self.tensor
        return data

    def model_dump_json(self, **kwargs) -> str:
        """
        Serialize the model to a JSON string.

        Returns:
            str: A JSON string representation of the model.
        """
        return json.dumps(self.model_dump(**kwargs), cls=TensorEncoder)