# notify-papers

This is an AWS-based system that automatically collects, evaluates, and notifies about the latest research papers related to specific research topics. Currently it only supports ArXiv as the paper source.

**Notification Methods:**

- Email notifications via Amazon SES
- Microsoft Teams notifications via Webhook

## Architecture

```mermaid
graph LR
    CW[CloudWatch Events] --> LF[Lambda]
    LF --> AX[ArXiv API<br/>Paper Search]
    LF --> S3[S3 Bucket<br/>Duplicate Detection]
    LF --> BR[Bedrock<br/>Claude Model<br/>Relevance Evaluation]
    LF --> TR[Amazon Translate<br/>Summary Translation]
    LF --> SES[Amazon SES<br/>Email Notification]
    LF --> TEAMS[Microsoft Teams<br/>Webhook Notification]
    SES --> USER[User Email]
    TEAMS --> CHANNEL[Teams Channel]
```

## Deployment

### Prerequisites

Before deploying this system, ensure you have the following tools installed:

- [uv](https://docs.astral.sh/uv/)
- [Terraform](https://www.terraform.io/)
- [AWS CLI](https://aws.amazon.com/cli/)

Also, ensure you have the following prerequisites:

- Enable Claude models in Amazon Bedrock before deployment. Please go to your [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/) and enable access to Claude models. The default model used is `anthropic.claude-3-haiku-20240307-v1:0`.
- If you use Teams notifications, set up an [Incoming Webhook](https://support.microsoft.com/en-us/office/create-incoming-webhooks-with-workflows-for-microsoft-teams-8ae491c7-0394-4861-ba59-055e33f75498) in your Teams channel and add the URL to `TEAMS_WEBHOOK_URL` in `terraform.tfvars`.
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

If using Email notifications, verify your email address by checking your inbox for a verification email from AWS SES.

## Local Development

### Prerequisites

Before trying this system, ensure you have the following tools installed:

- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/)

Also, ensure you have the following prerequisites:

- Enable Claude models in Amazon Bedrock before deployment. Please go to your [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/) and enable access to Claude models. The default model used is `anthropic.claude-3-haiku-20240307-v1:0`.

### Run API Locally

1. Set up virtual environment:
   ```bash
   uv sync --frozen
   ```
2. Start mock services:
   ```bash
   docker compose up -d
   ```
3. Set up environment variables (copy and modify as needed):
   ```bash
   cp .env.example .env
   # Edit .env file with your settings, then run:
   set -a && source .env && set +a
   ```
4. Run the function locally:
   ```bash
   uv run python -m src.report_papers.main --end-date 2025-08-01
   ```
5. Check notifications:
   - **Email** (SES Mock Web UI):
     ```bash
     open http://localhost:8005
     ```
