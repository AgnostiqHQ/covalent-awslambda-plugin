import enum
import json
import os
import random
import subprocess

import covalent as ct
from covalent._shared_files import logger

# from covalent_awslambda_plugin import AWSLambdaExecutor

app_log = logger.app_log
log_stack_info = logger.log_stack_info

# Width and depth
N = 3

# random.seed(5)
# terraform_dir = os.getenv("TF_DIR")

# proc = subprocess.run(
#     [
#         "terraform",
#         f"-chdir={terraform_dir}",
#         "output",
#         "-json",
#     ],
#     check=True,
#     capture_output=True,
# )

# s3_bucket_name = json.loads(proc.stdout.decode())["s3_bucket_name"]["value"]
# iam_role_name = json.loads(proc.stdout.decode())["iam_role_name"]["value"]

# executor = AWSLambdaExecutor(
#     credentials=os.getenv("AWS_SHARED_CREDENTIALS_FILE"),
#     profile=os.getenv("AWS_PROFILE"),
#     region=os.getenv("AWS_REGION"),
#     lambda_role_name=iam_role_name,
#     s3_bucket_name=s3_bucket_name,
#     poll_freq=5,
#     timeout=60,
#     memory_size=512,
#     cleanup=True,
# )


@ct.electron
def separate(x):
    return random.randrange(1, x)


@ct.electron
def combine(x):
    print(x)
    return sum(x)


@ct.lattice
def workflow(n):
    vals = []
    nodes = range(n)
    result = 42

    for i in nodes:
        for _ in nodes:
            if i == 0:
                vals.append(separate(1e6))
            else:
                vals.append(separate(result))
        result = combine(vals)

    return result


# dispatch_id = ct.dispatch(workflow)(N)
# app_log.debug(f"AWS Lambda functional test `hagrid_workflow.py` dispatch id: {dispatch_id}")
# print(dispatch_id)

# assert ct.get_result(dispatch_id, wait=True).result == 3127

print(workflow(N))
