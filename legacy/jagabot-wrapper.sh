#!/bin/bash
# jagabot-wrapper.sh - Wrapper script that ensures API keys are loaded

# Load ~/.bashrc to get API keys
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi

# Load from .env if it exists
if [ -f ~/.jagabot/.env ]; then
    set -a
    source ~/.jagabot/.env
    set +a
fi

# Run jagabot with all arguments
exec jagabot "$@"
