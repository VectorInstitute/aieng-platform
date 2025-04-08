#!/bin/bash

# Script to deploy GitHub MCP server

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
  echo "Error: Docker is not installed!"
  echo "Please install Docker and try again."
  exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Creating sample .env file. Edit it with your GitHub token."
  echo "GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here" > .env
  chmod 600 .env
  echo "Please edit the .env file with your GitHub token and run this script again."
  exit 1
fi

# Load environment variables from .env file
source .env

# Check if GitHub token is available
if [ -z "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
  echo "Error: GITHUB_PERSONAL_ACCESS_TOKEN not found in .env file!"
  exit 1
fi

# Stop any existing containers
docker stop github-mcp-server 2>/dev/null || true

# User feedback
echo "Starting GitHub MCP server..."
echo "Server will be available at http://localhost:8092"
echo "Use Ctrl+C to stop the server"

# Run the GitHub MCP server using Docker with exposed port
docker run -i --rm \
    --name github-mcp-server \
    -p 8092:8080 \
    -e GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN" \
    -e TRANSPORT_MODE=http \
    ghcr.io/github/github-mcp-server:latest

echo "GitHub MCP server stopped."
