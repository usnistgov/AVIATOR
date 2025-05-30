#########################################################################
# 1) Sign in to Hugging Face by running this command: huggingface-cli login
#
##### 2) RUN #####
### Execute this script:
# PYTHONPATH=/path/to/vul-code-gen python vul_code_gen/index_knowledge_base.py 
### Alternatively, uncomment code below
# Set project location to be able to call project modules 
import sys
sys.path.append("path/to/vul-code-gen")
#########################################################################

from vul_code_gen.VulCodePairRAG import ChromaVulCodePairRAG
from vul_code_gen.dataset_utils import load_primevul_vul_pairs

import os

script_dir = os.path.dirname(os.path.abspath(__file__))

### Parameters for the RAG
vector_store_path=f"{script_dir}/chromadb"

primevul_paired_knowledge_base_data_path="path/to/PrimeVul_v0.1/primevul_train_paired.jsonl"

# huggingface_embedder_name="NovaSearch/stella_en_400M_v5"
huggingface_embedder_name="Alibaba-NLP/gte-Qwen2-1.5B-instruct"
embedder_cache_path=f"{script_dir}/model_cache/embedder"
max_embed_context_size=8192 #The limit for stella_en_400M_v5

### Initialize the RAG handler class:
# Load the embedding model and indexer
vul_code_rag = ChromaVulCodePairRAG(
    embedding_model_path=huggingface_embedder_name,
    embedder_cache_path=embedder_cache_path,
    knowledge_base_path=vector_store_path
)

### Index knowledge base embeddings into a Chroma vector database
# Load data for the knowledge base to index
df_knowledge_base = load_primevul_vul_pairs(primevul_paired_knowledge_base_data_path)
# Index
vul_code_rag.index(df_knowledge_base, max_embed_context_size)