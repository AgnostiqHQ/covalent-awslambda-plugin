# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

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
execution_role = (
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
    "execution_role": execution_role,
    "profile": profile,
    "region": region,
    "poll_freq": poll_freq,
    "timeout": timeout,
    "memory_size": memory_size,
    "cleanup": True,
}

print("Executor config:")
print(executor_config)

executor = AWSLambdaExecutor(**executor_config)
