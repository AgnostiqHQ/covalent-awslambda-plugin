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

import os
from unittest.mock import MagicMock

import pytest

from covalent_awslambda_plugin.exec import handler


@pytest.fixture
def event():
    return {
        "S3_BUCKET_NAME": "test",
        "COVALENT_TASK_FUNC_FILENAME": "test_function.pkl",
        "RESULT_FILENAME": "test_result.pkl",
    }


def test_assert_os_environ_home(mocker, event):
    os_environ_mock = mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    os_environ_mock.__setitem__.assert_called_with("HOME", "/tmp")


def test_assert_os_chdir_tmp(mocker, event):
    os_chdir_mock = mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    os_chdir_mock.assert_called_with("/tmp")


def test_assert_s3_bucket_name_keyerror(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    with pytest.raises(KeyError) as r:
        handler({"COVALENT_TASK_FUNC_FILENAME": "test", "RESULT_FILENAME": "test"}, None)


def test_assert_covalent_task_filename_keyerror(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    with pytest.raises(KeyError) as r:
        handler({"S3_BUCKET_NAME": "test", "RESULT_FILENAME": "test"}, None)


def test_assert_result_filename_keyerror(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    with pytest.raises(KeyError) as r:
        handler({"S3_BUCKET_NAME": "test", "COVALENT_TASK_FUNC_FILENAME": "test"}, None)


def test_assert_os_path_join(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    os_path_join_mock = mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    assert os_path_join_mock.call_count == 2


def test_assert_boto3_client(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    boto3_client_mock = mocker.patch(
        "covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock()
    )
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    boto3_client_mock.assert_called_with("s3")


def test_assert_s3_download_file_mock(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    boto3_client_mock = mocker.patch(
        "covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock()
    )
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    boto3_client_mock.return_value.download_file.assert_called_once()


def test_assert_pickle_load_mock(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    pickle_load_mock = mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    pickle_load_mock.assert_called_once()


def test_assert_function_call(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    pickle_load_mock = mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    args = pickle_load_mock.return_value[1]
    kwargs = pickle_load_mock.return_value[2]

    pickle_load_mock.return_value[0].assert_called_once_with(*args, **kwargs)


def test_assert_pickle_dump(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    mocker.patch("covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock())
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    pickle_dump_mock = mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    pickle_dump_mock.assert_called_once()


def test_assert_s3_upload_file(mocker, event):
    mocker.patch("covalent_awslambda_plugin.exec.os.chdir")
    mocker.patch("covalent_awslambda_plugin.exec.os.environ")
    mocker.patch("covalent_awslambda_plugin.exec.os.path.join")
    s3_client_mock = mocker.patch(
        "covalent_awslambda_plugin.exec.boto3.client", return_value=MagicMock()
    )
    mocker.patch("covalent_awslambda_plugin.exec.open")
    mocker.patch(
        "covalent_awslambda_plugin.exec.pickle.load",
        return_value=(MagicMock(), MagicMock(), MagicMock()),
    )
    mocker.patch("covalent_awslambda_plugin.exec.pickle.dump")

    # invoke the handler
    handler(event, None)

    s3_client_mock.return_value.upload_file.assert_called_once()
