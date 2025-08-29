# notify-papers

This is an AWS-based system that automatically collects, evaluates, and notifies about the latest research papers related to specific research topics. Currently it only supports ArXiv as the paper source.

## Architecture

```mermaid
graph TD
    CW[CloudWatch Events] --> LF[Lambda]
    LF --> AX[ArXiv API<br/>Paper Search]
    LF --> S3[S3 Bucket<br/>Duplicate Detection]
    LF --> BR[Bedrock<br/>Claude Model<br/>Relevance Evaluation]
    LF --> TR[Amazon Translate<br/>Summary Translation]
    LF --> SES[Amazon SES<br/>Email Notification]
    SES --> USER[User Email]
```

## Deployment

### Prerequisites

Before deploying this system, ensure you have the following tools installed:

- [uv](https://docs.astral.sh/uv/)
- [Terraform](https://www.terraform.io/)
- [AWS CLI](https://aws.amazon.com/cli/)

Also, ensure you have the following prerequisites:

- Enable Claude models in Amazon Bedrock before deployment. Please go to your [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/) and enable access to Claude models. The default model used is `anthropic.claude-3-haiku-20240307-v1:0`.
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

After deployment, you'll need to verify your email address. Check your email inbox for a verification email from AWS SES.
