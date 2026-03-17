# Thinky Dev Sandbox
# Based on trailofbits/claude-code-devcontainer, adapted for org use
ARG UV_VERSION=0.10.0
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ARG TZ
ENV TZ="$TZ"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
  bubblewrap \
  socat \
  fd-find \
  ripgrep \
  tmux \
  zsh \
  build-essential \
  jq \
  nano \
  unzip \
  vim \
  dnsutils \
  ipset \
  iptables \
  iproute2 \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install git-delta
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  curl -fsSL "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" -o /tmp/git-delta.deb && \
  dpkg -i /tmp/git-delta.deb && \
  rm /tmp/git-delta.deb

# Install uv
COPY --from=uv /uv /usr/local/bin/uv

# Install fzf
ARG FZF_VERSION=0.67.0
RUN ARCH=$(dpkg --print-architecture) && \
  case "${ARCH}" in \
    amd64) FZF_ARCH="linux_amd64" ;; \
    arm64) FZF_ARCH="linux_arm64" ;; \
    *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
  esac && \
  curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-${FZF_ARCH}.tar.gz" | tar -xz -C /usr/local/bin

# Create directories and set ownership
RUN mkdir -p /commandhistory /workspace /home/vscode/.claude /home/vscode/.codex /opt && \
  touch /commandhistory/.bash_history && \
  touch /commandhistory/.zsh_history && \
  chown -R vscode:vscode /commandhistory /workspace /home/vscode/.claude /home/vscode/.codex /opt

ENV DEVCONTAINER=true
ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano

WORKDIR /workspace

USER vscode

ENV PATH="/home/vscode/.local/bin:$PATH"

# Install Claude Code (no third-party plugins)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install Codex CLI
RUN npm install -g @openai/codex 2>/dev/null || echo "Codex CLI install skipped (npm not yet available)"

# Install Python 3.13 via uv
RUN uv python install 3.13 --default

# Install ast-grep
RUN uv tool install ast-grep-cli

# Install fnm and Node 22
ARG NODE_VERSION=22
ENV FNM_DIR="/home/vscode/.fnm"
RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir "$FNM_DIR" --skip-shell && \
  export PATH="$FNM_DIR:$PATH" && \
  eval "$(fnm env)" && \
  fnm install ${NODE_VERSION} && \
  fnm default ${NODE_VERSION}

# Install Codex CLI (now that Node is available)
RUN export PATH="$FNM_DIR:$PATH" && \
  eval "$(fnm env)" && \
  npm install -g @openai/codex

# Install Oh My Zsh
ARG ZSH_IN_DOCKER_VERSION=1.2.1
RUN sh -c "$(curl -fsSL https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
  -p git \
  -x

# Copy zsh configuration
COPY --chown=vscode:vscode .zshrc /home/vscode/.zshrc.custom
RUN echo 'source ~/.zshrc.custom' >> /home/vscode/.zshrc

# Copy org configs into the image
COPY --chown=vscode:vscode org-configs/settings.json /opt/org-settings.json
COPY --chown=vscode:vscode org-configs/CLAUDE.md /opt/org-CLAUDE.md
COPY --chown=vscode:vscode org-configs/codex-config.toml /opt/org-codex-config.toml

# Copy post_install script
COPY --chown=vscode:vscode post_install.py /opt/post_install.py
