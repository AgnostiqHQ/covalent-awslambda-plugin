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

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "s3_bucket" {
  bucket = "${var.name}-covalent-artifact-bucket"
  force_destroy = true
}

resource "aws_iam_role" "lambda_iam_role" {
  name = "${var.name}-lambda-iam-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
  managed_policy_arns = [ "arn:aws:iam::aws:policy/AWSLambdaExecute" ]

  tags = {
    "Terraform" = "true"
  }
}

resource "aws_ecr_repository" "ecr_repository" {
  name                 = "${var.name}-lambda-executor-base-ecr-repo"
  image_tag_mutability = "MUTABLE"

  force_delete = true
  image_scanning_configuration {
    scan_on_push = false
  }

  provisioner "local-exec" {
    command = "docker pull public.ecr.aws/covalent/covalent-lambda-executor:${var.executor_base_image_tag_name} && aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com && docker tag public.ecr.aws/covalent/covalent-lambda-executor:${var.executor_base_image_tag_name} ${aws_ecr_repository.ecr_repository.repository_url}:${var.executor_base_image_tag_name} && docker push ${aws_ecr_repository.ecr_repository.repository_url}:${var.executor_base_image_tag_name}"
  }
}

resource aws_lambda_function lambda {
    function_name = "${var.name}-lambda-fn"
    role = aws_iam_role.lambda_iam_role.arn
    package_type = "Image"
    timeout = var.timeout
    memory_size = var.memory_size
    image_uri = "${aws_ecr_repository.ecr_repository.repository_url}:${var.executor_base_image_tag_name}"
    ephemeral_storage {
      size = var.ephemeral_storage  # Min 512 MB and the Max 10240 MB
    }
}
