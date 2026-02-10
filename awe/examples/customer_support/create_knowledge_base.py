#########################################################################
# 1) Sign in to Hugging Face by running this command: hf auth login

import os
import sys
from pathlib import Path

# Ensure awe package is importable (no PYTHONPATH needed when run from repo)
_src = Path(__file__).resolve().parent.parent.parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
#########################################################################
import pandas as pd
from customer_support_rag import SupportKnowledgeRAG
import logging

logger = logging.getLogger(__name__)

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Load the knowledge base
df = pd.read_csv(os.path.join(current_dir, "knowledge_base_data/articles.csv"))

# Initialize the RAG system
rag = SupportKnowledgeRAG(
    embedding_model_path="intfloat/multilingual-e5-large-instruct",
    knowledge_base_path=os.path.join(current_dir, "support_knowledge_base")
)

# Index the knowledge base
rag.index(
    data=df,
    max_embed_context_size=1000
)

logger.info("Knowledge base successfully indexed!")