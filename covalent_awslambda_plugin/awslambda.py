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

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from typing import Callable, Dict, List
from zipfile import ZipFile

import boto3
import botocore.exceptions
import cloudpickle as pickle
from boto3.session import Session
from covalent._shared_files import logger
from covalent._shared_files.config import get_config
from covalent.executor import BaseExecutor

from .scripts import PYTHON_EXEC_SCRIPT

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
    "cleanup": False,
}

LAMBDA_FUNCTION_NAME = "lambda-{dispatch_id}-{node_id}"
FUNC_FILENAME = "func-{dispatch_id}-{node_id}.pkl"
RESULT_FILENAME = "result-{dispatch_id}-{node_id}.pkl"
LAMBDA_DEPLOYMENT_ARCHIVE_NAME = "archive-{dispatch_id}-{node_id}.zip"
LAMBDA_FUNCTION_SCRIPT_NAME = "lambda_function.py"


class DeploymentPackageBuilder:
    """AWS Lambda deployment package (zip archive) builder

    Args:
        directory: Path to local filesystem on where to store the archive
        archive_name: Name of the deployment archive
        s3_bucket_name: Name of the AWS S3 bucket to be used to cache the deployment package
    """

    def __init__(self, directory: str, archive_name: str, s3_bucket_name: str):
        self.directory = directory
        self.archive_name = archive_name
        self.s3_bucket_name = s3_bucket_name
        self.target_dir = os.path.join(self.directory, "targets")
        self.deployment_archive = os.path.join(self.directory, self.archive_name)

    def install(self, pkg_name: str, pre: bool = False):
        """Install the necessary Python packages into the specified target directory

        Args:
            pkg_name: Name of the Python package to be installed
            pre: Boolean flag representing whether to install a pre-release version of the package

        Returns:
            None
        """
        if pre:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    self.target_dir,
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
                self.target_dir,
                "--upgrade",
                pkg_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

    def __enter__(self):
        """Create the zip archive"""
        if os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)
            os.mkdir(self.target_dir)

        # Install the required python dependencies
        self.install("boto3")
        self.install("covalent", pre=True)

        # Create zip archive with dependencies
        with ZipFile(self.deployment_archive, mode="w") as archive:
            for file_path in pathlib.Path(self.target_dir).rglob("*"):
                archive.write(
                    file_path, arcname=file_path.relative_to(pathlib.Path(self.target_dir))
                )

        return self.deployment_archive

    def __exit__(self, exc_type, exc_value, exc_tb):
        """None"""
        pass


