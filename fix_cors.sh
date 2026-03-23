#!/bin/bash
echo "Fixing Ollama CORS..."
curl -s -X OPTIONS "http://david-x570:11434/api/generate" -i | grep Access-Control-Allow-Origin
echo "If Ollama CORS is not allowing your domain, you need to restart the ollama service on david-x570 with:"
echo "OLLAMA_ORIGINS=\"*\" ollama serve"
