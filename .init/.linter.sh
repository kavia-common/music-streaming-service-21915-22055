#!/bin/bash
cd /home/kavia/workspace/code-generation/music-streaming-service-21915-22055/BackendAPI
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