class AWSLambdaExecutor(BaseExecutor):
    """AWS Lambda executor plugin

    Args:
        credentials: Path to AWS credentials file (default: `~/.aws/credentials`)
        profile: AWS profile (default: `default`)
        region: AWS region (default: `us-east-1`)
        lambda_role_name: AWS IAM role name use to provision the Lambda function (default: `CovalentLambdaExecutionRole`)
        s3_bucket_name: Name of a AWS S3 bucket that the executor can use to store temporary files (default: `covalent-lambda-job-resources`)
        cache_dir: Path on the local file system to a cache directory (default: `~/.cache/covalent`)
        poll_freq: Time interval between successive polls to the lambda function (default: `5`)
        timeout: Duration in seconds before the Lambda function times out (default: `60`)
        cleanup: Flag represents whether or not to cleanup temporary files generated during execution (default: `True`)
    """

    def __init__(
        self,
        credentials: str = None,
        profile: str = None,
        region: str = None,
        lambda_role_name: str = None,
        s3_bucket_name: str = None,
        cache_dir: str = None,
        poll_freq: int = None,
        timeout: int = None,
        memory_size: int = None,
        cleanup: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(cache_dir=cache_dir, **kwargs)

        self.credentials = credentials or get_config("executors.awslambda.credentials")
        self.profile = profile or get_config("executors.awslambda.profile")
        self.region = region or get_config("executors.awslambda.region")
        self.s3_bucket_name = s3_bucket_name or get_config("executors.awslambda.s3_bucket_name")
        self.role_name = lambda_role_name or get_config("executors.awslambda.lambda_role_name")
        self.cache_dir = cache_dir or os.path.join(os.environ["HOME"], ".cache/covalent")
        self.poll_freq = poll_freq or get_config("executors.awslambda.poll_freq")
        self.timeout = timeout or get_config("executors.awslambda.timeout")
        self.memory_size = memory_size or get_config("executors.awslambda.memory_size")
        self.cleanup = cleanup
        self._cwd = tempfile.mkdtemp()
        self._key_exists = False

        # Set cloud environment variables
        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = f"{self.credentials}"
        os.environ["AWS_PROFILE"] = f"{self.profile}"
        os.environ["AWS_REGION"] = f"{self.region}"

    @contextmanager
    def get_session(self) -> Session:
        """Yield a boto3 session to be used for instantiating AWS service clients/resources

        Args:
            None

        Returns:
            session: AWS boto3.Session object
        """
        yield boto3.Session(profile_name=self.profile, region_name=self.region)

    def _is_lambda_active(self, function_name: str):
        """Check if the lambda function is active of not

        Args:
            function_name: Name of the lambda function

        Returns:
            bool: Boolean value either True/False
        """
        # Check if lambda is active
        is_active = False
        with self.get_session() as session:
            lambda_client = session.client("lambda")
            while not is_active:
                lambda_state = lambda_client.get_function(FunctionName=function_name)
                app_log.debug(
                    f"Lambda function {function_name} state: {lambda_state['Configuration']['State']}"
                )
                if lambda_state["Configuration"]["State"] == "Active":
                    is_active = True
                else:
                    time.sleep(0.1)
                    continue
        return is_active

    def _create_lambda(self, function_name: str, deployment_archive_name: str) -> Dict:
        """Create the AWS Lambda function

        Args:
            function_name: AWS Lambda function name
            deployment_archive_name: Lambda deployment zip archive name

        Returns:
            response: AWS boto3 client create_lambda response
        """
        with self.get_session() as session:
            iam_client = session.client("iam")
            role_arn = None
            try:
                response = iam_client.get_role(RoleName=f"{self.role_name}")
                role_arn = response["Role"]["Arn"]
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        lambda_create_kwargs = {
            "FunctionName": f"{function_name}",
            "Runtime": "python3.8",
            "Role": f"{role_arn}",
            "Handler": "lambda_function.lambda_handler",
            "Code": {"S3Bucket": f"{self.s3_bucket_name}", "S3Key": deployment_archive_name},
            "PackageType": "Zip",
            "Publish": True,
            "Timeout": self.timeout,
            "MemorySize": self.memory_size,
        }

        with self.get_session() as session:
            lambda_client = session.client("lambda")
            try:
                response = lambda_client.create_function(**lambda_create_kwargs)
                app_log.debug(f"Lambda function: {function_name} created: {response}")
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        # Check if lambda is active
        lambda_state = "Active" if self._is_lambda_active(function_name) else None
        return lambda_state

    def _invoke_lambda(self, function_name: str) -> Dict:
        """Invoke the AWS Lambda function

        Args:
            function_name: AWS Lambda function name

        Returns:
            response: AWS boto3 client invoke lambda response
        """
        with self.get_session() as session:
            client = session.client("lambda")
            try:
                response = client.invoke(FunctionName=function_name)
                return response
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

    def _is_key_in_bucket(self, object_key):
        """Return True if the object is present in the S3 bucket

        Args:
            object_key: Name of the object to check if present in S3

        Returns:
            bool: True/False
        """
        with self.get_session() as session:
            s3_client = session.client("s3")
            try:
                current_keys = [
                    item["Key"]
                    for item in s3_client.list_objects(Bucket=self.s3_bucket_name)["Contents"]
                ]
                if object_key in current_keys:
                    return True
                else:
                    return False
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

    def _get_result_object(self, workdir: str, result_filename: str):
        """Fetch the result object from the S3 bucket

        Args:
            workdir: Path on the local file system where the pickled object is downloaded

        Returns:
            None
        """
        with self.get_session() as session:
            while not self._key_exists:
                self._key_exists = self._is_key_in_bucket(result_filename)
                time.sleep(0.1)

        if self._key_exists:
            with self.get_session() as session:
                s3_client = session.client("s3")
                # Download file
                try:
                    s3_client.download_file(
                        self.s3_bucket_name,
                        result_filename,
                        os.path.join(workdir, result_filename),
                    )
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    exit(1)

        with open(os.path.join(workdir, result_filename), "rb") as f:
            result_object = pickle.load(f)

        return result_object

    def setup(self, task_metadata: Dict):
        """AWS Lambda specific setup tasks

        Args:
            task_metadata: Dictionary containing the task dispatch_id and node_id

        Returns:
            None
        """
        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        workdir = os.path.join(self._cwd, dispatch_id)
        deployment_archive_name = LAMBDA_DEPLOYMENT_ARCHIVE_NAME.format(
            dispatch_id=dispatch_id, node_id=node_id
        )
        lambda_function_name = LAMBDA_FUNCTION_NAME.format(
            dispatch_id=dispatch_id, node_id=node_id
        )

        app_log.debug(f"Starting setup for task - {dispatch_id}-{node_id} ... ")

        if not os.path.exists(workdir):
            os.mkdir(workdir)

        app_log.debug(
            f"Creating the Lambda deployment archive at {os.path.join(workdir, deployment_archive_name)} ..."
        )
        with DeploymentPackageBuilder(
            workdir, deployment_archive_name, self.s3_bucket_name
        ) as deployment_archive:
            exec_script = PYTHON_EXEC_SCRIPT.format(
                func_filename=FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id),
                result_filename=RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id),
                s3_bucket_name=self.s3_bucket_name,
            )
            with open(os.path.join(workdir, LAMBDA_FUNCTION_SCRIPT_NAME), "w") as f:
                f.write(exec_script)
            # Add script to the deployment archive
            with ZipFile(deployment_archive, mode="a") as archive:
                archive.write(
                    os.path.join(workdir, LAMBDA_FUNCTION_SCRIPT_NAME),
                    arcname=LAMBDA_FUNCTION_SCRIPT_NAME,
                )

        app_log.debug(
            f"Lambda deployment archive: {os.path.join(workdir, deployment_archive_name)} created. Uploading to S3 ..."
        )

        # Upload archive to s3 bucket
        with self.get_session() as session:
            client = session.client("s3")
            try:
                client.upload_file(
                    deployment_archive, self.s3_bucket_name, deployment_archive_name
                )
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

        app_log.debug(f"Lambda deployment archive: {deployment_archive_name} uploaded to S3 ... ")

        # Create the lambda function
        app_log.debug(f"Creating AWS Lambda function {lambda_function_name} ...")
        state = self._create_lambda(lambda_function_name, deployment_archive_name)
        app_log.debug(f"Lambda function: {lambda_function_name} created in state: {state}")

        app_log.debug(f"Finished setup for task - {dispatch_id}-{node_id} ... ")

    def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):
        """Run the executor

        Args:
            function: Python callable to be executed on the remote executor
            args: List of positional arguments to be passed to the function
            kwargs: Keyword arguments to be passed into the function
            task_metadata: Dictionary containing the task dispatch_id and node_id

        Returns:
            None
        """
        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        workdir = os.path.join(self._cwd, dispatch_id)

        func_filename = FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        result_filename = RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        lambda_function_name = LAMBDA_FUNCTION_NAME.format(
            dispatch_id=dispatch_id, node_id=node_id
        )

        app_log.debug(f"In run for task - {dispatch_id} - {node_id} ... ")

        app_log.debug("Pickling function, args and kwargs..")
        with open(os.path.join(workdir, func_filename), "wb") as f:
            pickle.dump((function, args, kwargs), f)

        app_log.debug(f"Uploading function to S3 bucket {self.s3_bucket_name}")
        # Upload pickled file to s3 bucket created
        with self.get_session() as session:
            client = session.client("s3")
            try:
                with open(os.path.join(workdir, func_filename), "rb") as f:
                    client.upload_fileobj(f, self.s3_bucket_name, func_filename)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)
        app_log.debug(f"Function {func_filename} uploaded to S3 bucket {self.s3_bucket_name}")

        # Invoke the created lambda
        app_log.debug(f"Invoking AWS Lambda function {lambda_function_name}")
        lambda_invocation_response = self._invoke_lambda(lambda_function_name)
        app_log.debug(f"Lambda function response: {lambda_invocation_response}")

        # Download the result object
        app_log.debug(f"Retrieving result for task - {dispatch_id} - {node_id}")
        result_object = self._get_result_object(workdir, result_filename)
        app_log.debug(f"Result retrived for task - {dispatch_id} - {node_id}")

        return result_object

    def teardown(self, task_metadata: Dict):
        """Cleanup temporary files and the Lambda function

        Args:
            task_metadata: Dictionary containing the task dispatch_id and node_id

        Returns:
            None
        """
        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        lambda_function_name = LAMBDA_FUNCTION_NAME.format(
            dispatch_id=dispatch_id, node_id=node_id
        )
        workdir = os.path.join(self._cwd, dispatch_id)

        app_log.debug(f"In teardown for task - {dispatch_id} - {node_id}")

        if self.cleanup:
            with self.get_session() as session:
                app_log.debug(f"Cleaning up resources created in S3 bucket {self.s3_bucket_name}")
                s3_resource = session.resource("s3")
                try:
                    s3_resource.Object(
                        self.s3_bucket_name,
                        FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id),
                    ).delete()
                    s3_resource.Object(
                        self.s3_bucket_name,
                        RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id),
                    ).delete()
                    s3_resource.Object(
                        self.s3_bucket_name,
                        LAMBDA_DEPLOYMENT_ARCHIVE_NAME.format(
                            dispatch_id=dispatch_id, node_id=node_id
                        ),
                    ).delete()
                    app_log.debug(f"All objects from bucket {self.s3_bucket_name} deleted")
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    exit(1)
                app_log.debug("Cleanup of resources in S3 bucket finished")

                app_log.debug(f"Deleting lambda function {lambda_function_name}")
                lambda_client = session.client("lambda")
                try:
                    response = lambda_client.delete_function(FunctionName=lambda_function_name)
                    app_log.debug(f"Lambda cleanup response: {response}")
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    exit(1)
                app_log.debug(f"Lambda function {lambda_function_name} deleted")

                app_log.debug(f"Cleaning up working directory {workdir}")
                if os.path.exists(workdir):
                    shutil.rmtree(workdir)
                app_log.debug(f"Working directory {workdir} deleted")

        app_log.debug(f"Finished teardown for task - {dispatch_id} - {node_id}")
