#!/bin/bash

# Check for required configuration files
if [ ! -f /app/.env ] && [ ! -f /app/config.yaml ]; then
  echo "Error: Neither .env nor config.yaml found. Please mount at least one of them as a volume."
  exit 1
fi

# Start the application
exec python -m lecf.cli 