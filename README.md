# AVIATOR: Towards AI-Agentic Vulnerability Injection Workflow for High-Fidelity, Large-Scale Code Security Dataset

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)


## 📝 Abstract
The increasing complexity of software systems and the sophistication of cyber-attacks have underscored the critical need for effective automated vulnerability detection and repair systems. Traditional methods, such as static program analysis, face significant challenges related to scalability, adaptability, and high false-positive and false-negative rates. AI-driven approaches, particularly those using machine learning and deep learning models, show promise but are heavily reliant on the quality and quantity of training data. This paper introduces a novel framework designed to automatically introduce realistic, category-specific vulnerabilities into secure C/C++ codebases. The proposed approach coordinates multiple AI agents that simulate expert reasoning, along with function agents and traditional code analysis tools. It leverages Retrieval-Augmented Generation for contextual grounding and employs Low-Rank approximation of weights for efficient model fine-tuning. Our experimental study on 116 code samples from three different benchmarks suggests that our approach outperforms other techniques with regard to dataset accuracy, achieving between 89% and 95% success rate in injecting vulnerabilities. 

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
Contains the datasets used for validating the AVIATOR framework:
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
- Python 3.11
- CUDA 12.1 (for GPU support)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/aviator.git
cd aviator
```

2. Create and activate the conda environment:
```bash
conda create --name unsloth_env python=3.11 pytorch-cuda=12.1 pytorch cudatoolkit xformers -c pytorch -c nvidia -c xformers -y
conda activate unsloth_env
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install ESBMC (for code verification):
```bash
wget https://github.com/esbmc/esbmc/releases/download/v7.5/ESBMC-Linux.zip && unzip ESBMC-Linux.zip && rm ESBMC-Linux.zip && chmod 777 bin/esbmc
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
