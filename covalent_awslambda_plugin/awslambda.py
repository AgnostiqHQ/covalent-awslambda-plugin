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

import asyncio
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from typing import Callable, Dict, List, Tuple
from zipfile import ZipFile

import boto3
import botocore.exceptions
import cloudpickle as pickle
from boto3.session import Session
from covalent._shared_files import logger
from covalent._shared_files.config import get_config
from covalent_aws_plugins import AWSExecutor

from .scripts import PYTHON_EXEC_SCRIPT

app_log = logger.app_log
log_stack_info = logger.log_stack_info

executor_plugin_name = "AWSLambdaExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials_file": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ.get("HOME"), ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "region": os.environ.get("AWS_REGION") or "us-east-1",
    "s3_bucket_name": "covalent-lambda-job-resources",
    "execution_role": "CovalentLambdaExecutionRole",
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

    async def install(self, pkg_name: str):
        """Install the necessary Python packages into the specified target directory

        Args:
            pkg_name: Name of the Python package to be installed

        Returns:
            None
        """
        cmd = " ".join(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                self.target_dir,
                "--upgrade",
                pkg_name,
            ]
        )
        proc, stdout, stderr = await AWSLambdaExecutor.run_async_subprocess(cmd)
        if proc.returncode != 0:
            app_log.error(stderr)
            raise RuntimeError(f"Unable to install package {pkg_name}")

    def write_deployment_archive(self):
        # Create zip archive with dependencies
        with ZipFile(self.deployment_archive, mode="w") as archive:
            for file_path in pathlib.Path(self.target_dir).rglob("*"):
                archive.write(
                    file_path, arcname=file_path.relative_to(pathlib.Path(self.target_dir))
                )

    async def __aenter__(self):
        """Create the zip archive"""
        if os.path.exists(self.target_dir):
            shutil.rmtree(self.target_dir)
            os.mkdir(self.target_dir)

        # Install the required python dependencies
        await self.install("boto3")
        await self.install("covalent==0.177.0.post1.dev0")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.write_deployment_archive)

        return self.deployment_archive

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """None"""
        pass


