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

import botocore.exceptions
import cloudpickle as pickle
import pytest
from mock import AsyncMock, MagicMock

from covalent_awslambda_plugin import AWSLambdaExecutor


@pytest.fixture
def lambda_executor():
    return AWSLambdaExecutor(
        function_name="test_function",
        credentials_file="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        s3_bucket_name="test_bucket_name",
        poll_freq=30,
    )


def test_init():
    awslambda = AWSLambdaExecutor(
        function_name="test_function",
        credentials_file="~/.aws/credentials",
        profile="test_profile",
        region="us-east-1",
        s3_bucket_name="test_bucket_name",
        poll_freq=30,
    )

    assert awslambda.function_name == "test_function"
    assert awslambda.credentials_file == "~/.aws/credentials"
    assert awslambda.profile == "test_profile"
    assert awslambda.region == "us-east-1"
    assert awslambda.s3_bucket_name == "test_bucket_name"
    assert awslambda.poll_freq == 30


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
    exception_filename = "exception.json"

    await lambda_executor.submit_task(
        lambda_function_name, func_filaname, result_filename, exception_filename
    )

    session_mock.return_value.__enter__.return_value.client.assert_called_with("lambda")
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.assert_called_with(
        FunctionName=lambda_function_name,
        Payload=json.dumps(
            {
                "S3_BUCKET_NAME": lambda_executor.s3_bucket_name,
                "COVALENT_TASK_FUNC_FILENAME": "test.pkl",
                "RESULT_FILENAME": "result.pkl",
                "EXCEPTION_FILENAME": "exception.json",
            }
        ),
        InvocationType="Event",
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
    exception_filename = "exception.json"

    client_error_mock = botocore.exceptions.ClientError(MagicMock(), MagicMock())
    session_mock.return_value.__enter__.return_value.client.return_value.invoke.side_effect = (
        client_error_mock
    )

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.submit_task(
            lambda_function_name, func_filaname, result_filename, exception_filename
        )
        app_log_mock.exception.assert_called_with(client_error_mock)


@pytest.mark.asyncio
async def test_normal_run(lambda_executor, mocker):
    function = None
    args = []
    kwargs = {}
    dispatch_id = "asdf"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

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

    poll_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task",
        return_value=f"result-{dispatch_id}-{node_id}.pkl",
    )
    query_exception_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_task_exception"
    )
    query_result_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_result"
    )
    await lambda_executor.run(function, args, kwargs, task_metadata)

    poll_mock.assert_awaited_once()
    query_result_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_exception_during_run(lambda_executor, mocker):
    function = None
    args = []
    kwargs = {}
    dispatch_id = "asdf"
    node_id = 0
    task_metadata = {"dispatch_id": dispatch_id, "node_id": node_id}

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

    poll_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task",
        return_value=f"exception-{dispatch_id}-{node_id}.json",
    )
    query_exception_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_task_exception"
    )
    query_result_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_result"
    )
    with pytest.raises(RuntimeError):
        await lambda_executor.run(function, args, kwargs, task_metadata)

    poll_mock.assert_awaited_once()
    query_exception_mock.assert_awaited_once()


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
    s3_client_head_object_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.head_object
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    key_exists = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_head_object_mock.assert_called_with(
        Bucket=lambda_executor.s3_bucket_name, Key=result_filename
    )
    assert key_exists


@pytest.mark.asyncio
async def test_get_status_else_path(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    result_filename = "test_file"

    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_head_object_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.head_object
    )
    s3_client_head_object_mock.side_effect = botocore.exceptions.ClientError({}, "head_object")

    return_value = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_head_object_mock.assert_called_with(
        Bucket=lambda_executor.s3_bucket_name, Key=result_filename
    )
    assert not return_value


@pytest.mark.asyncio
async def test_get_status_exception_path(lambda_executor, mocker):
    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )

    result_filename = "test_file"

    session_client_mock = session_mock.return_value.__enter__.return_value.client
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    s3_client_head_object_mock = (
        session_mock.return_value.__enter__.return_value.client.return_value.head_object
    )
    s3_client_head_object_mock.side_effect = botocore.exceptions.ClientError({}, "head_object")

    return_value = await lambda_executor.get_status(result_filename)

    session_client_mock.assert_called_with("s3")
    s3_client_head_object_mock.assert_called_with(
        Bucket=lambda_executor.s3_bucket_name, Key=result_filename
    )


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


@pytest.mark.asyncio
async def test_poll_task(lambda_executor, mocker):
    lambda_executor.timeout = 5
    object_key = "test"
    get_status_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_status", return_value=True
    )
    key = await lambda_executor._poll_task([object_key])
    get_status_mock.assert_called_once()
    assert key == object_key


