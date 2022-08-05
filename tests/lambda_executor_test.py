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

import os
from contextlib import contextmanager

import pytest
from mock import MagicMock

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


def test_function_pkl_upload_to_s3(lambda_executor, mocker):
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


# def test_deserialization(mocker):
#    """Test that the input function is deserialized."""
#
#    executor = CustomExecutor(
#        executor_input1 = "input1",
#    )
#
#    def simple_task(x):
#        return x
#
#    transport_function = TransportableObject(simple_task)
#    deserizlized_mock = mocker.patch.object(
#        transport_function,
#        "get_deserialized",
#        return_value = simple_task,
#    )
#
#    executor.execute(
#        function = transport_function,
#        args = [5],
#        kwargs = {},
#        info_queue = MPQ(),
#        task_id = 0,
#        dispatch_id = 0,
#        results_dir = "./",
#    )
#
#    deserizlized_mock.assert_called_once()
#
# def test_function_call(mocker):
#    """Test that the deserialized function is called with correct arguments."""
#
#    executor = CustomExecutor(
#        executor_input1 = "input1",
#    )
#
#    simple_task = mocker.MagicMock(return_value=0)
#    simple_task.__name__ = "simple_task"
#
#    transport_function = TransportableObject(simple_task)
#
#    # This mock is so that the call to execute uses the same simple_task object that we
#    # want to make sure is called.
#    mocker.patch.object(transport_function, "get_deserialized", return_value = simple_task)
#
#    args = [5]
#    kwargs = {"kw_arg": 10}
#    executor.execute(
#        function = transport_function,
#        args = args,
#        kwargs = kwargs,
#        info_queue = MPQ(),
#        task_id = 0,
#        dispatch_id = 0,
#        results_dir = "./",
#    )
#
#    simple_task.assert_called_once_with(5, kw_arg = 10)
#
# def test_final_result():
#    """Functional test to check that the result of the function execution is as expected."""
#
#
#    executor = ct.executor.CustomExecutor(
#        executor_input1 = "input1",
#    )
#
#    @ct.electron(executor = executor)
#    def simple_task(x):
#        return x
#
#    @ct.lattice
#    def sample_workflow(a):
#        c = simple_task(a)
#        return c
#
#    dispatch_id = ct.dispatch(sample_workflow)(5)
#    print(dispatch_id)
#    result = ct.get_result(dispatch_id=dispatch_id, wait=True)
#    print(result)
#
#    # The custom executor has a doubling of each electron's result, for illustrative purporses.
#    assert result.result == 10
#
