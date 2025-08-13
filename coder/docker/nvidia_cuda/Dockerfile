FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update \
    && apt-get install -y \
    sudo \
    curl \
    git \
    jq \
    tar \
    unzip \
    python3 \
    python3-pip \
    python3-venv \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ARG USER=coder
RUN useradd --groups sudo --no-create-home --shell /bin/bash ${USER} \
    && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
    && chmod 0440 /etc/sudoers.d/${USER}

USER ${USER}
WORKDIR /home/${USER}
