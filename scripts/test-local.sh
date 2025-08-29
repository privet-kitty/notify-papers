#!/bin/bash

# Local testing script for Report Papers AI Agent

set -e

echo "🧪 Testing Report Papers AI Agent locally"

# Check environment variables
if [ -z "$S3_CONFIG_BUCKET" ] || [ -z "$EMAIL_RECIPIENT" ]; then
    echo "❌ Missing required environment variables:"
    echo "   S3_CONFIG_BUCKET, EMAIL_RECIPIENT"
    echo ""
    echo "Set them like this:"
    echo "export S3_CONFIG_BUCKET=your-s3-bucket"
    echo "export EMAIL_RECIPIENT=your-email@example.com"
    echo ""
    echo "Optional environment variables:"
    echo "export AWS_BEDROCK_REGION=us-east-1  # Default region"
    echo "export LLM_MODEL=anthropic.claude-3-haiku-20240307-v1:0  # Default model"
    exit 1
fi

# Check AWS credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -z "$AWS_PROFILE" ]; then
    echo "❌ AWS credentials not found"
    echo "Please set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE"
    exit 1
fi

echo "✅ Environment variables set"

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "📦 Installing dependencies..."
    uv sync
fi

echo "🏃 Running configuration test..."
uv run python -m src.report_papers.main

echo ""
echo "✅ Local test completed!"
echo "Check the output above for any errors or warnings."