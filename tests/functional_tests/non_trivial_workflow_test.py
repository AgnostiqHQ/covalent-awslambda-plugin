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

import random
from dataclasses import dataclass
from typing import Dict, List

import covalent as ct
import pytest


@pytest.mark.functional_tests
def test_non_trivial_workflow():
    # Width and depth
    N = 3

    @dataclass
    class CustomMatrix:
        matrix_config: Dict
        matrix: List[List[int]]

    @ct.electron(executor="awslambda")
    def expand(x: CustomMatrix):
        n_dims = x.matrix_config["n_dims"]
        matrix = x.matrix
        new_row = [sum(matrix[i][j] for i in range(n_dims)) for j in range(n_dims)]
        new_col = [sum(matrix[i][j] for j in range(n_dims)) for i in range(n_dims)]

        diag_00 = sum(matrix[i][i] for i in range(n_dims))
        diag_n0 = sum(matrix[i][n_dims - i - 1] for i in range(n_dims))

        new_row = [diag_00] + new_row
        new_row.append(diag_n0)

        new_matrix = [new_row] + matrix
        new_matrix.append(new_row)

        for i in range(1, n_dims):
            new_matrix[i] = [new_col[i]] + matrix[i]
            new_matrix[i].append(new_col[i])

        new_mat_name = x.matrix_config["mat_name"] + "-1"

        print("In expand:")
        print(new_matrix)

        return CustomMatrix(
            matrix_config={"mat_name": new_mat_name, "n_dims": n_dims + 1}, matrix=new_matrix
        )

    @ct.electron(executor="awslambda")
    def shrink(x: List[CustomMatrix]):
        new_name = "".join(cm.matrix_config["mat_name"] for cm in x)
        new_matrix = [random.choice(x[i].matrix) for i in range(3)]

        print("In shrink:")
        print(new_matrix)

        return CustomMatrix(matrix_config={"mat_name": new_name, "n_dims": 3}, matrix=new_matrix)

    @ct.lattice
    def workflow(n):
        nodes = range(n)
        initiate = CustomMatrix(
            matrix_config={"mat_name": "luffy", "n_dims": 3},
            matrix=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        )
        result = None

        for i in nodes:
            vals = []
            for _ in nodes:
                if i == 0:
                    vals.append(expand(initiate))
                else:
                    vals.append(expand(result))
            result = shrink(vals)

        return result

    dispatch_id = ct.dispatch(workflow)(N)

    res = ct.get_result(dispatch_id, wait=True)
    status = str(res.status)

    print(res)

    assert status == str(ct.status.COMPLETED)
