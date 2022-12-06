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
