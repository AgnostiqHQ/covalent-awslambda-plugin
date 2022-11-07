from dotenv import load_dotenv

load_dotenv()

import os

from covalent_awslambda_plugin import AWSLambdaExecutor

executor_config = {
    "s3_bucket_name": os.getenv("executor_s3_bucket_name"),
    "poll_freq": os.getenv("executor_poll_freq", 5),
    "timeout": os.getenv("executor_timeout", 60),
    "cleanup": os.getenv("executor_cleanup", True),
}

print("Executor configuration:")
print(executor_config)

executor = AWSLambdaExecutor(**executor_config)
