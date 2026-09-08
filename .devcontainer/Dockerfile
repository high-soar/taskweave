FROM ghcr.io/astral-sh/uv:latest AS uv
FROM mcr.microsoft.com/devcontainers/base:ubuntu

COPY --from=uv /uv /usr/local/bin/
COPY --from=uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ボリュームマウント先ディレクトリを事前に作成しvscodeユーザーに所有権を付与
RUN mkdir -p \
    /home/vscode/.copilot \
    /home/vscode/.gemini \
    /home/vscode/.vscode-server/data/User/globalStorage/github.copilot-chat \
    /home/vscode/.vscode-server/bin \
    && chown -R vscode:vscode /home/vscode
