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

"""Tests for Covalent AWSLambda executor"""

from http import client
import os
from contextlib import contextmanager
from unittest.mock import MagicMixin

import botocore.exceptions
import pytest
from mock import MagicMock, call

from covalent_awslambda_plugin import AWSLambdaExecutor


@pytest.fixture
def lambda_executor():
    return AWSLambdaExecutor(
        credentials="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        lambda_role_name="test_lambda_role",
        s3_bucket_name="test_bucket_name",
    )


def test_init():
    awslambda = AWSLambdaExecutor(
        credentials="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        lambda_role_name="test_lambda_role",
        s3_bucket_name="test_bucket_name",
    )

    assert awslambda.credentials == "~/.aws/credentials"
    assert awslambda.profile == "test_profile"
    assert awslambda.region == "us-east-1"
    assert awslambda.role_name == "test_lambda_role"
    assert awslambda.cache_dir == os.path.join(os.environ["HOME"], ".cache/covalent")
    assert awslambda.poll_freq == 5
    assert awslambda.timeout == 60
    assert awslambda.memory_size == 512
    assert awslambda.cleanup

    assert os.environ["AWS_SHARED_CREDENTIALS_FILE"] == awslambda.credentials
    assert os.environ["AWS_PROFILE"] == awslambda.profile
    assert os.environ["AWS_REGION"] == awslambda.region


def test_workdir_create(lambda_executor, mocker):
    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor._cleanup = MagicMock()

    os_path_exists_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.os.path.exists", return_value=False
    )
    os_mkdir_mock = mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.ExecScriptBuilder", return_value=MagicMock())
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder", return_value=MagicMock()
    )

    lambda_executor.run(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    os_path_exists_mock.assert_called_once()
    os_mkdir_mock.assert_called_once()


def test_function_pickle_dump(lambda_executor, mocker):
    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor._cleanup = MagicMock()

    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch("covalent_awslambda_plugin.awslambda.open", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.ExecScriptBuilder", return_value=MagicMock())
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder", return_value=MagicMock()
    )
    pickle_dump_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    lambda_executor.run(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    pickle_dump_mock.assert_called_once()


def test_upload_to_s3(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._create_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._invoke_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._get_result_object")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._cleanup")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.ExecScriptBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    lambda_executor.run(MagicMock(), MagicMock(), MagicMock(), MagicMock())

    assert session_mock.call_count == 2
    session_mock.return_value.__enter__.assert_called()
    session_mock.return_value.__enter__.return_value.client.assert_called_with("s3")
    session_mock.return_value.__enter__.return_value.client.return_value.upload_fileobj.assert_called()
    session_mock.return_value.__enter__.return_value.client.return_value.upload_file.assert_called()


def test_upload_fileobj_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.upload_fileobj.side_effect = (
        client_error_mock
    )

    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._create_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._invoke_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._get_result_object")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._cleanup")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.ExecScriptBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor.run(MagicMock(), MagicMock(), MagicMock(), MagicMock())

    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)


def test_upload_file_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.upload_file.side_effect = (
        client_error_mock
    )

    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._create_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._invoke_lambda")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._get_result_object")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._cleanup")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.ExecScriptBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor.run(MagicMock(), MagicMock(), MagicMock(), MagicMock())

    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)

def test_create_lambda_iam_get_role(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    lambda_executor.dispatch_id = "abcd"
    lambda_executor.node_id = "1"
    lambda_executor.function_name = "xyz"

    lambda_executor._create_lambda()

    assert session_mock.call_count == 2
    session_mock.return_value.__enter__.assert_called()
    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call('iam')])
    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call('lambda')])
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called_with(RoleName=lambda_executor.role_name)

def test_create_lambda_iam_get_role_exection(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    lambda_executor.dispatch_id = "abcd"
    lambda_executor.node_id = "1"
    lambda_executor.function_name = "xyz"
    lambda_executor.role_arn = "test_arn"
    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = MagicMock()

    session_mock.return_value.__enter__.return_value.client.return_value.get_role.side_effect = client_error_mock
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor._create_lambda()

    app_log_mock.exception.assert_called_with(client_error_mock)
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called()
    exit_mock.assert_called_with(1)

def test_create_lambda_create_function(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    lambda_executor.dispatch_id = "abcd"
    lambda_executor.node_id = "1"
    lambda_executor.function_name = "xyz"
    lambda_executor.role_arn = "test_arn"
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = MagicMock()
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")


    lambda_executor._create_lambda()

    session_mock.return_value.__enter__.return_value.client.assert_called_with('lambda')
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.assert_called()
    app_log_mock.warning.assert_called()


def test_create_lambda_create_function_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    lambda_executor.dispatch_id = "abcd"
    lambda_executor.node_id = "1"
    lambda_executor.function_name = "xyz"
    lambda_executor.role_arn = "test_arn"
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = MagicMock()
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.side_effect = client_error_mock


    lambda_executor._create_lambda()

    session_mock.return_value.__enter__.return_value.client.assert_called_with('lambda')
    assert not app_log_mock.warning.called
    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)


def test__is_lambda_active_called(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    lambda_executor.dispatch_id = "abcd"
    lambda_executor.node_id = "1"
    lambda_executor.function_name = "xyz"
    lambda_executor.role_arn = "test_arn"
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = MagicMock()

    lambda_executor._is_lambda_active = MagicMock()

    lambda_executor._create_lambda()

    lambda_executor._is_lambda_active.assert_called_once()
