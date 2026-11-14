#!/bin/sh
# Builds the sandbox image that every submission runs in.
set -eu
cd "$(dirname "$0")/.."
docker build -t "${SANDBOX_IMAGE:-topranker-sandbox:latest}" sandbox
