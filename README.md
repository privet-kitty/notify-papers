# Report Papers AI Agent

This is an AWS-based system that automatically collects, evaluates, and notifies about the latest research papers related to specific research topics.

## Architecture

```
CloudWatch Events → Lambda Function → ArXiv API
                         ↓
                    Claude (Bedrock) → Email (SES)
                         ↓
                    S3 (State Management)
```
