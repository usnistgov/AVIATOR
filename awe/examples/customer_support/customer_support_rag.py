import os
import json
import pandas as pd
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from awe import RAG

# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler())  # Avoid "No handlers could be found" warnings

class SupportKnowledgeRAG(RAG):
    """
    Handle the RAG logic for indexing and retrieval of customer support knowledge base,
    using a Chroma vector database and a HuggingFace embedding model.
    
    Attributes:
        embedding_model_path (str): The path to the embedding model used for encoding the knowledge base.
        embedder_cache_path (str): The path where to cache the model.
        knowledge_base_path (str): The path where the indexed knowledge base is stored.
    """

    def _load_embedding_model(self) -> any:
        # Initialize the HuggingFaceEmbeddings encoder with the specified parameters
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model_path,
            cache_folder=self.embedder_cache_path,
            model_kwargs={"trust_remote_code": True}  # Pass trust_remote_code through model_kwargs
        )
        
    def _load_db(self) -> any:
        # Initialize Chroma vector store
        logger.info(f"Loading Chroma vector database from {self.knowledge_base_path}.")
        return Chroma(embedding_function=self._embedding_model, persist_directory=self.knowledge_base_path)

    def _chunk_text(self, text: str, max_context_size: int) -> list[str]:
        """
        Splits text into smaller chunks using RecursiveCharacterTextSplitter.

        Args:
            text (str): The text to split.
            max_context_size (int): Maximum chunk size.

        Returns:
            list[str]: List of text chunks.
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_context_size,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return text_splitter.split_text(text)

    def index(self, data: pd.DataFrame, max_embed_context_size: int) -> None:
        """
        Index the provided data in the Chroma vector store.

        Args:
            data (pd.DataFrame): DataFrame containing knowledge base articles and metadata to index.
                Must contain columns 'content' (text) and 'category' (article category).
            max_embed_context_size (int): Maximum size of each chunk for embedding.
        """
        super().index(data, max_embed_context_size)

        # Get existing ids inside the database
        existing_ids = set(self._knowledge_base.get(include=[])['ids'])

        logger.info("Indexing input data into Chroma vector database.")

        # Generate embeddings and index knowledge base
        for idx, row in tqdm(data.iterrows(), total=len(data.index)):
            content = str(row['content'])
            category = str(row['category'])
            article_id = str(row.get('article_id', idx))

            # Only add articles that are not present in the DB
            if article_id not in existing_ids:
                chunks = self._chunk_text(content, max_embed_context_size)
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{article_id}_{i}"
                    metadata = {'category': category, 'article_id': article_id}
                    self._knowledge_base.add_texts([chunk], metadatas=[metadata], ids=[chunk_id])

        logger.info(f"✅ Embeddings saved to {self.knowledge_base_path}.")

    def retrieve_relevant(self, retrieval_query: str, top_k: int = 3, category: str = None) -> list[str]:
        """
        Retrieves the most relevant knowledge base articles for the given query.

        Args:
            retrieval_query (str): The query to search for in the knowledge base.
            top_k (int): The number of top results to retrieve. Defaults to 3.
            category (str, optional): Filter results by category.

        Returns:
            list[str]: List of relevant knowledge base articles.
        """
        # Prepare filter if category is provided
        filter_dict = {"category": category} if category else None
        
        # Use Chroma to perform a similarity search on the vector store
        result = self._knowledge_base.similarity_search_with_score(
            retrieval_query, 
            k=top_k, 
            filter=filter_dict
        )

        return [doc.page_content for doc, _score in result]