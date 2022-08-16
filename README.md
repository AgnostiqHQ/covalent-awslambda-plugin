&nbsp;

<div align="center">

<img src="./assets/aws_lambda_readme_banner.jpg" width=150%>

</div>

## Covalent AWS Lambda Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with AWS [Lambda](https://aws.amazon.com/lambda/) for dispatching compute. In order for workflows to leverage this executor, users must ensure that all the necessary IAM permissions are properly setup and configured. This executor uses the S3 and AWS Lambda service to execute an electron, thus the IAM roles/policies must be configured correctly. Precisely, the following IAM permissions are needed for the executor to run any dispatched electrons properly

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*",
                "s3-object-lambda:*"
            ],
            "Resource": [
                "arn:aws:s3:::<bucket-name>",
                "arn:aws:s3:::<bucket-name>/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:DescribeStacks",
                "cloudformation:ListStackResources",
                "cloudwatch:ListMetrics",
                "cloudwatch:GetMetricData",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcs",
                "kms:ListAliases",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:GetRole",
                "iam:GetRolePolicy",
                "iam:ListAttachedRolePolicies",
                "iam:ListRolePolicies",
                "iam:ListRoles",
                "lambda:*",
                "logs:DescribeLogGroups",
                "states:DescribeStateMachine",
                "states:ListStateMachines",
                "tag:GetResources",
                "xray:GetTraceSummaries",
                "xray:BatchGetTraces"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": "lambda.amazonaws.com"
                }
            }
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogStreams",
                "logs:GetLogEvents",
                "logs:FilterLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/*"
        }
    ]
}
```

where `<bucket-name>` is the name of the S3 bucket configured to the Lambda executor to upload and download objects from. The default bucket name is set to `covalent-lambda-job-resources` and it must be present prior to running the executor. The S3 bucket can either be created using the `awscli` or with the AWS web console.
To create a S3 bucket using the AWS CLI, the following can be used

```sh
pip install awscli
aws configure
aws s3api create-bucket --bucket `my-s3-bucket-for-covalent` --region `us-east-1`
```

Secondly, the lambda function created by this executor on AWS also needs an IAM role with suitable permisisons to execute. By default, this executor assumes there exists a IAM role `CovalentLambdaExecutionRole` with the `AWSLambdaExecute` execute policy attached to it. The policy document is summarized here for convenience

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:*"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::*"
        }
    ]
}
```


To use this plugin with Covalent, users can either clone this repository or install it via `pip install covalent-awslambda-plugin`. If the repository is cloned, the plugin can be installed as follows

```sh
git clone https://github.com/AgnostiqHQ/covalent-awslambda-plugin.git
cd covalent-awslambda-plugin
pip install -e .
```

Users can optionally configure this executor by specifying its properties in their Covalent configuration file. Following is a section showing the default configuration values for this executor

```
[executors.awslambda]
credentials = "/home/user/.aws/credentials"
profile = "default"
region = "us-east-1"
lambda_role_name = "CovalentLambdaExecutionRole"
s3_bucket_name = "covalent-lambda-job-resources"
cache_dir = "/home/user/.cache/covalent"
poll_freq = 5
timeout = 60
memory_size = 512
cleanup = true
```

To this executor in their workflows, users can either create an instance of the `AWSLambdaExecutor` class with their custom configuration values or simply use the defaults. The following code snippets illustrate how this can be done in a workflow

```python
# Custom configuration
from covalent.executor import AWSLambdaExecutor
lambda_executor = AWSLambdaExecutor(credentials="my_custom_credentials",
                    profile="custom_profile",
                    region="us-east-1",
                    lambda_role_name="custom_role_name",
                    s3_bucket_name="custom_s3_bucket_name",
                    cache_dir="custom_cache_dir_location",
                    poll_freq="custom_integer_value",
                    timeout="custom_timeout_value (max 900s)",
                    memory_size="custom_memory_size (max 512 M)",
                    cleanup="True or False")

@ct.electron(executor=lambda_executor)
def my_task(...):
    ...
```

If the values specified in the configuration file are to be used, the executor can be used as follows
```python
@ct.electron(executor="awslambda"):
def my_task(...):
    ...
```

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
