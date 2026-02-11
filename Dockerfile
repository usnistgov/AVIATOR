# AVIATOR: AI-agentic vulnerability injection workflow
# Python 3.11, uv, ESBMC, cppcheck, PrimeVul (optional), RAG index
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV AVIATOR_ROOT=/app/AVIATOR
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Build args for optional setup steps
ARG SKIP_ESBMC=0
ARG SKIP_CPPCHECK=0
ARG SKIP_PRIMEVUL_DOWNLOAD=0

# Install system deps: uv, build tools, wget, unzip, git, cppcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    unzip \
    git \
    make \
    g++ \
    cppcheck \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project into AVIATOR root (build context: AVIATOR repo root)
WORKDIR /app/AVIATOR
COPY pyproject.toml uv.lock .python-version ./
COPY awe ./awe
COPY vul_code_gen ./vul_code_gen
COPY LoRA_FT ./LoRA_FT
COPY scripts ./scripts
COPY validation_dataset ./validation_dataset
COPY LICENSE ./

# Sync Python deps
RUN uv sync

# Install ESBMC
RUN if [ "$SKIP_ESBMC" = "0" ]; then \
    mkdir -p static_tools && \
    wget -q https://github.com/esbmc/esbmc/releases/download/v7.5/ESBMC-Linux.zip -O static_tools/ESBMC-Linux.zip && \
    unzip -o -d static_tools/esbmc static_tools/ESBMC-Linux.zip && rm -f static_tools/ESBMC-Linux.zip && \
    chmod +x static_tools/esbmc/bin/esbmc 2>/dev/null || find static_tools -name esbmc -type f -exec chmod +x {} \; ; \
    else echo "Skipping ESBMC"; fi

# Cppcheck: use system binary, create expected path
RUN if [ "$SKIP_CPPCHECK" = "0" ]; then \
    mkdir -p static_tools/cppcheck/bin && \
    ln -sf /usr/bin/cppcheck static_tools/cppcheck/bin/cppcheck; \
    else echo "Skipping cppcheck"; fi

# Download PrimeVul (optional)
RUN if [ "$SKIP_PRIMEVUL_DOWNLOAD" = "0" ]; then \
    uv pip install gdown && \
    mkdir -p data/PrimeVul_v0.1 && \
    gdown "https://drive.google.com/uc?id=1yqMzbjB7Apo3E1lOmLbhQxvSkpS8r-hk" -O data/PrimeVul_v0.1/primevul_train_paired.jsonl && \
    gdown "https://drive.google.com/uc?id=1yv-lTCbcwRmmYFzkk6PSnJNpxR9KxA0z" -O data/PrimeVul_v0.1/primevul_test_paired.jsonl && \
    gdown "https://drive.google.com/uc?id=1aI7pGuMOgq3dn9w6g_QAv7cjDmWU1vKt" -O data/PrimeVul_v0.1/primevul_valid_paired.jsonl || true; \
    else echo "Skipping PrimeVul download (mount data/ at runtime)"; mkdir -p data/PrimeVul_v0.1; fi

# Index RAG (only if PrimeVul exists)
RUN if [ -f data/PrimeVul_v0.1/primevul_train_paired.jsonl ]; then \
    uv run python vul_code_gen/index_knowledge_base.py --primevul_paired_path data/PrimeVul_v0.1/primevul_train_paired.jsonl; \
    else echo "Skipping RAG index (no primevul_train_paired.jsonl)"; fi

WORKDIR /app/AVIATOR

# Default: show run_injection help. To run: docker run aviator scripts/run_injection.sh --dataset-path ...
# For eval: docker run aviator scripts/run_injection_with_eval.sh --dataset-path ...
ENTRYPOINT ["/bin/bash"]
CMD ["scripts/run_injection.sh", "--help"]
