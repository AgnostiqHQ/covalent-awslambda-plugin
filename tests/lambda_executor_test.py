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
from mock import AsyncMock, MagicMock, call

from covalent_awslambda_plugin import AWSLambdaExecutor, DeploymentPackageBuilder


@pytest.fixture
def lambda_executor():
    return AWSLambdaExecutor(
        credentials_file="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        s3_bucket_name="test_bucket_name",
        execution_role="test_lambda_role",
        poll_freq=30,
        timeout=10,
        memory_size=512,
        cleanup=True,
    )


def test_init():
    awslambda = AWSLambdaExecutor(
        credentials_file="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        execution_role="test_lambda_role",
        s3_bucket_name="test_bucket_name",
        poll_freq=30,
        timeout=10,
        memory_size=512,
        cleanup=True,
    )

    assert awslambda.credentials_file == "~/.aws/credentials"
    assert awslambda.profile == "test_profile"
    assert awslambda.region == "us-east-1"
    assert awslambda.execution_role == "test_lambda_role"
    assert awslambda.s3_bucket_name == "test_bucket_name"
    assert awslambda.poll_freq == 30
    assert awslambda.timeout == 10
    assert awslambda.memory_size == 512
    assert awslambda.cleanup


@pytest.mark.asyncio
async def test_setup_and_teardown_are_invoked(lambda_executor, mocker):
    "Simply assert that the setup, run and teardown methods are invoked when execute is called"
    lambda_executor.get_session = MagicMock()
    lambda_executor._is_lambda_active = MagicMock()
    lambda_executor._create_lambda = MagicMock()
    lambda_executor.submit_task = MagicMock()
    lambda_executor.get_status = MagicMock()
    lambda_executor.query_result = MagicMock()
    lambda_executor.setup = AsyncMock()
    lambda_executor.run = AsyncMock()
    lambda_executor.teardown = AsyncMock()

    await lambda_executor.execute(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

    lambda_executor.setup.assert_awaited_once()
    lambda_executor.run.assert_awaited_once()
    lambda_executor.teardown.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_workdir_create(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._create_lambda = AsyncMock()
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

    await lambda_executor.setup(task_metadata)

    os_path_exists_mock.assert_called_once()
    os_mkdir_mock.assert_called_once()


@pytest.mark.asyncio
async def test_deployment_package_builder(lambda_executor, mocker):
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

    lambda_executor._create_lambda = AsyncMock()
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    await lambda_executor.setup(task_metadata)

    deployment_package_builder_mock.return_value.__aenter__.assert_awaited_once()
    deployment_package_builder_mock.return_value.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_deployment_package_builder_base_setup(mocker):
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
    async with DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name) as bldr:
        pass

    os_path_exists_mock.assert_called_once_with(pkg_bldr.target_dir)
    shutil_rmtree_mock.assert_called_once_with(pkg_bldr.target_dir)
    os_mkdir_mock.assert_called_once_with(pkg_bldr.target_dir)
    assert install_mock.await_count == 2
    zipfile_mock.assert_called_once_with(pkg_bldr.deployment_archive, mode="w")


def test_deployment_package_builder_write_archive(mocker):
    import pathlib

    workdir = "testdir"
    archive_name = "test_archive"
    s3_bucket_name = "test_bucket"
    zip_mock = MagicMock()

    zipfile_mock = mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    glob_mock = mocker.patch(
        "pathlib.PosixPath.rglob", return_value=[pathlib.PosixPath("covalent")]
    )
    rel_mock = mocker.patch(
        "pathlib.PosixPath.relative_to", return_value=[pathlib.PosixPath("covalent")]
    )
    pkg_bldr = DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name)
    pkg_bldr.write_deployment_archive()
    zipfile_mock.return_value.__enter__.return_value.write.assert_called_once()


