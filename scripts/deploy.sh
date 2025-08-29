#!/bin/bash

# Deployment script for Report Papers AI Agent

set -e

echo "🚀 Deploying Report Papers AI Agent"

# Check if terraform.tfvars exists
if [ ! -f "terraform/terraform.tfvars" ]; then
    echo "❌ terraform/terraform.tfvars not found"
    echo "Please copy terraform/terraform.tfvars.example to terraform/terraform.tfvars and fill in your values"
    exit 1
fi

# Create deployment package (fallback for non-container deployment)
echo "📦 Creating deployment package..."
rm -f lambda-deployment-package.zip

# Use uv to create a clean environment and package
uv build

# Export dependencies to requirements.txt from project root
mkdir -p build/lambda
uv export --format requirements-txt --no-dev > build/requirements.txt

# Install dependencies from project root using absolute target path
uv pip install -r build/requirements.txt --target build/lambda
uv pip install dist/*.whl --target build/lambda --no-deps

cd build/lambda

# Add source code
cp -r ../../src ./

# Create zip file
zip -r ../../lambda-deployment-package.zip . -x "*.pyc" "*/__pycache__/*" "*.egg-info/*"
cd ../../

rm -rf build/

echo "✅ Deployment package created: lambda-deployment-package.zip"

# Initialize and apply Terraform
echo "🏗️  Initializing Terraform..."
cd terraform
terraform init

echo "🚀 Applying Terraform changes..."
terraform apply

# Get outputs
echo ""
echo "✅ Deployment completed!"
echo ""
echo "📝 Deployment Information:"
terraform output

echo ""
echo "⚡ Next Steps:"
echo "1. Verify your email address in AWS SES console"
echo "2. Test the Lambda function manually"
echo "3. Check CloudWatch logs for any issues"
echo "4. The function will run daily at 9 AM UTC"