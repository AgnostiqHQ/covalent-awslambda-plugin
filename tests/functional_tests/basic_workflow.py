from covalent_awslambda_plugin import AWSLambdaExecutor
import covalent as ct
import os
import subprocess
import json

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

s3_bucket_name = json.loads(proc.stdout.decode())["s3_bucket_name"]["value"]

executor = AWSLambdaExecutor(
    credentials=os.getenv("AWS_SHARED_CREDENTIALS_FILE"),
    profile=os.getenv("AWS_PROFILE"),
    region=os.getenv("AWS_REGION"),
    s3_bucket_name=s3_bucket_name,
    poll_freq=5,
    timeout=60,
    memory_size=512,
    cleanup=True,
)

@ct.electron(executor=executor)
def join_words(a, b):
    return ", ".join([a, b])

@ct.electron(executor=executor)
def excitement(a):
    return f"{a}!"

@ct.lattice
def simple_workflow(a, b):
    phrase = join_words(a, b)
    return excitement(phrase)

dispatch_id = ct.dispatch(simple_workflow)("Hello", "World")
print(dispatch_id)

print(ct.get_result(dispatch_id, wait=True))
