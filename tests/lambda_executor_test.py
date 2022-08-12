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

import botocore.exceptions
import pytest
from mock import MagicMock, call

from covalent_awslambda_plugin import AWSLambdaExecutor, DeploymentPackageBuilder


@pytest.fixture
def lambda_executor():
    return AWSLambdaExecutor(
        credentials="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        lambda_role_name="test_lambda_role",
        s3_bucket_name="test_bucket_name",
        cache_dir="~/.cache/covalent",
        poll_freq=30,
        timeout=10,
        memory_size=512,
        cleanup=True,
    )


def test_init():
    awslambda = AWSLambdaExecutor(
        credentials="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        lambda_role_name="test_lambda_role",
        s3_bucket_name="test_bucket_name",
        cache_dir="~/.cache/covalent",
        poll_freq=30,
        timeout=10,
        memory_size=512,
        cleanup=True,
    )

    assert awslambda.credentials == "~/.aws/credentials"
    assert awslambda.profile == "test_profile"
    assert awslambda.region == "us-east-1"
    assert awslambda.role_name == "test_lambda_role"
    assert awslambda.s3_bucket_name == "test_bucket_name"
    assert awslambda.cache_dir == "~/.cache/covalent"
    assert awslambda.poll_freq == 30
    assert awslambda.timeout == 10
    assert awslambda.memory_size == 512
    assert awslambda.cleanup

    assert os.environ["AWS_SHARED_CREDENTIALS_FILE"] == awslambda.credentials
    assert os.environ["AWS_PROFILE"] == awslambda.profile
    assert os.environ["AWS_REGION"] == awslambda.region


def test_setup_and_teardown_are_invoked(lambda_executor, mocker):
    "Simply assert that the setup, run and teardown methods are invoked when execute is called"
    lambda_executor.get_session = MagicMock()
    lambda_executor._is_lambda_active = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._is_key_in_bucket = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor.setup = MagicMock()
    lambda_executor.run = MagicMock()
    lambda_executor.teardown = MagicMock()

    lambda_executor.execute(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

    lambda_executor.setup.assert_called_once()
    lambda_executor.run.assert_called_once()
    lambda_executor.teardown.assert_called_once()


def test_setup_workdir_create(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._cwd = "testdir"

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    os_path_join_mock = mocker.patch("covalent_awslambda_plugin.awslambda.os.path.join")
    os_path_exists_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.os.path.exists", return_value=False
    )
    os_mkdir_mock = mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder", return_value=MagicMock()
    )

    lambda_executor.setup(task_metadata)

    os_path_exists_mock.assert_called_once()
    os_mkdir_mock.assert_called_once()


def test_deployment_package_builder(lambda_executor, mocker):
    """Test if the deployment package builder context manager enter method is invoked"""
    dispatch_id = "aabbcc"
    node_id = 0

    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    deployment_package_builder_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder", return_value=MagicMock()
    )
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    lambda_executor._create_lambda = MagicMock()
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    lambda_executor.setup(task_metadata)

    deployment_package_builder_mock.return_value.__enter__.assert_called_once()
    deployment_package_builder_mock.return_value.__exit__.assert_called_once()


def test_deployment_package_builder_base_setup(mocker):
    workdir = "testdir"
    archive_name = "test_archive"
    s3_bucket_name = "test_bucket"

    zipfile_mock = mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    os_path_exists_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True
    )
    shutil_rmtree_mock = mocker.patch("covalent_awslambda_plugin.awslambda.shutil.rmtree")
    os_mkdir_mock = mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")
    install_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install"
    )

    pkg_bldr = DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name)
    with DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name) as bldr:
        pass

    os_path_exists_mock.assert_called_once_with(pkg_bldr.target_dir)
    shutil_rmtree_mock.assert_called_once_with(pkg_bldr.target_dir)
    os_mkdir_mock.assert_called_once_with(pkg_bldr.target_dir)
    assert install_mock.call_count == 2
    zipfile_mock.assert_called_once_with(pkg_bldr.deployment_archive, mode="w")


def test_deployment_package_builder_install_method(mocker):
    workdir = "testdir"
    archive_name = "test_archive"
    s3_bucket_name = "test_bucket"

    subprocess_mock = mocker.patch("covalent_awslambda_plugin.awslambda.subprocess.run")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch("covalent_awslambda_plugin.awslambda.shutil.rmtree")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")

    with DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name) as bldr:
        pass

    assert subprocess_mock.call_count == 2


