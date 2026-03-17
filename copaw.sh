#!/bin/bash
# CoPaw Manager - Quick Start Script
# 
# Usage:
#   ./copaw.sh          # Interactive mode
#   ./copaw.sh start    # Start all services
#   ./copaw.sh stop     # Stop all services
#   ./copaw.sh status   # Check status

cd /root/nanojaga

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run manager
python3 copaw_manager.py "$@"
