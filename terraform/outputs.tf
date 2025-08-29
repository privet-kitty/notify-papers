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
  value       = "aws lambda invoke --function-name ${aws_lambda_function.paper_agent.arn} --region ${var.aws_region} /dev/stdout"
}