@pytest.mark.asyncio
async def test_deployment_package_builder_install_method(mocker):
    workdir = "testdir"
    archive_name = "test_archive"
    s3_bucket_name = "test_bucket"

    proc_mock = MagicMock()
    proc_mock.returncode = 0
    subprocess_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.run_async_subprocess",
        return_value=(proc_mock, "", ""),
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch("covalent_awslambda_plugin.awslambda.shutil.rmtree")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.mkdir")

    async with DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name) as bldr:
        pass

    assert subprocess_mock.await_count == 2


@pytest.mark.asyncio
async def test_deployment_package_builder_install_exceptions(mocker):
    workdir = "testdir"
    archive_name = "test_archive"
    s3_bucket_name = "test_bucket"
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    proc_mock = MagicMock()
    proc_mock.returncode = 1

    subprocess_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.run_async_subprocess",
        return_value=(proc_mock, "", "error"),
    )

    with pytest.raises(RuntimeError) as ex:
        async with DeploymentPackageBuilder(workdir, archive_name, s3_bucket_name) as bldr:
            pass
        app_log_mock.error.assert_called_with("error")


@pytest.mark.asyncio
async def test_function_pickle_dump(lambda_executor, mocker):
    def f(x):
        return x

    lambda_executor._upload_task = AsyncMock()
    lambda_executor.submit_task = AsyncMock()
    lambda_executor._poll_task = AsyncMock()
    lambda_executor.get_session = MagicMock()

    lambda_executor.query_result = AsyncMock()

    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.join")
    file_open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_dump_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    await lambda_executor.run(f, 1, {}, {"dispatch_id": "aabbcc", "node_id": 0})

    file_open_mock.return_value.__enter__.assert_called()
    pickle_dump_mock.assert_called_once()


@pytest.mark.asyncio
async def test_upload_fileobj(lambda_executor, mocker):

    lambda_executor.get_session = MagicMock()

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.join")
    file_open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")

    await lambda_executor._upload_task("test_workdir", "test_func_filename")

    file_open_mock.assert_called_once()

    lambda_executor.get_session.assert_called_once()
    lambda_executor.get_session.return_value.__enter__.assert_called_once()
    lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_once_with(
        "s3"
    )
    file_open_mock.assert_called()
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_fileobj.assert_called_once()


@pytest.mark.asyncio
async def test_upload_fileobj_sync_exception(lambda_executor, mocker):
    def f(x):
        return x

    lambda_executor.get_session = MagicMock()

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_fileobj.side_effect = (
        client_error_mock
    )

    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.pickle.dump")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor._upload_task("test_workdir", "test_func_filename")
        app_log_mock.exception.assert_called_with(client_error_mock)


@pytest.mark.asyncio
async def test_setup(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    target_metdata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = AsyncMock()

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aenter__",
        return_value=None,
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aexit__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install", return_value=None
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    await lambda_executor.setup(target_metdata)

    lambda_executor.get_session.assert_called()
    lambda_executor.get_session.return_value.__enter__.assert_called()
    lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_with("s3")
    lambda_executor.get_session.return_value.__enter__.return_value.client.return_value.upload_file.assert_called()


@pytest.mark.asyncio
async def test_setup_exception(lambda_executor, mocker):
    dispatch_id = "aabbcc"
    node_id = 0
    task_metdata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = MagicMock()

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aenter__",
        return_value=None,
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aexit__", return_value=None
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

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.setup(task_metdata)

        lambda_executor.get_session.assert_called()
        lambda_executor.get_session.return_value.__enter__.assert_called()
        lambda_executor.get_session.return_value.__enter__.return_value.client.assert_called_with(
            "s3"
        )
        app_log_mock.exception.assert_called_once()


@pytest.mark.asyncio
async def test_create_lambda_invocation(lambda_executor, mocker):
    """Test to see if create lambda method gets invoked"""
    dispatch_id = "aabbcc"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    lambda_executor.get_session = MagicMock()
    lambda_executor._create_lambda = AsyncMock()
    mocker.patch("covalent_awslambda_plugin.awslambda.os.path.exists", return_value=True)
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aenter__",
        return_value=None,
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.__aexit__", return_value=None
    )
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.DeploymentPackageBuilder.install", return_value=None
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.ZipFile")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    await lambda_executor.setup(task_metadata)

    lambda_executor._create_lambda.assert_called_once_with(
        f"lambda-{dispatch_id}-{node_id}", f"archive-{dispatch_id}-{node_id}.zip"
    )


