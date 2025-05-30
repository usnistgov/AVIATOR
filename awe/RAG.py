from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class RAG(BaseModel, ABC):
    """
    Abstract class to handle the logic for the different steps of a RAG before the generation of the answer using an LLM.
    Steps include: indexing the knowledge base (should be done once forever), retrieving data from the knowledge base that is most similar to an input query.

    Attributes:
        embedding_model_path (str): The path to the embedding model used for encoding the knowledge base.
        embedder_cache_path (str, optional): The path where to cache the model.
        knowledge_base_path (str): The path where the indexed knowledge base is stored.
    """
    embedding_model_path: str = Field(description="The path to the embedding model used for encoding the knowledge base.")
    embedder_cache_path: str | None = Field(default=None, description="The path where to cache the model.")
    knowledge_base_path: str = Field(description="The path where the indexed knowledge base is stored.")
    
    def model_post_init(self, __context: any) -> None:
        """
        Pydantic class initialization: load the database.
        """
        self._embedding_model = self._load_embedding_model()
        self._knowledge_base = self._load_db()
    
    @abstractmethod
    def _load_embedding_model(self) -> any:
        """
        Function to load the embedding model.

        Returns:
            any: The loaded embedding model.
        """
        pass

    @abstractmethod
    def _load_db(self) -> any:
        """
        Function to load the database. Called after the embedding model was loaded.

        Returns:
            any: The loaded database.
        """
        pass
    
    # @abstractmethod
    # def _clear_index(self) -> None:
    #     """
    #     Clear the existing index from the storage location.

    #     Returns:
    #         None
    #     """
    #     pass

    @abstractmethod
    def index(self, data: any, max_embed_context_size: int) -> None:
        """
        Index the provided data by generating embeddings and storing them in the knowledge base.

        Args:
            data (any): Data to index. Must adhere to the format requested by the Indexer child class.
            max_embed_context_size (int): Maximum size of each chunk for embedding.
        """
        pass
    
    @abstractmethod
    def retrieve_relevant(self, retrieval_query: str, top_k: int = 5, **kwargs: any) -> list[any]:
        """
        Retrieve the most relevant chunks of data for the given query.

        Args:
            retrieval_query (str): The query string to search in the knowledge base.
            top_k (int): The number of top results to retrieve. Defaults to 5.
            **kwargs (any): Additional keyword arguments for customization.

        Returns:
            list[any]: A list of most relevant retrieved data chunks.
        """
        pass