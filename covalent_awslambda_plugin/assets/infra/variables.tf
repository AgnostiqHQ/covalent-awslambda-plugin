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
