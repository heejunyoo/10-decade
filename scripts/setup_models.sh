#!/bin/bash
# Local LLM Setup Script
# Upgrades the 3B model to 8B for better Korean performance.

MODEL_NAME="llama3.1:8b"

echo "🧠 Checking Local AI Models..."

if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed! Please install it from https://ollama.com first."
    exit 1
fi

echo "🚀 Pulling $MODEL_NAME (This may take a while depending on internet speed)..."
ollama pull "$MODEL_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Model $MODEL_NAME installed successfully!"
    echo "   The app will now automatically prefer this model."
else
    echo "❌ Failed to pull model. Please try running 'ollama pull $MODEL_NAME' manually."
fi
