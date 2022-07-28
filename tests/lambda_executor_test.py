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

from unittest.mock import patch
import pytest
from mock import Mock
import covalent as ct
from covalent_awslambda_plugin import AWSLambdaExecutor

@pytest.fixture(scope="module")
def lambda_executor():
    yield AWSLambdaExecutor(profile_name="default", region_name="us-east-1")

def test_init(lambda_executor):
    """Test that initialization properly sets member variables."""
    assert lambda_executor.profile_name == "default"
    assert lambda_executor.region_name == "us-east-1"


#def test_deserialization(mocker):
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
#def test_function_call(mocker):
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
#def test_final_result():
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