@pytest.mark.asyncio
async def test_create_lambda_iam_get_role(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = AsyncMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch("covalent_awslambda_plugin.awslambda.open")

    await lambda_executor._create_lambda(lambda_function_name, archive_name)

    session_mock.return_value.__enter__.assert_called()
    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call("iam")])
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called_with(
        RoleName=lambda_executor.execution_role
    )


@pytest.mark.asyncio
async def test_create_lambda_iam_get_role_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"
    lambda_executor._is_lambda_active = AsyncMock(return_value=True)

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.get_role.return_value = {
        "Role": {"Arn": "test_arn"}
    }

    session_mock.return_value.__enter__.return_value.client.return_value.get_role.side_effect = (
        client_error_mock
    )
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor._create_lambda(lambda_function_name, archive_name)
        app_log_mock.exception.assert_called_with(client_error_mock)

    session_mock.return_value.__enter__.return_value.client.return_value.get_role.assert_called()


@pytest.mark.asyncio
async def test_create_lambda_create_function(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = AsyncMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    await lambda_executor._create_lambda(lambda_function_name, archive_name)

    session_mock.return_value.__enter__.return_value.client.assert_has_calls([call("lambda")])
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.assert_called()


@pytest.mark.asyncio
async def test_create_lambda_create_function_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    lambda_executor._is_lambda_active = AsyncMock(return_value=True)
    dispatch_id = "abcd"
    node_id = 0

    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    archive_name = f"archive-{dispatch_id}-{node_id}.zip"

    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.create_function.side_effect = (
        client_error_mock
    )

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor._create_lambda(lambda_function_name, archive_name)
        app_log_mock.exception.assert_called_with(client_error_mock)


@pytest.mark.asyncio
async def test_is_lambda_active(lambda_executor, mocker):
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

    await lambda_executor._is_lambda_active(lambda_function_name)

    session_mock.return_value.__enter__.return_value.client.return_value.get_function.assert_called_with(
        FunctionName=lambda_function_name
    )


@pytest.mark.asyncio
async def test_submit_task(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    await lambda_executor.submit_task(lambda_function_name)

    session_mock.return_value.__enter__.return_value.client.assert_called_with("lambda")
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.assert_called_with(
        FunctionName=lambda_function_name
    )


@pytest.mark.asyncio
async def test_submit_task_exception(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.side_effect = (
        client_error_mock
    )

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.submit_task(lambda_function_name)
        app_log_mock.exception.assert_called_with(client_error_mock)


@pytest.mark.asyncio
async def test_normal_run(lambda_executor, mocker):
    open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.load")
    upload_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._upload_task"
    )

    function_response = {"StatusCode": 200}

    submit_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.submit_task",
        return_value=function_response,
    )

    poll_mock = mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task")
    query_mock = mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_result")
    function = None
    args = []
    kwargs = {}
    dispatch_id = "asdf"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}
    await lambda_executor.run(function, args, kwargs, task_metadata)
    poll_mock.assert_awaited_once()
    query_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_error_handling(lambda_executor, mocker):
    open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    pickle_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.pickle.load")
    upload_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._upload_task"
    )
    payload_mock = MagicMock()
    function_response = {"StatusCode": 200, "FunctionError": "Unhandled", "Payload": payload_mock}

    submit_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.submit_task",
        return_value=function_response,
    )

    poll_mock = mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task")
    query_mock = mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_result")
    function = None
    args = []
    kwargs = {}
    dispatch_id = "asdf"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

    with pytest.raises(RuntimeError) as ex:
        await lambda_executor.run(function, args, kwargs, task_metadata)
        payload_mock.read.assert_called()
        poll_mock.assert_not_awaited()
        query_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_status(lambda_executor, mocker):
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

    key_exists = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_list_objects_mock.assert_called_with(Bucket=lambda_executor.s3_bucket_name)
    assert key_exists


