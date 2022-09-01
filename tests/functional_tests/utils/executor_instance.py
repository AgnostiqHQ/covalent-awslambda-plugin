import json
import os
import subprocess

from covalent_awslambda_plugin import AWSLambdaExecutor

terraform_dir = os.getenv("TF_DIR")
proc = subprocess.run(
    [
        "terraform",
        f"-chdir={terraform_dir}",
        "output",
        "-json",
    ],
    check=True,
    capture_output=True,
)

TERRAFORM_OUTPUTS = json.loads(proc.stdout.decode())

print("Terraform output:")
print(TERRAFORM_OUTPUTS)

s3_bucket_name = (
    os.getenv("LAMBDA_EXECUTOR_S3_BUCKET_NAME") or TERRAFORM_OUTPUTS["s3_bucket_name"]["value"]
)
lambda_role_name = (
    os.getenv("LAMBDA_EXECUTOR_LAMBDA_ROLE_NAME") or TERRAFORM_OUTPUTS["iam_role_name"]["value"]
)
credentials = os.getenv("AWS_SHARED_CREDENTIALS_FILE", "~/.aws/credentials")
profile = os.getenv("AWS_PROFILE", "default")
region = os.getenv("AWS_REGION", "us-east-1")
poll_freq = os.getenv("LAMBDA_EXECUTOR_POLL_FREQ", 5)
timeout = os.getenv("LAMBDA_EXECUTOR_TIMEOUT", 60)
memory_size = os.getenv("LAMBDA_EXECUTOR_MEMORY_SIZE", 512)

executor_config = {
    "s3_bucket_name": s3_bucket_name,
    "lambda_role_name": lambda_role_name,
    "profile": profile,
    "region": region,
    "poll_freq": poll_freq,
    "timeout": timeout,
    "memory_size": memory_size,
    "cleanup": True,
}

executor = AWSLambdaExecutor(**executor_config)
