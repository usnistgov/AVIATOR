# AVIATOR: Towards AI-Agentic Vulnerability Injection Workflow for High-Fidelity, Large-Scale Code Security Dataset

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)


## 📝 Abstract
The increasing complexity of software systems and the sophistication of cyber-attacks have underscored the critical need for reliable automated software vulnerability detection. Data-driven approaches using deep learning models show promise but critically depend on the availability of large, accurately labeled datasets. Yet existing datasets either suffer from noisy labels, limited vulnerability coverage, or fail to reflect vulnerabilities as they occur in real-world software. This also limits large-scale benchmarking of such solutions. Automated vulnerability injection provides a way to address these limitations, but existing techniques remain limited in coverage, contextual fidelity, or injection success.
In this paper, we present AVIATOR, the first AI-agentic vulnerability injection framework. AVIATOR decomposes vulnerability injection into a coordinated workflow of specialized AI agents, tool-based analysis, and iterative self-correction, explicitly mirroring expert reasoning. It integrates RAG and lightweight LoRA-based fine-tuning to produce realistic, category-specific vulnerabilities without relying on handcrafted patterns.
Across three benchmarks, AVIATOR achieves high injection fidelity (91-95\%) surpassing existing injection techniques in both accuracy and vulnerability coverage. When used for data augmentation to train deep learning-based vulnerability detection (DLVD) models, AVIATOR provides the strongest downstream gains in vulnerability detection. Across models and base datasets, AVIATOR improves average F1 scores by +22\% over no augmentation, +25\% over VGX, holding the prior best injection success rate, and +3\% over VulScribeR, the prior state-of-the-art LLM-based injection model, with +7\% higher recall and no precision loss. Its augmented data exhibits the lowest distributional distortion and scales efficiently with <2% syntax rejection at 4.3× lower cost than VulScribeR.

## 🏗️ Repository Structure

This repository contains the implementation of the AVIATOR framework, which consists of the following main components:

### 🤖 awe
A low-code Python library for building and executing AI agentic workflows. This library provides the core functionality for implementing the workflow orchestration in AVIATOR. It supports:
- AI agents and tool agents
- Comprehensive logging and experiment reproducibility
- Error recovery and extensibility
- Workflow configuration through JSON files

### 🔄 LoRA_FT
Contains the implementation of the fine-tuning approaches used in AVIATOR:
- Supervised Fine-Tuning (SFT)
- Generative Reward-Penalized Optimization (GRPO)
- Low-Rank Adaptation (LoRA) for efficient model fine-tuning

### 📊 validation_dataset
Contains the datasets or links to the datasets used for validating the AVIATOR framework in the paper:
- Test cases and benchmarks
- Evaluation metrics and results
- Ground truth data for vulnerability injection

### 🛠️ vul_code_gen
The main implementation of the AVIATOR vulnerability injection workflow, including:
- Agent implementations for vulnerability injection
- Integration with code analysis tools
- RAG implementation for contextual grounding
- Workflow configurations and examples

## 🚀 Installation

### Prerequisites
- Python>=3.11
- uv

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/aviator.git
cd AVIATOR/
```

2. Create the virtual environment and install dependencies:
```bash
uv sync
```

3. Install ESBMC (for code verification):
```bash
wget https://github.com/esbmc/esbmc/releases/download/v7.5/ESBMC-Linux.zip && unzip -d esbmc ESBMC-Linux.zip && rm ESBMC-Linux.zip && chmod +x esbmc/bin/esbmc
```

## 📦 Dependencies

### Core Dependencies
- [unsloth (2025.3.19)](https://pypi.org/project/unsloth/) - Efficient model fine-tuning
- [pydantic (2.11.1)](https://docs.pydantic.dev/latest/) - Data validation
- [langchain-huggingface (0.1.2)](https://python.langchain.com/docs/integrations/providers/huggingface/) - LLM integration
- [langchain_chroma (0.2.2)](https://api.python.langchain.com/en/latest/vectorstores/langchain_chroma.vectorstores.Chroma.html) - Vector storage
- [langchain_text_splitters (0.3.7)](https://api.python.langchain.com/en/latest/text_splitters_api_reference.html) - Text processing
- [xformers (0.0.29.post3)](https://pypi.org/project/xformers/) - Transformer optimization
- [codebleu (0.7.1)](https://pypi.org/project/codebleu/) - Code evaluation
- [tree-sitter-cpp (0.21.0)](https://pypi.org/project/tree-sitter/) - C++ parsing
- [clang-format (20.1.0)](https://pypi.org/project/clang-format/) - Code formatting
- [openai (1.72.0)](https://pypi.org/project/openai/) - OpenAI API integration

### Additional Dependencies
- PyTorch (>=2.0.0)
- Transformers (>=4.30.0)
- Accelerate (>=0.20.0)

## 📚 Datasets

The Primevul dataset used for training and validation is accessible through: [Primevul Dataset](https://drive.google.com/drive/folders/1cznxGme5o6A_9tT8T47JUh3MPEpRYiKK)

The FormAI dataset used for validation is accessible through: [FormAI Dataset](https://github.com/FormAI-Dataset)

The SARD100 dataset used for validation is accessible through: [SARD100](https://samate.nist.gov/SARD/test-suites/100)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