@pytest.mark.asyncio
async def test_get_status_else_path(lambda_executor, mocker):
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

    return_value = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_list_objects_mock.assert_called_with(Bucket=lambda_executor.s3_bucket_name)
    assert not return_value


@pytest.mark.asyncio
async def test_get_status_exception_path(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    result_filename = "test_file"

    session_client_mock = session_mock.return_value.__enter__.return_value.client

    s3_client_list_objects_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.list_objects
    )
    s3_client_list_objects_mock.side_effect = botocore.exceptions.ClientError({}, "list_objects")

    with pytest.raises(botocore.exceptions.ClientError) as ex:
        return_value = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_list_objects_mock.assert_called_with(Bucket=lambda_executor.s3_bucket_name)


@pytest.mark.asyncio
async def test_query_result(lambda_executor, mocker):
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

    lambda_executor.get_status = AsyncMock(return_value=True)

    await lambda_executor.query_result(workdir, result_filename)

    session_client_mock.assert_called_once_with("s3")
    s3_client_mock.assert_called_once_with(
        lambda_executor.s3_bucket_name, result_filename, os.path.join(workdir, result_filename)
    )
    open_mock.assert_called_once_with(os.path.join(workdir, result_filename), "rb")
    pickle_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


@pytest.mark.asyncio
async def test_query_result_exception(lambda_executor, mocker):
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

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.query_result(workdir, result_filename)

        session_client_mock.assert_called_once_with("s3")

        s3_client_mock.assert_called_once_with(
            lambda_executor.s3_bucket_name, result_filename, os.path.join(workdir, result_filename)
        )

        app_log_mock.exception.assert_called_once_with(client_error_mock)
        open_mock.assert_called_once_with(os.path.join(workdir, result_filename), "rb")
        pickle_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


@pytest.mark.asyncio
async def test_teardown(lambda_executor, mocker):
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

    await lambda_executor.teardown(task_metadata)

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


@pytest.mark.asyncio
async def test_teardown_exception(lambda_executor, mocker):
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

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.teardown(task_metadata)
        s3_resource_mock.assert_called_once_with("s3")
        app_log_mock.exception.assert_called_with(client_error_mock)
        client_mock.assert_called_once_with("lambda")
        lambda_delete_function_mock.assert_called_with(FunctionName=lambda_function_name)
        assert app_log_mock.exception.call_count == 2
        assert exit_mock.call_count == 2
        os_path_exists_mock.assert_called_once()
        shutil_rmtree_mock.assert_called_once()


@pytest.mark.asyncio
async def test_run_async_subprocess(lambda_executor):
    """Test awslambda executor async subprocess call"""

    test_dir, test_file, non_existent_file = "file_dir", "file.txt", "non_existent_file.txt"
    create_file = (
        f"rm -rf {test_dir} && mkdir {test_dir} && cd {test_dir} && touch {test_file} && echo 'hello remote "
        f"executor' >> {test_file} "
    )
    read_non_existent_file = f"cat {non_existent_file}"

    (
        create_file_proc,
        create_file_stdout,
        create_file_stderr,
    ) = await AWSLambdaExecutor.run_async_subprocess(create_file)

    # Test that file creation works as expected
    assert create_file_proc.returncode == 0
    assert create_file_stdout.decode() == ""
    assert create_file_stderr.decode() == ""

    # Test that file was created and written to correctly
    try:
        with open(f"{test_dir}/{test_file}", "r") as test_file:
            lines = test_file.readlines()
            assert lines[0].strip() == "hello remote executor"

    except FileNotFoundError as fe:
        pytest.fail(f'Failed to parse {test_file} with exception "{fe}"')

    # Test that reading from a non-existent file throws an error and returns a non-zero exit code
    (
        read_file_proc,
        read_file_stdout,
        read_file_stderr,
    ) = await AWSLambdaExecutor.run_async_subprocess(read_non_existent_file)

    assert read_file_proc.returncode == 1
    assert (
        read_file_stderr.decode().strip() == f"cat: {non_existent_file}: No such file or directory"
    )
