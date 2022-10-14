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

import json
import os
from unittest import result

import botocore.exceptions
import pytest
from mock import AsyncMock, MagicMock, call

from covalent_awslambda_plugin import AWSLambdaExecutor


@pytest.fixture
def lambda_executor():
    return AWSLambdaExecutor(
        function_name="test_function",
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
        function_name="test_function",
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

    assert awslambda.function_name == "test_function"
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
async def test_submit_task(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    dispatch_id = "abcd"
    node_id = 0
    lambda_function_name = f"lambda-{dispatch_id}-{node_id}"
    func_filaname = "test.pkl"
    result_filename = "result.pkl"

    await lambda_executor.submit_task(lambda_function_name, func_filaname, result_filename)

    session_mock.return_value.__enter__.return_value.client.assert_called_with("lambda")
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.assert_called_with(
        FunctionName=lambda_function_name,
        Payload=json.dumps(
            {
                "S3_BUCKET_NAME": lambda_executor.s3_bucket_name,
                "COVALENT_TASK_FUNC_FILENAME": "test.pkl",
                "RESULT_FILENAME": "result.pkl",
            }
        ),
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
    func_filaname = "test.pkl"
    result_filename = "result.pkl"

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.side_effect = (
        client_error_mock
    )

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.submit_task(lambda_function_name, func_filaname, result_filename)
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