@pytest.mark.asyncio
async def test_poll_task_exception_path(lambda_executor, mocker):
    lambda_executor.timeout = 5
    get_status_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_status", return_value=False
    )
    asyncio_sleep_mock = mocker.patch("covalent_awslambda_plugin.awslambda.asyncio.sleep")

    with pytest.raises(TimeoutError):
        await lambda_executor._poll_task(["test"])

    get_status_mock.assert_called_once()
    asyncio_sleep_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_raise_task_exception(lambda_executor, mocker):
    task_metadata = {"dispatch_id": "abcd", "node_id": 0}
    function = None
    args = []
    kwargs = {}

    exception_filename = (
        f"exception-{task_metadata['dispatch_id']}-{task_metadata['node_id']}.json"
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._upload_task")
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.submit_task", return_value=""
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task",
        return_value=exception_filename,
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_task_exception")

    with pytest.raises(RuntimeError):
        await lambda_executor.run(function, args, kwargs, task_metadata)


@pytest.mark.asyncio
async def test_return_result_object(lambda_executor, mocker):
    task_metadata = {"dispatch_id": "abcd", "node_id": 0}
    function = None
    args = []
    kwargs = {}

    result_filename = f"result-{task_metadata['dispatch_id']}-{task_metadata['node_id']}.pkl"
    mocker.patch("covalent_awslambda_plugin.awslambda.open")
    mocker.patch("covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._upload_task")
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.submit_task", return_value=""
    )
    mocker.patch("covalent_awslambda_plugin.awslambda.app_log")
    mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._poll_task",
        return_value=result_filename,
    )
    query_result_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.query_result", return_value="object"
    )

    await lambda_executor.run(function, args, kwargs, task_metadata)

    query_result_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_task_execption(lambda_executor, mocker):
    exception_filename = "test_exepction_file"
    workdir = "test_dir"

    session_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor.get_session",
        return_value=MagicMock(),
    )
    session_client_mock = session_mock.return_value.__enter__.return_value.client
    s3_client_mock = session_client_mock.return_value.download_file
    open_mock = mocker.patch("covalent_awslambda_plugin.awslambda.open")
    json_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.json.load")

    lambda_executor.get_status = AsyncMock(return_value=True)

    await lambda_executor.query_task_exception(workdir, exception_filename)

    session_client_mock.assert_called_once_with("s3")
    s3_client_mock.assert_called_once_with(
        lambda_executor.s3_bucket_name,
        exception_filename,
        os.path.join(workdir, exception_filename),
    )
    open_mock.assert_called_once_with(os.path.join(workdir, exception_filename), "r")
    json_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


@pytest.mark.asyncio
async def test_query_task_exception_exception_path(lambda_executor, mocker):
    exception_filename = "test_file"
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
    json_load_mock = mocker.patch("covalent_awslambda_plugin.awslambda.json.load")
    app_log_mock = mocker.patch("covalent_awslambda_plugin.awslambda.app_log")

    with pytest.raises(botocore.exceptions.ClientError):
        await lambda_executor.query_task_exception(workdir, exception_filename)

        session_client_mock.assert_called_once_with("s3")

        s3_client_mock.assert_called_once_with(
            lambda_executor.s3_bucket_name,
            exception_filename,
            os.path.join(workdir, exception_filename),
        )

        app_log_mock.exception.assert_called_once_with(client_error_mock)
        open_mock.assert_called_once_with(os.path.join(workdir, exception_filename), "r")
        json_load_mock.assert_called_once_with(open_mock.return_value.__enter__.return_value)


def test_pickle_func_sync(lambda_executor):
    """Test the synchronous function pickling method."""

    def test_func(x):
        return x

    lambda_executor._pickle_func_sync(test_func, "/tmp", "test.pkl", [1], {"x": 1})
    with open("/tmp/test.pkl", "rb") as f:
        func, args, kwargs = pickle.load(f)

    assert func(1) == 1
    assert args == [1]
    assert kwargs == {"x": 1}


@pytest.mark.asyncio
async def test_pickle_func(lambda_executor, mocker):
    """Test the asynchronous function pickling method."""
    pickle_func_sync_mock = mocker.patch(
        "covalent_awslambda_plugin.awslambda.AWSLambdaExecutor._pickle_func_sync"
    )

    def test_func(x):
        return x

    await lambda_executor._pickle_func(test_func, "/tmp", "test.pkl", [1], {"x": 1})
    pickle_func_sync_mock.assert_called_once_with(test_func, "/tmp", "test.pkl", [1], {"x": 1})
