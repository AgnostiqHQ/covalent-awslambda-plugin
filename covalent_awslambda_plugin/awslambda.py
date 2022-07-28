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

app_log = logger.app_log
log_stack_info = logger.log_stack_info


executor_plugin_name = "AWSLambdaExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or os.path.join(os.environ.get("HOME"), ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "",
}

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
        **kwargs,
    ) -> None:
        self.credentials = credentials
        self.profile = profile

        self._ecr_repo_name = None

        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = self.credentials
        os.environ['AWS_PROFILE'] = self.profile

        super().__init__(**kwargs)

    @contextmanager
    def get_session(self) -> Session:
        """Yield a custom session using the provided credentials"""
        yield boto3.Session(profile_name=self.profile)

    def _create_ecr_if_not_exists(self):
        """Create a new registry if one does not exists"""

    def _setup_ecr(self):
        """Setup ECR repository for the workflow"""
        with self.get_session() as session:
            ecr = session.client("ecr")
            try:
                response = ecr.create_repository(repositoryName=self._ecr_repo_name)
            except botocore.exceptions.ClientError as ce:
                app_log.error(ce)
                exit(1)


    def _teardown_ecr(self):
        """Delete the create container registry"""
        with self.get_session() as session:
            ecr = session.client("ecr")
            try:
                response = ecr.delete_repository(repositoryName=self._ecr_repo_name, force=True)
            except botocore.exceptions.ClientError as ce:
                app_log.error(ce)
                exit(1)
            app_log.info(f"{self._ecr_repo_name} deleted")

    def setup(self, dispatch_id: str, node_id: str):
        """Use this method to do all the setup work necessary for the executor
        ** Create ECR
        ** Push/Pull images from ECR
        **
        * Setup an ECR registry
        """
        self._ecr_repo_name = f"covalent-dispatch-{dispatch_id}"
        self._setup_ecr()

    def run(self, function: Callable, args: List, kwargs: Dict):
        pass

    def teardown(self, dispatch_id: str, node_id: str):
        self._teardown_ecr()

    def execute(self, function: Callable, args: List, kwargs: Dict, dispatch_id: str,
        results_dir: str, node_id: int = -1):
        self.setup(dispatch_id=dispatch_id, node_id = node_id)
        self.run(function=function, args=args, kwargs=kwargs)
        self.teardown(dispatch_id=dispatch_id, node_id=node_id)
        return None, None, None
