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
from contextlib import contextmanager
from typing import Callable, Dict, List
from abc import ABC, abstractmethod
import cloudpickle as pickle

import boto3
import botocore.exceptions
from boto3.session import Session

# Covalent logger
from covalent._shared_files import logger

# DispatchInfo objects are used to share info of a dispatched computation between different
# tasks (electrons) of the workflow (lattice).
from covalent._shared_files.util_classes import DispatchInfo

# All executor plugins inherit from the BaseExecutor base class.
from covalent.executor import BaseExecutor
from sqlalchemy import func

app_log = logger.app_log
log_stack_info = logger.log_stack_info


executor_plugin_name = "AWSLambdaExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or os.path.join(os.environ.get("HOME"), ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "region": os.environ.get("AWS_REGION") or "us-east-1"
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

class S3BucketBuilder(ResourceBuilder):
    """Create an S3 bucket"""
    def __init__(self, bucket_name: str, session):
        self.bucket_name = bucket_name
        super().__init__(session=session)

    def setup(self):
        s3_bucket = self.session.resource('s3')
        try:
            app_log.debug(f"Creating S3 bucket: {self.bucket_name}")
            response = s3_bucket.create_bucket(Bucket=self.bucket_name)
            app_log.debug(f"S3 BUCKET RESPONSE: {response}")
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

    def teardown(self):
        s3_resource = self.session.resource('s3')
        s3_bucket = s3_resource.Bucket(self.bucket_name)
        app_log.debug(f"Deleting bucket: {s3_bucket}")
        try:
            for s3_object in s3_bucket.objects.all():
                s3_object.delete()
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

        try:
            response = s3_bucket.delete()
            app_log.warning(f"{response}")
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

class ECRBuilder(ResourceBuilder):
    """Create an AWS Elastic container registry
    """
    def __init__(self, name: str, session):
        self.name = name
        self.client = session.client("ecr")

    def setup(self):
        try:
            app_log.debug(f"Creating ECR: {self.name}")
            response = self.client.create_repository(repositoryName=self.name)
            app_log.debug(f"{response}")
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

    def teardown(self):
        try:
            app_log.debug(f"Deleting ECR: {self.name}")
            response = self.client.delete_repository(repositoryName=self.name, force=True)
            app_log.debug(f"{response}")
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

class DockerfileBuilder(ResourceBuilder):
    """Create a Dockerfile which wraps an executable Python task

    Args:
        exec_script_filename: Name of the executable Python script
        docker_working_dir: Working directory path within the container
    """
    def __init__(self, exec_script_filename: str):
        self.script = exec_script_filename
    def setup(self):
        """Create the dockerfile"""
        dockerfile=f"""
        FROM python:3.8-slim-buster

        RUN apt-get update && \\
            apt-get install -y && \\
            apt-get install -y build-essential && \\
            rm -rf /var/lib/apt/lists/* && \\
            pip install --no-cache-dir --use-feature=in-tree-build boto3 && \\
            pip install --no-cache-dir --use-feature=in-tree-build cloudpickle && \\
            pip install --no-cache-dir --use-feature=in-tree-build covalent --pre

        WORKDIR /tmp/covalent

        COPY {self.script} /tmp/covalent

        ENTRYPOINT ["python"]
        CMD [/tmp/covalent/{self.script}]
        """

        with open("Dockerfile", "w") as f:
            f.write(dockerfile)

    def teardown(self):
        """Delete the Dockerfile"""
        if os.path.exists("Dockerfile"):
            os.remove("Dockerfile")

class DockerImageBuilder(ResourceBuilder):
    """Build a Docker image given the dockerfile using AWS CodeBuild service"""
    def __init__(self, account_id: str, project_name: str, repo_name: str, dispatch_id: str, node_id: int):
        self.account_id = account_id
        self.project_name = project_name
        self.ecr_repo_name = repo_name
        self.dispatch_id = dispatch_id
        self.node_id = node_id

    def setup(self):
        with self.get_session() as session:
            client = session.client("codebuild")

            # create a project
            project_kwargs = {
                'name': self.project_name,
                'source': {
                    'type': 'NO_SOURCE',
                    'buildspec': open('./buildspec.yml', 'r').read(),
                    'reportBuildStatus': True,
                },
                'artifacts': {
                    'type': 'NO_ARTIFACTS'
                },
                'environment': {
                    'type': 'LINUX_CONTAINER',
                    'image': 'aws/codebuild/standard:5.0',
                    'computeType': 'BUILD_GENERAL1_SMALL',
                    'environmentVariables': [
                        {
                            'name': 'ECR_REPO_NAME',
                            'value': self.ecr_repo_name
                        },
                        {
                            'name': 'DISPATCH_ID',
                            'value': self.dispatch_id
                        },
                        {
                            'name': 'NODE_ID',
                            'value': self.node_id
                        },
                        {
                            'name': 'AWS_ACCOUNT_ID',
                            'value': self.account_id
                        }
                    ],
                    'privilegedMode': True,
                },
                'serviceRole': session.client('sts').get_caller_identity()['Arn']
            }
            try:
                response = client.create_project(**project_kwargs)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

    def teardown(self):
        with self.get_session() as session:
            client = session.client("codebuild")
            try:
                response = client.delete_project(name=self.project_name)
            except botocore.exceptions.ClientError as ce:
                app_log.exception(ce)
                exit(1)

