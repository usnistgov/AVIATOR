#########################################################################
# 1) Sign in to Hugging Face by running this command: huggingface-cli login
#
##### 2) RUN #####
### Execute this script:
# PYTHONPATH=/path/to/vul-code-gen python awe/examples/customer_support/index_knowledge_base.py 
### Alternatively, uncomment code below
# Set project location to be able to call project modules 
import sys
sys.path.append("path/to/vul-code-gen")
#########################################################################

import os
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