def test_function_pickle_dump(lambda_executor, mocker):
    def f(x):
        return x

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor._cleanup = MagicMock()
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.join")
    file_open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_dump_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    lambda_executor.run(f, 1, {}, {"dispatch_id": "aabbcc", "node_id": 0})

    file_open_mock.return_value.__enter__.assert_called()
    pickle_dump_mock.assert_called_once()


def test_upload_fileobj(lambda_executor, mocker):
    def f(x):
        return x

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor._cleanup = MagicMock()

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.join")
    file_open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    lambda_executor.run(f, 1, {}, {"dispatch_id": "aabbcc", "node_id": 0})

    assert file_open_mock.call_count == 2
    file_open_mock.return_value.__enter__.call_count == 2
    lambda_executor.get_session.assert_called_once()
    lambda_executor.get_session.return_value.__enter__.assert_called_once()
    lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_once_with(
        "s3"
    )
    file_open_mock.assert_called()
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_fileobj.assert_called_once()


def test_upload_fileobj_exception(lambda_executor, mocker):
    def f(x):
        return x

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor._invoke_lambda = MagicMock()
    lambda_executor._get_result_object = MagicMock()
    lambda_executor._cleanup = MagicMock()

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_fileobj.side_effect = (
        client_error_mock
    )

    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor.run(f, 1, {}, {"dispatch_id": "aabbcc", "node_id": 0})

    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)


def test_upload_file(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    target_metdata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__enter__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__exit__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install", return_value=None
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    lambda_executor.setup(target_metdata)

    lambda_executor.get_session.assert_called()
    lambda_executor.get_session.return_value.__enter__.assert_called()
    lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_with("s3")
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_file.assert_called()


def test_upload_file_exception(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    task_metdata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__enter__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__exit__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install", return_value=None
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_file.side_effect = (
        client_error_mock
    )

    lambda_executor.setup(task_metdata)

    lambda_executor.get_session.assert_called()
    lambda_executor.get_session.return_value.__enter__.assert_called()
    lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_with("s3")
    app_log_mock.exception.assert_called_once()
    exit_mock.assert_called_once_with(1)


def test_create_lambda_invocation(lambda_executor, mocker):
    """Test to see if create lambda method gets invoked"""
    dispatch_id = "aabbcc"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__enter__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__exit__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install", return_value=None
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    lambda_executor.setup(task_metadata)

    lambda_executor._create_lambda.assert_called_once_with(
        f"lambda-{dispatch_id}-{node_id}", f"archive-{dispatch_id}-{node_id}.zip"
    )


def test_create_lambda_iam_get_role(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    lambda_executor._create_lambda(lambda_function_name, archive_name)

    session_mock.return_value.__enter__.assert_called()
    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call("iam")])
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called_with(
        RoleName=lambda_executor.role_name
    )


def test_create_lambda_iam_get_role_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"
    lambda_executor._is_lambda_active = MagicMock(return_value=True)

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = {
        "Role": {"Arn": "test_arn"}
    }

    session_mock.return_value.__enter__.return_value.client.return_value.get_role.side_effect = (
        client_error_mock
    )
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor._create_lambda(lambda_function_name, archive_name)

    app_log_mock.exception.assert_called_with(client_error_mock)
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called()
    exit_mock.assert_called_with(1)


def test_create_lambda_create_function(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    lambda_executor._create_lambda(lambda_function_name, archive_name)

    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call("lambda")])
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.assert_called()


def test_create_lambda_create_function_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = MagicMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.side_effect = (
        client_error_mock
    )

    lambda_executor._create_lambda(lambda_function_name, archive_name)

    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)


