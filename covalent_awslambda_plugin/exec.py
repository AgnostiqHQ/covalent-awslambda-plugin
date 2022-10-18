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

"""Handler for AWS Lambda executor."""

import json
import os

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
