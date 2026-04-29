#!/bin/bash

# SyncMCP Setup Script for macOS/Linux

echo "🚀 Setting up SyncMCP..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies in editable mode
echo "Checking and installing dependencies (LiteLLM, Gemini, etc.)..."
pip install -e .

# Initialize global store
echo "Initializing global store..."
ctx setup

echo "✅ Setup complete! You can now run 'ctx init' in any project."
echo "💡 To use AI scanning, set your SYNC_MODEL and API key in .env or system env vars."
