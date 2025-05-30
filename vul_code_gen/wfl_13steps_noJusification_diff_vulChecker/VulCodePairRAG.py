import hashlib
import logging
from tqdm import tqdm
import pandas as pd

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

# Import the abstract RAG class (assumed to be the one you provided before)
from awe import RAG

# Module-specific logger
logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler())


class ChromaVulCodePairRAG(RAG):
    """
    A RAG implementation that indexes pairs of corresponding vulnerable and benign source code samples
    using a Chroma vector store for persistence and similarity search.

    The vector store is built on the embeddings of the benign code. For retrieval, a query benign code
    is embedded and used to search the vector store (optionally filtered by a vulnerability ID). The
    returned entries contain both the benign and vulnerable code samples.
    """

    def _load_embedding_model(self) -> HuggingFaceEmbeddings:
        """
        Loads the HuggingFace embedding model.
        """
        logger.info(f"Loading HuggingFace embedding model: {self.embedding_model_path}")

        # Wrap it with HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model_path,
            cache_folder=self.embedder_cache_path,
            model_kwargs={"trust_remote_code": True}
        )

    def _load_db(self) -> Chroma:
        """
        Loads (or creates) the Chroma vector store from disk.
        """
        logger.info(f"Loading Chroma vector store from {self.knowledge_base_path}.")
        return Chroma(
            embedding_function=self._embedding_model,
            persist_directory=self.knowledge_base_path
        )

    def _chunk_code(self, code: str, max_embed_context_size: int, language=Language.CPP) -> list[str]:
        """
        Optionally splits long code into chunks using RecursiveCharacterTextSplitter.

        Args:
            code (str): The code to split.
            max_embed_context_size (int): Maximum size for each chunk.
            language: Language type for splitting (default: Python).

        Returns:
            list[str]: List of code chunks.
        """
        if len(code) > max_embed_context_size:
            text_splitter = RecursiveCharacterTextSplitter.from_language(
                language=language, chunk_size=max_embed_context_size, chunk_overlap=50
            )
            return text_splitter.split_text(code)
        else:
            return [code]

    def _get_pair_hash(self, benign: str, vul_id: str) -> str:
        """
        Computes a unique hash for a code pair (using the benign code and vulnerability ID).

        Args:
            benign (str): The benign code.
            vul_id (str): The vulnerability ID.

        Returns:
            str: MD5 hash string.
        """
        # Combining benign code and vulnerability ID helps differentiate pairs.
        hash_input = benign + vul_id
        return hashlib.md5(hash_input.encode()).hexdigest()

    def index(self, data: pd.DataFrame, max_embed_context_size: int) -> None:
        """
        Indexes code pairs into the Chroma vector store. For each row in the input DataFrame,
        the benign code is embedded (optionally after splitting into chunks) and added to the store
        along with metadata (the vulnerable code and vulnerability ID).

        Args:
            data (pd.DataFrame): DataFrame with columns: "benign", "vulnerable", "vul_id".
            max_embed_context_size (int): Maximum allowed size for a text chunk to embed.
        """

        # Retrieve existing ids from the vector store to avoid duplicate indexing.
        existing_ids = set(self._knowledge_base.get(include=[])['ids'])

        logger.info("Indexing code pairs into the Chroma vector store.")

        # Generate embeddings and index knowledge base
        for _, row in tqdm(data.iterrows(), total=len(data.index), desc="Indexing"):
            benign_code = str(row["benign"])
            vulnerable_code = str(row["vulnerable"])
            vul_id = str(row["vul_id"])

            # Generate an identifier for this code pair.
            pair_id = self._get_pair_hash(benign_code, vul_id)
            
            if pair_id not in existing_ids:
                # Optionally, chunk the benign code if it is longer than allowed.
                chunks = self._chunk_code(benign_code, max_embed_context_size)

                for chunk in chunks:
                    metadata = {
                        "vul_id": vul_id,
                        "benign": benign_code,      # full benign code
                        "vulnerable": vulnerable_code  # full vulnerable code
                    }
                    self._knowledge_base.add_texts([chunk], metadatas=[metadata], ids=[pair_id])

        logger.info(f"✅ Finished indexing. Embeddings persisted at {self.knowledge_base_path}.")

    def retrieve_relevant(self, retrieval_query: str, vul_id: str, top_k: int = 5) -> list[dict]:
        """
        Retrieves the top_k code pairs whose benign code is most similar to the query,
        filtering by the requested vulnerability ID (provided as keyword argument 'vul_id').

        Args:
            retrieval_query (str): The benign code snippet to query against the index.
            top_k (int): Number of top results to return.
            vul_id (str): The target vulnerability category ID for the code snippet (e.g., "89" for SQL Injection).
            
        Returns:
            List[dict]: A list of dictionaries for each matching code pair with keys:
                        "benign", "vulnerable", and "vul_id".
        """

        # Perform a similarity search on the benign code with a metadata filter for vul_id.
        result = self._knowledge_base.similarity_search_with_score(
            retrieval_query,
            k=top_k,
            filter={"vul_id": vul_id}
        )

        # Each result is a tuple (doc, score) where doc.metadata contains our stored data.
        results = []
        for doc, score in result:
            # Return the full pair information.
            metadata = doc.metadata
            results.append(
                format_annotated_example(
                    metadata.get("benign"),
                    metadata.get("vulnerable")
                )
            )
        return results