class ExecScriptBuilder(ResourceBuilder):
    """Create the executable Python script that executes the task"""
    def __init__(self, func: Callable, args: List, kwargs: Dict, dispatch_id: str, node_id: int,
        s3_bucket: str, session):
        self.function = func
        self.args = args
        self.kwargs = kwargs
        self.bucket_name = s3_bucket

        self._func_filename = f"func-{dispatch_id}-{node_id}.pkl"
        self._result_filename = f"result-{dispatch_id}-{node_id}.pkl"
        self._script_filename = f"script-{dispatch_id}-{node_id}.py"

        super().__init__(session)
    
    def setup(self):
        # Pickle function, args and kwargs
        with open(self._func_filename, "wb") as f:
            pickle.dump((self.function, self.args, self.kwargs), f)

        # Upload pickled file to s3 bucket created
        client = self.session.client('s3')
        try:
            with open(self._func_filename, "rb") as f:
                client.upload_fileobj(f, self.bucket_name, self._func_filename)
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)

        exec_script=f"""
        import os
        import cloudpickle as pickle
        import boto3

        local_func_filename = os.path.join(/tmp/covalent/{self._func_filename})
        local_result_filename = os.path.join(/tmp/covalent/{self._result_filename})

        s3 = boto3.client("s3")
        s3.download_file({self.bucket_name}, {self._func_filename}, local_file_name)

        with open(local_func_filename, "rb") as f:
            function, args, kwargs = pickle.load(f)

        result = function(*args, **kwargs)

        with open(local_result_filename, "wb") as f:
            pickle.dump(result, f)

        s3.upload_file(local_result_filename, {self.bucket_name}, {self._result_filename})
        """

        with open(self._script_filename, "w") as f:
            f.write(exec_script)

    def teardown(self):
        if os.path.exists(self._script_filename):
            os.remove(self._script_filename)

        # Remove file from s3
        s3_resource = self.session.resource('s3')
        s3_bucket = s3_resource.Bucket(self.bucket_name)
        try:
            for s3_object in s3_bucket.objects.all():
                s3_object.delete()
        except botocore.exceptions.ClientError as ce:
            app_log.exception(ce)
            exit(1)


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
        **kwargs,
    ) -> None:
        self.credentials = credentials
        self.profile = profile
        self.region = region

        self._ecr_repo_name = None
        self._codebuild_project_name = None
        self._s3_bucket_name = None
        self._script_filename = None

        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = f"{self.credentials}"
        os.environ['AWS_PROFILE'] = f"{self.profile}"
        os.environ['AWS_REGION'] = f"{self.region}"

        super().__init__(**kwargs)

    @contextmanager
    def get_session(self) -> Session:
        yield boto3.Session(profile_name=self.profile, region_name=self.region)

    def setup(self, function: Callable, args: List, kwargs: Dict, dispatch_id: str, node_id: str):
        """Setup the infra necessary for the lambda executor"""
        self._s3_bucket_name=f"bucket-{dispatch_id}-{node_id}"
        self._ecr_repo_name = f"ecr-{dispatch_id}-{node_id}"
        self._script_filename = f"script-{dispatch_id}-{node_id}"

        with self.get_session() as session:
            #S3BucketBuilder(bucket_name=self._s3_bucket_name, session=session).setup()
            #ECRBuilder(name=self._ecr_repo_name, session=session).setup()
            ExecScriptBuilder(func=function, args=args, kwargs=kwargs,
                dispatch_id=dispatch_id, node_id=node_id, s3_bucket=self._s3_bucket_name).setup()
            DockerfileBuilder(exec_script_filename=self._script_filename).setup()

    def run(self, function: Callable, args: List, kwargs: Dict):
        pass

    def teardown(self, dispatch_id: str, node_id: str):
        with self.get_session() as session:
            #S3BucketBuilder(bucket_name=self._s3_bucket_name, session=session).teardown()
            #ECRBuilder(self._ecr_repo_name, session).teardown()
            pass

    def execute(self, function: Callable, args: List, kwargs: Dict, dispatch_id: str,
        results_dir: str, node_id: int = -1):
        self.setup(function, args, kwargs, dispatch_id=dispatch_id, node_id = node_id)
        self.run(function=function, args=args, kwargs=kwargs)
        self.teardown(dispatch_id=dispatch_id, node_id=node_id)
        return None, None, None