class AWSLambdaExecutor(AWSExecutor):
    """AWS Lambda executor plugin

    Args:
        credentials_file: Path to AWS credentials file (default: `~/.aws/credentials`)
        profile: AWS profile (default: `default`)
        region: AWS region (default: `us-east-1`)
        s3_bucket_name: Name of a AWS S3 bucket that the executor can use to store temporary files (default: `covalent-lambda-job-resources`)
        execution_role: AWS IAM role name use to provision the Lambda function (default: `CovalentLambdaExecutionRole`)
        poll_freq: Time interval between successive polls to the lambda function (default: `5`)
        timeout: Duration in seconds before the Lambda function times out (default: `60`)
        cleanup: Flag represents whether or not to cleanup temporary files generated during execution (default: `True`)
    """

    def __init__(
        self,
        s3_bucket_name: str,
        execution_role: str,
        credentials_file: str = None,
        profile: str = None,
        region: str = None,
        poll_freq: int = None,
        timeout: int = None,
        memory_size: int = None,
        cleanup: bool = False,
    ) -> None:

        # AWSExecutor parameters
        required_attrs = {
            "credentials_file": credentials_file
            or get_config("executors.awslambda.credentials_file"),
            "profile": profile or get_config("executors.awslambda.profile"),
            "region": region or get_config("executors.awslambda.region"),
            "s3_bucket_name": s3_bucket_name or get_config("executors.awslambda.s3_bucket_name"),
            "execution_role": execution_role or get_config("executors.awslambda.execution_role"),
        }

        super().__init__(**required_attrs)

        # Lambda executor parameters
        self.poll_freq = poll_freq or get_config("executors.awslambda.poll_freq")
        self.timeout = timeout or get_config("executors.awslambda.timeout")
        self.memory_size = memory_size or get_config("executors.awslambda.memory_size")
        self.cleanup = cleanup

        self._cwd = tempfile.mkdtemp()
        self._key_exists = False

    @contextmanager
    def get_session(self) -> Session:
        """Yield a boto3 session to be used for instantiating AWS service clients/resources

        Args:
            None

        Returns:
            session: AWS boto3.Session object
        """
        yield boto3.Session(**self.boto_session_options())

    def _upload_task_sync(self, workdir: str, func_filename: str):
        """
        Upload the function file to remote

        Args:
            workdir: Work dir on remote to upload file to
            func_filename: Name of the function file

        Returns:
            None
        """

        app_log.debug(f"Uploading function to S3 bucket {self.s3_bucket_name}")
        with self.get_session() as session:
            client = session.client("s3")
            try:
                with open(os.path.join(workdir, func_filename), "rb") as f:
                    client.upload_fileobj(f, self.s3_bucket_name, func_filename)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise
        app_log.debug(f"Function {func_filename} uploaded to S3 bucket {self.s3_bucket_name}")

    async def _upload_task(self, workdir: str, func_filename: str):
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self._upload_task_sync, workdir, func_filename)
        await fut

    async def _is_lambda_active(self, function_name: str) -> bool:
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
                    await asyncio.sleep(0.5)
                    continue
        return is_active

    async def _create_lambda(self, function_name: str, deployment_archive_name: str) -> Dict:
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
                response = iam_client.get_role(RoleName=f"{self.execution_role}")
                role_arn = response["Role"]["Arn"]
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise

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
                raise

        # Check if lambda is active
        is_active = await self._is_lambda_active(function_name)
        return "Active" if is_active else None

    def submit_task_sync(self, function_name: str) -> Dict:
        """The actual (blocking) submit_task function"""

        app_log.debug(f"Invoking AWS Lambda function {function_name}")

        with self.get_session() as session:
            client = session.client("lambda")
            try:
                return client.invoke(FunctionName=function_name)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise

    async def submit_task(self, function_name: str) -> Dict:
        """
        Submit the task by invoking the AWS Lambda function

        Args:
            function_name: AWS Lambda function name

        Returns:
            response: AWS boto3 client invoke lambda response
        """
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self.submit_task_sync, function_name)
        return await fut

    def get_status_sync(self, object_key: str):
        with self.get_session() as session:
            while not self._key_exists:
                s3_client = session.client("s3")
                try:
                    current_keys = [
                        item["Key"]
                        for item in s3_client.list_objects(Bucket=self.s3_bucket_name)["Contents"]
                    ]
                    self._key_exists = object_key in current_keys

                    if not self._key_exists:
                        time.sleep(0.5)

                    return self._key_exists
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    raise

    async def get_status(self, object_key: str):
        """
        Return status of availability of result object on remote machine

        Args:
            object_key: Name of the S3 object

        Returns:
            bool indicating whether the object exists or not on S3 bucket
        """

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self.get_status_sync, object_key)
        return await fut

    async def _poll_task(self, object_key: str):
        """
        Poll task until its result is ready

        Args:
            object_key: Name of the object to check if present in S3
        """

        while not await self.get_status(object_key):
            app_log.debug(f"Polling object: {object_key}")
            await asyncio.sleep(self.poll_freq)

    def query_result_sync(self, workdir: str, result_filename: str):
        """
        Fetch the result object from the S3 bucket

        Args:
            workdir: Path on the local file system where the pickled object is downloaded

        Returns:
            None
        """

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
                    raise

        with open(os.path.join(workdir, result_filename), "rb") as f:
            result_object = pickle.load(f)

        return result_object

    def _upload_deployment_archive_sync(self, deployment_archive, deployment_archive_name):
        with self.get_session() as session:
            client = session.client("s3")
            try:
                client.upload_file(
                    deployment_archive, self.s3_bucket_name, deployment_archive_name
                )
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise

    async def query_result(self, workdir: str, result_filename: str):
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self.query_result_sync, workdir, result_filename)
        return await fut

    async def setup(self, task_metadata: Dict):
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
        async with DeploymentPackageBuilder(
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
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._upload_deployment_archive_sync,
            deployment_archive,
            deployment_archive_name,
        )

        app_log.debug(f"Lambda deployment archive: {deployment_archive_name} uploaded to S3 ... ")

        # Create the lambda function
        app_log.debug(f"Creating AWS Lambda function {lambda_function_name} ...")
        state = await self._create_lambda(lambda_function_name, deployment_archive_name)
        app_log.debug(f"Lambda function: {lambda_function_name} created in state: {state}")

        app_log.debug(f"Finished setup for task - {dispatch_id}-{node_id} ... ")

    async def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):
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

        # Upload pickled file to s3 bucket created
        await self._upload_task(workdir, func_filename)

        # Invoke the created lambda
        lambda_invocation_response = await self.submit_task(lambda_function_name)
        app_log.debug(f"Lambda function response: {lambda_invocation_response}")
        if "FunctionError" in lambda_invocation_response:
            error = lambda_invocation_response["Payload"].read().decode("utf-8")
            raise RuntimeError(
                f"Exception occurred while running task {dispatch_id}:{node_id}: {error}"
            )

        # Poll task
        await self._poll_task(result_filename)

        # Download the result object
        app_log.debug(f"Retrieving result for task - {dispatch_id} - {node_id}")
        result_object = await self.query_result(workdir, result_filename)
        app_log.debug(f"Result retrived for task - {dispatch_id} - {node_id}")

        return result_object

    def cancel(self) -> None:
        """
        Cancel execution
        """
        raise NotImplementedError("Cancellation is currently not supported")

    async def teardown(self, task_metadata: Dict):
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
                    raise

                app_log.debug("Cleanup of resources in S3 bucket finished")

                app_log.debug(f"Deleting lambda function {lambda_function_name}")
                lambda_client = session.client("lambda")

                try:
                    response = lambda_client.delete_function(FunctionName=lambda_function_name)
                    app_log.debug(f"Lambda cleanup response: {response}")
                except botocore.exceptions.ClientError as ce:
                    app_log.exception(ce)
                    raise

                app_log.debug(f"Lambda function {lambda_function_name} deleted")

                app_log.debug(f"Cleaning up working directory {workdir}")
                if os.path.exists(workdir):
                    shutil.rmtree(workdir)
                app_log.debug(f"Working directory {workdir} deleted")

        app_log.debug(f"Finished teardown for task - {dispatch_id} - {node_id}")

    # copied from RemoteExecutor
    @staticmethod
    async def run_async_subprocess(cmd) -> Tuple:
        """
        Invokes an async subprocess to run a command.
        """

        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if stdout:
            app_log.debug(stdout)

        if stderr:
            app_log.debug(stderr)

        return proc, stdout, stderr
