# Paper notification agent

This is an AWS-based system that automatically collects, evaluates, and notifies about the latest research papers related to specific research topics.

## Architecture

```
CloudWatch Events → Lambda Function → ArXiv API
                         ↓
                    Claude (Bedrock) → Email (SES)
                         ↓
                    S3 (State Management)
```

## Deployment

### Prerequisites

Before deploying this system, ensure you have the following tools installed:

- [uv](https://docs.astral.sh/uv/) - Python package and project manager
- [Terraform](https://www.terraform.io/) - Infrastructure as Code tool
- AWS CLI - Configured with appropriate credentials

Before deploying this system, ensure you have the following prerequisites:

- Enable Claude models in Amazon Bedrock before deployment. Please go to the [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/) and enable access to Claude models.
- Copy the example configuration file and customize it:
  ```bash
  cp terraform/terraform.tfvars.example terraform/terraform.tfvars
  ```

### Deployment procedure

1. Build lambda package:
   ```bash
   sh scripts/build_lambda.sh
   ```
2. Deploy infrastructure to AWS:
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

### Postrequisites

After deployment, you'll need to verify your email address. Check your email inbox for a verification email from AWS SES
