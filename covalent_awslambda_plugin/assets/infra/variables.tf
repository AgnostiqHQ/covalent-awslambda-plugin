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

variable "name" {
  default = "covalent-lambda"
  description = "Prefix to use for all provisioned resources"
}

variable "executor_base_image_tag_name" {
  default = "latest"
  description = "Image tag for image in provisioned ecr repo to be used for lambda invocations"
}

variable "aws_region" {
  default = "us-east-1"
  description = "The aws region"
}

variable "timeout" {
  default = 900
  description = "The amount of time your Lambda Function has to run in seconds"
}

variable "memory_size" {
  default = 1024
  description = "The amount of memory in MB your Lambda Function can use at runtime"
}

variable "ephemeral_storage" {
  default = 1024
  description = "Size of the ephemeral storage in MB"
}
