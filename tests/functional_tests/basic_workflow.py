from covalent_awslambda_plugin import AWSLambdaExecutor
import covalent as ct

executor = AWSLambdaExecutor(
    credentials="~/.aws/credentials",
    profile="default",
    region="us-east-1",
    lambda_role_name="CovalentLambdaExecutionRole",
    s3_bucket_name="covalent-lambda-job-resources",
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