def test_is_lambda_active(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    session_mock.return_value.__enter__.return_value.client.return_value.get_function.return_value = {
        "Configuration": {"State": "Active"}
    }
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    lambda_executor._is_lambda_active(lambda_function_name)

    session_mock.return_value.__enter__.return_value.client.return_value.get_function.assert_called_with(
        FunctionName=lambda_function_name
    )


def test_invoke_lambda(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    lambda_executor._invoke_lambda(lambda_function_name)

    session_mock.return_value.__enter__.return_value.client.assert_called_with("lambda")
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.assert_called_with(
        FunctionName=lambda_function_name
    )


def test_invoke_lambda_exeception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.side_effect = (
        client_error_mock
    )

    lambda_executor._invoke_lambda(lambda_function_name)

    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)


def test_is_key_in_bucket(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    result_filename = "test_file"

    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_list_objects_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.list_objects
    )
    s3_client_list_objects_mock.return_value = {"Contents": [{"Key": result_filename}]}
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    key_exists = lambda_executor._is_key_in_bucket(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_list_objects_mock.assert_called_with(Bucket=lambda_executor.s3_bucket_name)
    assert key_exists


def test_is_key_in_bucket_else_path(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    result_filename = "test_file"

    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_list_objects_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.list_objects
    )
    s3_client_list_objects_mock.return_value = {"Contents": [{"Key": "not_test_file"}]}

    return_value = lambda_executor._is_key_in_bucket(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_list_objects_mock.assert_called_with(Bucket=lambda_executor.s3_bucket_name)
    assert not return_value


def test_get_result_object(lambda_executor, mocker):
    result_filename = "test_file"
    workdir = "test_dir"
    lambda_executor._key_exists = True

    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_mock = session_client_mock.return_value.download_file
    open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.load")

    lambda_executor._key_exists = False
    lambda_executor._is_key_in_bucket = MagicMock(return_value=True)

    lambda_executor._get_result_object(workdir, result_filename)

    session_client_mock.assert_called_once_with("s3")
    s3_client_mock.assert_called_once_with(
        lambda_executor.s3_bucket_name, result_filename, os.path.join(workdir, result_filename)
    )
    open_mock.assert_called_once_with(os.path.join(workdir, result_filename), "rb")
    pickle_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


def test_get_result_object_execption(lambda_executor, mocker):
    result_filename = "test_file"
    workdir = "test_dir"
    lambda_executor._key_exists = True

    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_mock = session_client_mock.return_value.download_file
    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    s3_client_mock.side_effect = client_error_mock

    open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.load")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    lambda_executor._get_result_object(workdir, result_filename)

    session_client_mock.assert_called_once_with("s3")

    s3_client_mock.assert_called_once_with(
        lambda_executor.s3_bucket_name, result_filename, os.path.join(workdir, result_filename)
    )

    app_log_mock.exception.assert_called_once_with(client_error_mock)
    exit_mock.assert_called_once_with(1)
    open_mock.assert_called_once_with(os.path.join(workdir, result_filename), "rb")
    pickle_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


def test_teardown(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 1
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    lambda_executor.cleanup = True
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    shutil_rmtree_mock = mocker.patch("covalent_awslambda_plugin.awslambda.shutil.rmtree")
    session_resource_mock = session_mock.return_value.__enter__.return_value.resource
    session_object_mock = session_resource_mock.return_value.Object
    object_delete_mock = session_object_mock.return_value.delete
    session_client_mock = session_mock.return_value.__enter__.return_value.client
    lambda_client_mock = session_client_mock.return_value

    lambda_executor.teardown(task_metadata)

    session_resource_mock.assert_called_with("s3")
    session_object_mock.assert_has_calls(
        [call(lambda_executor.s3_bucket_name, f"func-{dispatch_id}-{node_id}.pkl")]
    )
    session_object_mock.assert_has_calls(
        [call(lambda_executor.s3_bucket_name, f"result-{dispatch_id}-{node_id}.pkl")]
    )
    session_object_mock.assert_has_calls(
        [call(lambda_executor.s3_bucket_name, f"archive-{dispatch_id}-{node_id}.zip")]
    )
    assert object_delete_mock.call_count == 3
    session_client_mock.assert_called_with("lambda")
    lambda_client_mock.delete_function.assert_called_once_with(FunctionName=lambda_function_name)
    shutil_rmtree_mock.assert_called_once()


def test_teartdown_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    dispatch_id = "aabbcc"
    node_id = 1
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    workdir = "test_workdir"
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    exit_mock = mocker.patch("covalent_awslambda_plugin.awslambda.exit")

    s3_resource_mock = session_mock.return_value.__enter__.return_value.resource
    delete_object_mock = s3_resource_mock.return_value.Object.return_value.delete

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    delete_object_mock.side_effect = client_error_mock

    client_mock = session_mock.return_value.__enter__.return_value.client
    lambda_client_mock = client_mock.return_value
    lambda_delete_function_mock = lambda_client_mock.delete_function
    lambda_delete_function_mock.side_effect = client_error_mock
    os_path_exists_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True
    )
    shutil_rmtree_mock = mocker.patch("covalent_awslambda_plugin.awslambda.shutil.rmtree")

    lambda_executor.teardown(task_metadata)

    s3_resource_mock.assert_called_once_with("s3")
    app_log_mock.exception.assert_called_with(client_error_mock)
    exit_mock.assert_called_with(1)
    client_mock.assert_called_once_with("lambda")
    lambda_delete_function_mock.assert_called_with(FunctionName=lambda_function_name)
    assert app_log_mock.exception.call_count == 2
    assert exit_mock.call_count == 2
    os_path_exists_mock.assert_called_once()
    shutil_rmtree_mock.assert_called_once()
