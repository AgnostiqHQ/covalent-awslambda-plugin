import json
import os
from unittest import expectedFailure

import boto3
import cloudpickle as pickle


def handler(event, context):
    try:
        os.environ["HOME"] = "/tmp"
        os.chdir("/tmp")

        s3_bucket = event["S3_BUCKET_NAME"]
        func_filename = event["COVALENT_TASK_FUNC_FILENAME"]
        result_filename = event["RESULT_FILENAME"]
        exception_filename = event["EXCEPTION_FILENAME"]

        local_func_filename = os.path.join("/tmp", func_filename)
        local_result_filename = os.path.join("/tmp", result_filename)
        local_exception_filename = os.path.join("/tmp", exception_filename)

        s3 = boto3.client("s3")
        s3.download_file(s3_bucket, func_filename, local_func_filename)

        with open(local_func_filename, "rb") as f:
            function, args, kwargs = pickle.load(f)

        result = function(*args, **kwargs)
        with open(local_result_filename, "wb") as f:
            pickle.dump(result, f)

        s3.upload_file(local_result_filename, s3_bucket, result_filename)
    except Exception as ex:
        # Write json and upload to S3
        with open(local_exception_filename, "w") as f:
            json.dump(str(ex), f)

        s3.upload_file(local_exception_filename, s3_bucket, exception_filename)
