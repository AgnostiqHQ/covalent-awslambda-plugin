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

ARG COVALENT_BASE_IMAGE
FROM ${COVALENT_BASE_IMAGE}

# AWS lambda specific env variables
ARG LAMBDA_TASK_ROOT=/var/task
ARG COVALENT_PACKAGE_VERSION
ARG PRE_RELEASE

ENV COVALENT_PLUGIN_LOAD=false

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
  pip install --target "${LAMBDA_TASK_ROOT}" boto3

RUN if [ -z "$PRE_RELEASE" ]; then \
    pip install --target "${LAMBDA_TASK_ROOT}" "$COVALENT_PACKAGE_VERSION"; else \
    pip install --target "${LAMBDA_TASK_ROOT}" --pre "$COVALENT_PACKAGE_VERSION"; \
  fi

COPY covalent_awslambda_plugin/exec.py ${LAMBDA_TASK_ROOT}

WORKDIR ${LAMBDA_TASK_ROOT}
ENV PYTHONPATH=$PYTHONPATH:${LAMBDA_TASK_ROOT}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD ["exec.handler"]
