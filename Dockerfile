# Lambda Python runtime
FROM public.ecr.aws/lambda/python:3.12

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy project files
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Install dependencies
RUN uv sync --frozen --no-dev --no-cache

# Set the CMD to your handler
CMD ["src.report_papers.main.lambda_handler"]