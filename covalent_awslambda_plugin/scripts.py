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

"""Python execution script"""

PYTHON_EXEC_SCRIPT = """
import os
import boto3
import cloudpickle as pickle

def lambda_handler(event, context):
    os.environ['HOME'] = "/tmp"
    os.chdir("/tmp")

    s3 = boto3.client("s3")

    try:
        s3.download_file("{s3_bucket_name}", "{func_filename}", "/tmp/{func_filename}")
    except Exception as e:
        print(e)
        raise e

    with open("/tmp/{func_filename}", "rb") as f:
        function, args, kwargs = pickle.load(f)

    try:
        result = function(*args, **kwargs)
    except Exception as e:
        print(e)
        raise e

    with open("/tmp/{result_filename}", "wb") as f:
        pickle.dump(result, f)

    try:
        s3.upload_file("/tmp/{result_filename}", "{s3_bucket_name}", "{result_filename}")
    except Exception as e:
        print(e)
        raise e
"""
