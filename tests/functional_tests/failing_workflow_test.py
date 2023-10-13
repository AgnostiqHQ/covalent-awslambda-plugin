# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the Apache License 2.0 (the "License"). A copy of the
# License may be obtained with this software package or at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Use of this file is prohibited except in compliance with the License.
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import covalent as ct
import pytest


@pytest.mark.functional_tests
def test_failing_workflow():
    @ct.electron(executor="awslambda")
    def failing_task(a, b):
        raise NotImplementedError("Not implemented!!!")

    @ct.lattice
    def failing_workflow(a, b):
        failing_task(a, b)

    dispatch_id = ct.dispatch(failing_workflow)(1, 2)

    result = ct.get_result(dispatch_id, wait=True)
    assert result.status == ct.status.FAILED
