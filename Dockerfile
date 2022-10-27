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

ARG COVALENT_BASE_IMAGE
FROM ${COVALENT_BASE_IMAGE}

# AWS lambda specific env variables
ARG LAMBDA_TASK_ROOT=/var/task

# Install aws-lambda-cpp build dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  rsync \
  g++ \
  make \
  cmake \
  unzip \
  libcurl4-openssl-dev && \
  rm -rf /var/lib/apt/lists/* && \
  pip install --target "${LAMBDA_TASK_ROOT}" awslambdaric && \
  pip install --target "${LAMBDA_TASK_ROOT}" boto3 "covalent>=0.202.0,<1"

COPY covalent_awslambda_plugin/exec.py ${LAMBDA_TASK_ROOT}

WORKDIR ${LAMBDA_TASK_ROOT}
ENV PYTHONPATH=$PYTHONPATH:${LAMBDA_TASK_ROOT}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD ["exec.handler"]