from typing import List, Tuple
import difflib

def find_differences(benign: str, vulnerable: str) -> List[Tuple[int, str, str]]:
    """
    Finds line-by-line differences between benign and vulnerable code.
    
    Returns:
        List of tuples (line_number, benign_line, vulnerable_line)
        for lines that differ
    """
    benign_lines = benign.splitlines()
    vulnerable_lines = vulnerable.splitlines()
    
    differ = difflib.Differ()
    diffs = list(differ.compare(benign_lines, vulnerable_lines))
    
    changes = []
    benign_idx = 0
    vuln_idx = 0
    
    for diff in diffs:
        if diff.startswith('  '):  # unchanged line
            benign_idx += 1
            vuln_idx += 1
        elif diff.startswith('- '):  # line only in benign
            changes.append((benign_idx, diff[2:], None))
            benign_idx += 1
        elif diff.startswith('+ '):  # line only in vulnerable
            changes.append((vuln_idx, None, diff[2:]))
            vuln_idx += 1
            
    return changes

def format_annotated_example(benign_code: str, vulnerable_code: str) -> str:
    """
    Creates a single annotated code example showing vulnerability introduction points.
    """
    changes = find_differences(benign_code, vulnerable_code)
    
    # Start with benign code lines
    benign_lines = benign_code.splitlines()
    annotated_lines = []
    
    # Track if we're inside a diff block
    in_diff_block = False
    
    for i, line in enumerate(benign_lines):
        # Check if this line has any changes
        matching_changes = [c for c in changes if c[0] == i]
        
        if matching_changes:
            if not in_diff_block:
                annotated_lines.append("// Begin vulnerability introduction")
                in_diff_block = True
                
            # Show both versions with annotations
            annotated_lines.append(f"// Secure version:")
            annotated_lines.append(f"// {line}")
            annotated_lines.append(f"// Vulnerable version:")
            vuln_line = next((c[2] for c in matching_changes if c[2] is not None), None)
            if vuln_line:
                annotated_lines.append(vuln_line)
            else:
                annotated_lines.append("// (Line removed)")
                
            annotated_lines.append("// End vulnerability introduction")
            in_diff_block = False
        else:
            # Unchanged line
            annotated_lines.append(line)
    
    template = """// Example showing how a benign code has been modified to introduce the vulnerability
{}

---""".format('\n'.join(annotated_lines))
    return template.strip()