#!/bin/bash
# Build script for Lambda deployment package

set -e

echo "📦 Building Lambda deployment package..."

# Remove old package
rm -f lambda-deployment-package.zip

# Use uv to build the package
echo "🔨 Building Python package with uv..."
uv build

# Create build directory
mkdir -p build/lambda

# Export dependencies to requirements.txt
echo "📋 Exporting dependencies..."
uv export --format requirements-txt --no-dev > build/requirements.txt

# Install dependencies to build directory
echo "⬇️ Installing dependencies..."
uv pip install -r build/requirements.txt --target build/lambda
uv pip install dist/*.whl --target build/lambda --no-deps

# Change to build directory
cd build/lambda

# Add source code
echo "📂 Adding source code..."
cp -r ../../src ./

# Create zip file
echo "🗜️ Creating deployment package..."
zip -r ../../lambda-deployment-package.zip . -x "*.pyc" "*/__pycache__/*" "*.egg-info/*"

# Return to project root and clean up
cd ../../
rm -rf build/

echo "✅ Lambda deployment package created: lambda-deployment-package.zip"
