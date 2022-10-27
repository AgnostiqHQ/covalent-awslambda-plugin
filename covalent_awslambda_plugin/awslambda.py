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
import json
import os
from contextlib import contextmanager
from typing import Callable, Dict, List, Tuple

import boto3
import botocore.exceptions
import cloudpickle as pickle
from boto3.session import Session
from covalent._shared_files import logger
from covalent._shared_files.config import get_config
from covalent_aws_plugins import AWSExecutor

app_log = logger.app_log
log_stack_info = logger.log_stack_info

executor_plugin_name = "AWSLambdaExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "function_name": "covalent-awslambda-executor",
    "credentials_file": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ.get("HOME"), ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "region": os.environ.get("AWS_REGION") or "us-east-1",
    "s3_bucket_name": "covalent-lambda-job-resources",
    "execution_role": "CovalentLambdaExecutionRole",
    "poll_freq": 5,
    "timeout": 900,
}

FUNC_FILENAME = "func-{dispatch_id}-{node_id}.pkl"
RESULT_FILENAME = "result-{dispatch_id}-{node_id}.pkl"
EXCEPTION_FILENAME = "exception-{dispatch_id}-{node_id}.json"


class AWSLambdaExecutor(AWSExecutor):
    """AWS Lambda executor plugin

    Args:
        function_name: Name of an existing lambda function to use during execution (default: `covalent-awsambda-executor`)
        s3_bucket_name: Name of a AWS S3 bucket that the executor can use to store temporary files (default: `covalent-lambda-job-resources`)
        execution_role: Name of the IAM role assigned to the AWS Lambda function
        credentials_file: Path to AWS credentials file (default: `~/.aws/credentials`)
        profile: AWS profile (default: `default`)
        region: AWS region (default: `us-east-1`)
        poll_freq: Time interval between successive polls to the lambda function (default: `5`)
        timeout: Duration in seconds to poll Lambda function for results (default: `900`)
    """

    def __init__(
        self,
        function_name: str = None,
        s3_bucket_name: str = None,
        credentials_file: str = None,
        profile: str = None,
        region: str = None,
        execution_role: str = "",
        poll_freq: int = None,
        timeout: int = 900,
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
        self.function_name = (
            function_name
            or get_config("executors.awslambda.function_name")
            or "covalent-awslambda-executor"
        )
        self.poll_freq = poll_freq or get_config("executors.awslambda.poll_freq")
        self.timeout = timeout or get_config("executors.awslambda.timeout")

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
        """Method to upload task."""
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self._upload_task_sync, workdir, func_filename)
        await fut

    def submit_task_sync(
        self, function_name: str, func_filename: str, result_filename: str, exception_filename: str
    ) -> Dict:
        """The actual (blocking) submit_task function"""
        app_log.debug(f"Invoking AWS Lambda function {function_name}")

        with self.get_session() as session:
            client = session.client("lambda")
            try:
                return client.invoke(
                    FunctionName=function_name,
                    Payload=json.dumps(
                        {
                            "S3_BUCKET_NAME": self.s3_bucket_name,
                            "COVALENT_TASK_FUNC_FILENAME": func_filename,
                            "RESULT_FILENAME": result_filename,
                            "EXCEPTION_FILENAME": exception_filename,
                        }
                    ),
                    InvocationType="Event",
                )
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise

    async def submit_task(
        self, function_name: str, func_filename: str, result_filename: str, exception_filename: str
    ) -> Dict:
        """
        Submit the task by invoking the AWS Lambda function

        Args:
            function_name: AWS Lambda function name

        Returns:
            response: AWS boto3 client invoke lambda response
        """
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(
            None,
            self.submit_task_sync,
            function_name,
            func_filename,
            result_filename,
            exception_filename,
        )
        return await fut

    def get_status_sync(self, object_key: str) -> bool:
        with self.get_session() as session:
            s3_client = session.client("s3")
            try:
                s3_client.head_object(Bucket=self.s3_bucket_name, Key=object_key)
            except botocore.exceptions.ClientError:
                return False
            return True

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

    async def _poll_task(self, object_keys: List[str]) -> str:
        """
        Poll task until its result is ready

        Args:
            object_key: Name of the object to check if present in S3
        """
        time_left = self.timeout

        while time_left > 0:
            for object_key in object_keys:
                app_log.debug(f"Polling object: {object_key}")
                status = await self.get_status(object_key)
                if status:
                    return object_key
                await asyncio.sleep(self.poll_freq)
            time_left -= self.poll_freq

        raise TimeoutError(f"{object_keys} not found in {self.s3_bucket_name}")

    def query_task_exception_sync(self, workdir: str, exception_filename: str):
        """
        Fetch the exception raised from the S3 bucket

        Args:
            workdir: Path on the local file system where the exception json dump is downloaded

        Returns:
            None
        """
        with self.get_session() as session:
            s3_client = session.client("s3")
            # Download file
            try:
                s3_client.download_file(
                    self.s3_bucket_name,
                    exception_filename,
                    os.path.join(workdir, exception_filename),
                )
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                raise

        with open(os.path.join(workdir, exception_filename), "r") as f:
            task_exception = json.load(f)

        return task_exception

    async def query_task_exception(self, workdir: str, exception_filename: str):
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(
            None, self.query_task_exception_sync, workdir, exception_filename
        )
        return await fut

    def query_result_sync(self, workdir: str, result_filename: str):
        """
        Fetch the result object from the S3 bucket

        Args:
            workdir: Path on the local file system where the pickled object is downloaded

        Returns:
            None
        """
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

    async def query_result(self, workdir: str, result_filename: str):
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self.query_result_sync, workdir, result_filename)
        return await fut

    def _pickle_func_sync(
        self, function: Callable, workdir: str, func_filename: str, args: List, kwargs: Dict
    ):
        """Method to pickle function synchronously."""
        app_log.debug("Pickling function, args and kwargs..")
        with open(os.path.join(workdir, func_filename), "wb") as f:
            pickle.dump((function, args, kwargs), f)

    async def _pickle_func(
        self, function: Callable, workdir: str, func_filename: str, args: List, kwargs: Dict
    ):
        """Pickle function asynchronously."""
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(
            None, self._pickle_func_sync, function, workdir, func_filename, args, kwargs
        )
        return await fut

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
        workdir = self.cache_dir

        func_filename = FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        result_filename = RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        exception_filename = EXCEPTION_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        app_log.debug(f"In run for task - {dispatch_id} - {node_id} ... ")

        # Pickle function asynchronously
        await self._pickle_func(function, workdir, func_filename, args, kwargs)

        # Upload pickled file to s3 bucket created
        await self._upload_task(workdir, func_filename)

        # Invoke the created lambda
        lambda_invocation_response = await self.submit_task(
            self.function_name, func_filename, result_filename, exception_filename
        )
        app_log.debug(f"Lambda function response: {lambda_invocation_response}")
        if "FunctionError" in lambda_invocation_response:
            error = lambda_invocation_response["Payload"].read().decode("utf-8")
            raise RuntimeError(
                f"Exception occurred while running task {dispatch_id}:{node_id}: {error}"
            )

        # Poll task
        object_key = await self._poll_task([result_filename, exception_filename])

        if object_key == exception_filename:
            # Download the raised exception
            app_log.debug(
                f"Retrieving exception raised during task execution - {dispatch_id} - {node_id}"
            )
            exception = await self.query_task_exception(workdir, exception_filename)
            app_log.debug(f"Exception retrived for task - {dispatch_id} - {node_id}")
            raise RuntimeError(exception)

        if object_key == result_filename:
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
