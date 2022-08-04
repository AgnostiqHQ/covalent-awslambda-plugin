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

"""This is an example of a custom Covalent executor plugin."""

import os
import pathlib
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Callable, Dict, List
from zipfile import ZipFile

import boto3
import botocore.exceptions
import cloudpickle as pickle
from boto3.session import Session

# Covalent logger
from covalent._shared_files import logger

# All executor plugins inherit from the BaseExecutor base class.
from covalent.executor import BaseExecutor

app_log = logger.app_log
log_stack_info = logger.log_stack_info

executor_plugin_name = "AWSLambdaExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ.get("HOME"), ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "region": os.environ.get("AWS_REGION") or "us-east-1",
    "lambda_role_name": "CovalentLambdaExecutionRole",
    "s3_bucket_name": "covalent-lambda-job-resources",
    "cache_dir": os.path.join(os.environ["HOME"], ".cache/covalent"),
    "poll_freq": 5,
    "timeout": 60,
    "memory_size": 512,
    "cleanup": True
}


class ResourceBuilder(ABC):
    """Abstract class to define an interface for building cloud/local resources"""

    def __init__(self, session):
        self.session = session

    @abstractmethod
    def setup(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def teardown(self, *args, **kwargs):
        raise NotImplementedError


class ExecScriptBuilder(ResourceBuilder):
    """Create the executable Python script that executes the task"""

    def __init__(
        self,
        func: Callable,
        args: List,
        kwargs: Dict,
        func_filename: str,
        result_filename: str,
        script_filename: str,
        s3_bucket: str,
    ):
        self.function = func
        self.args = args
        self.kwargs = kwargs
        self.bucket_name = s3_bucket
        self.func_filename = func_filename
        self.result_filename = result_filename
        self.script_filename = script_filename
        super().__init__(session=None)

    def setup(self):
        exec_script = """
import cloudpickle as pickle
import boto3
import os

def lambda_handler(event, context):
    os.environ['HOME'] = "/tmp"
    os.chdir("/tmp")

    s3 = boto3.client("s3")

    try:
        s3.download_file("{bucket_name}", "{func_filename}", "/tmp/{func_filename}")
    except Exception as e:
        print(e)

    with open("/tmp/{func_filename}", "rb") as f:
        function, args, kwargs = pickle.load(f)

    try:
        result = function(*args, **kwargs)
    except Exception as e:
        print(e)

    with open("/tmp/{result_filename}", "wb") as f:
        pickle.dump(result, f)

    try:
        s3.upload_file("/tmp/{result_filename}", "{bucket_name}", "{result_filename}")
    except Exception as e:
        print(e)
""".format(
            bucket_name=self.bucket_name,
            func_filename=self.func_filename,
            result_filename=self.result_filename,
        )
        with open(self.script_filename, "w") as f:
            f.write(exec_script)

        return self.script_filename

    def teardown(self):
        if os.path.exists(self.script_filename):
            os.remove(self.script_filename)


class DeploymentPackageBuilder:
    def __init__(self, directory: str, archive_name: str, s3_bucket_name: str):
        self.directory = directory
        self.archive_name = archive_name
        self.s3_bucket_name = s3_bucket_name
        self.__target_dir = os.path.join(self.directory, "targets")
        self.__deployment_archive = os.path.join(self.directory, self.archive_name)

    def install(self, pkg_name: str, pre: bool = False):
        if pre:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    self.__target_dir,
                    "--upgrade",
                    pkg_name,
                    "--pre",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                self.__target_dir,
                "--upgrade",
                pkg_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

    def __enter__(self):
        if os.path.exists(self.__target_dir):
            shutil.rmtree(self.__target_dir)
            os.mkdir(self.__target_dir)

        # Install the required python dependencies
        self.install("boto3")
        self.install("cloudpickle==2.0.0")
        self.install("covalent", pre=True)

        # Create zip archive with dependencies
        with ZipFile(self.__deployment_archive, mode="w") as archive:
            for file_path in pathlib.Path(self.__target_dir).rglob("*"):
                archive.write(
                    file_path, arcname=file_path.relative_to(pathlib.Path(self.__target_dir))
                )

        return self.__deployment_archive

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass
        """Cleanup transient resources"""
        pass


class AWSLambdaExecutor(BaseExecutor):
    """AWS Lambda executor plugin

    Args:
        profile: Name of AWS profile to use (default: default), environment variable: AWS_PROFILE
        region: AWS region, AWS_REGION
    """

    def __init__(
        self,
        credentials: str,
        profile: str,
        region: str,
        lambda_role_name: str,
        s3_bucket_name: str,
        cache_dir: str,
        poll_freq: int = 5,
        timeout: int = 60,
        memory_size: int = 512,
        cleanup: bool = True,
        **kwargs,
    ) -> None:
        self.credentials = credentials
        self.profile = profile
        self.region = region

        self.s3_bucket_name = s3_bucket_name
        self.role_name = lambda_role_name
        self.cache_dir = cache_dir
        self.poll_freq = poll_freq
        self.timeout = timeout
        self.memory_size = memory_size
        self.cleanup = cleanup

        self.cwd = os.getcwd()

        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = f"{self.credentials}"
        os.environ["AWS_PROFILE"] = f"{self.profile}"
        os.environ["AWS_REGION"] = f"{self.region}"

        self.func_filename = ""
        self.result_filename = ""
        self.script_filename = ""
        self.dispatch_id = ""
        self.node_id = None
        self.function_name = ""
        self.workdir = ""

        super().__init__(cache_dir=cache_dir, **kwargs)

    @contextmanager
    def get_session(self) -> Session:
        yield boto3.Session(profile_name=self.profile, region_name=self.region)

    def _create_lambda(self) -> Dict:
        """Create the lambda function"""
        self.function_name = f"lambda-{self.dispatch_id}-{self.node_id}"

        with self.get_session() as session:
            iam_client = session.client("iam")
            try:
                response = iam_client.get_role(RoleName=f"{self.role_name}")
                role_arn = response["Role"]["Arn"]
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        lambda_create_kwargs = {
            "FunctionName": f"{self.function_name}",
            "Runtime": "python3.8",
            "Role": f"{role_arn}",
            "Handler": "lambda_function.lambda_handler",
            "Code": {
                "S3Bucket": f"{self.s3_bucket_name}",
                "S3Key": f"lambda-{self.dispatch_id}-{self.node_id}.zip",
            },
            "PackageType": "Zip",
            "Description": f"AWS lambda for task {self.dispatch_id}/{self.node_id}",
            "Tags": {"dispatch_id": f"{self.dispatch_id}", "node_id": f"{self.node_id}"},
            "Publish": True,
            "Timeout": self.timeout,
            "MemorySize": self.memory_size,
        }

        with self.get_session() as session:
            lambda_client = session.client("lambda")
            try:
                response = lambda_client.create_function(**lambda_create_kwargs)
                app_log.warning(f"Lambda function: {self.function_name} created: {response}")
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        # Check if lambda is active
        is_active = False
        while not is_active:
            lambda_state = lambda_client.get_function(FunctionName=self.function_name)
            app_log.debug(
                f"Lambda funciton {self.function_name} state: {lambda_state['Configuration']['State']}"
            )
            if lambda_state["Configuration"]["State"] == "Active":
                is_active = True
            else:
                time.sleep(0.1)
                continue

        return lambda_state

    def _invoke_lambda(self) -> Dict:
        """Invoke the Lambda function and return the response"""
        with self.get_session() as session:
            client = session.client("lambda")
            try:
                response = client.invoke(FunctionName=self.function_name)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)
        return response

    def _get_result_object(self, workdir: str):
        """Retrive the result object from the pickle file upload to S3 bucket after the lambda execution"""
        key_exists = False
        with self.get_session() as session:
            s3_client = session.client("s3")
            # There must be a timeout block for this (can be replaced via http calls with timeouts to the s3 api)
            while not key_exists:
                try:
                    current_keys = [
                        item["Key"]
                        for item in s3_client.list_objects(Bucket=self.s3_bucket_name)["Contents"]
                    ]
                    if self.result_filename in current_keys:
                        app_log.debug(
                            f"Result object: {self.result_filename} found in {self.s3_bucket_name} bucket"
                        )
                        key_exists = True
                    else:
                        time.sleep(0.1)
                        continue
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    exit(1)

            # Download file
            try:
                s3_client.download_file(
                    self.s3_bucket_name,
                    self.result_filename,
                    os.path.join(workdir, self.result_filename),
                )
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        with open(os.path.join(workdir, self.result_filename), "rb") as f:
            result_object = pickle.load(f)

        return result_object

    def _cleanup(self) -> None:
        """Delete all resources that were created for the purposes of the lambda execution
        * Remove all resources from the S3 bucket
        * Delete the lambda
        """
        app_log.debug("In cleanup")
        with self.get_session() as session:
            s3_resource = session.resource("s3")
            try:
                bucket = s3_resource.Bucket(self.s3_bucket_name)
                bucket.objects.all().delete()
                app_log.debug(f"All objects from bucket {self.s3_bucket_name} deleted")
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

            lambda_client = session.client("lambda")
            try:
                response = lambda_client.delete_function(FunctionName=self.function_name)
                app_log.debug(f"Lambda cleanup response: {response}")
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

            # Cleanup
            if os.path.exists(self.workdir):
                shutil.rmtree(self.workdir)

    def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):
        # Pickle the callable, args and kwargs
        self.dispatch_id = task_metadata["dispatch_id"]
        self.node_id = task_metadata["node_id"]
        self.workdir = os.path.join(self.cwd, self.dispatch_id)
        app_log.debug(f"Creating transient files in {self.workdir}")

        if not os.path.exists(self.workdir):
            os.mkdir(self.workdir)

        self.func_filename = f"func-{self.dispatch_id}-{self.node_id}.pkl"
        self.result_filename = f"result-{self.dispatch_id}-{self.node_id}.pkl"
        self.script_filename = "lambda_function.py"

        app_log.debug("Pickling function, args and kwargs..")
        with open(os.path.join(self.workdir, self.func_filename), "wb") as f:
            pickle.dump((function, args, kwargs), f)

        app_log.debug(f"Uploading function to be executed to S3 bucket {self.s3_bucket_name}")
        # Upload pickled file to s3 bucket created
        with self.get_session() as session:
            client = session.client("s3")
            try:
                with open(os.path.join(self.workdir, self.func_filename), "rb") as f:
                    client.upload_fileobj(f, self.s3_bucket_name, self.func_filename)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        # Create deployment package
        app_log.warning("Creating deployment archive ...")
        with DeploymentPackageBuilder(
            self.workdir, f"lambda-{self.dispatch_id}-{self.node_id}.zip", self.s3_bucket_name
        ) as deployment_archive:
            # Create the lambda handler script
            exec_bldr = ExecScriptBuilder(
                func=function,
                args=args,
                kwargs=kwargs,
                func_filename=self.func_filename,
                result_filename=self.result_filename,
                script_filename=os.path.join(self.workdir, self.script_filename),
                s3_bucket=self.s3_bucket_name,
            )
            script_file = exec_bldr.setup()

            # Add script to the deployment archive
            with ZipFile(deployment_archive, mode="a") as archive:
                archive.write(script_file, arcname=self.script_filename)

            _, archive_name = os.path.split(deployment_archive)

            app_log.warning(
                f"Lambda deployment archive: {archive_name} created. Uploading to S3 ..."
            )

            # Upload archive to s3 bucket
            with self.get_session() as session:
                client = session.client("s3")
                try:
                    client.upload_file(deployment_archive, self.s3_bucket_name, archive_name)
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    exit(1)

        # Create the lambda function
        state = self._create_lambda()
        app_log.warning(f"Created lambda function: {self.function_name}, state: {state}")

        # Invoke the created lambda
        lambda_invocation_response = self._invoke_lambda()
        app_log.warning(f"Lambda function response: {lambda_invocation_response}")

        # Download the result object
        result_object = self._get_result_object(self.workdir)

        # Cleanup
        if self.cleanup:
            self._cleanup()

        return result_object
