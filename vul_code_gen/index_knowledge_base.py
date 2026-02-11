#########################################################################
# 1) Sign in to Hugging Face by running this command: hf auth login
#########################################################################

import argparse
import os
import sys
from pathlib import Path

# Makes the project root importable (awe, vul_code_gen)
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from vul_code_gen.AVIATOR_13steps_full_workflow.VulCodePairRAG import ChromaVulCodePairRAG
from vul_code_gen.dataset_utils import load_primevul_vul_pairs

script_dir = os.path.dirname(os.path.abspath(__file__))

### Parameters for the RAG
vector_store_path = f"{script_dir}/chromadb"
# huggingface_embedder_name="NovaSearch/stella_en_400M_v5"
huggingface_embedder_name = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
embedder_cache_path = f"{script_dir}/model_cache/embedder"
max_embed_context_size = 8192  # The limit for stella_en_400M_v5


def _patch_transformers_cache_for_gte_qwen():
    """Compat for Alibaba-NLP/gte-Qwen2: model code calls get_usable_length, removed in transformers 4.56+."""
    try:
        from transformers import cache_utils
        if not hasattr(cache_utils.DynamicCache, "get_usable_length"):
            def get_usable_length(self, new_seq_length=None, layer_idx=0):
                return self.get_seq_length(layer_idx)
            cache_utils.DynamicCache.get_usable_length = get_usable_length
    except Exception:
        pass


def main():
    _patch_transformers_cache_for_gte_qwen()
    parser = argparse.ArgumentParser(
        description="Index PrimeVul train paired data into the RAG knowledge base (Chroma)."
    )
    parser.add_argument(
        "--primevul_paired_path",
        type=str,
        required=True,
        help="Path to primevul_train_paired.jsonl (used for RAG).",
    )
    args = parser.parse_args()
    primevul_paired_knowledge_base_data_path = args.primevul_paired_path

    if not os.path.isfile(primevul_paired_knowledge_base_data_path):
        print(
            f"Error: Not a file or not found: {primevul_paired_knowledge_base_data_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    vul_code_rag = ChromaVulCodePairRAG(
        embedding_model_path=huggingface_embedder_name,
        embedder_cache_path=embedder_cache_path,
        knowledge_base_path=vector_store_path,
    )
    df_knowledge_base = load_primevul_vul_pairs(primevul_paired_knowledge_base_data_path)
    vul_code_rag.index(df_knowledge_base, max_embed_context_size)


if __name__ == "__main__":
    main()