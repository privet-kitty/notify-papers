output "s3_papers_bucket" {
  description = "S3 bucket name for duplicate detection"
  value       = aws_s3_bucket.papers_bucket.bucket
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.paper_agent.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.paper_agent.arn
}

output "lambda_execution_command" {
  description = "Command to invoke the Lambda function"
  value       = <<EOF
aws lambda invoke \
  --cli-binary-format raw-in-base64-out \
  --function-name ${aws_lambda_function.paper_agent.arn} \
  --region ${var.aws_region} \
  --payload '{"inclusive_end_date":null}' \
  /dev/stdout
EOF
}
