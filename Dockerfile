FROM mcr.microsoft.com/devcontainers/javascript-node:1-22-bookworm

RUN apt-get update -y \
    && export DEBIAN_FRONTEND=noninteractive
