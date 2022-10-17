&nbsp;

<div align="center">

<img src="./assets/aws_lambda_readme_banner.jpg" width=150%>

[![covalent](https://img.shields.io/badge/covalent-0.177.0-purple)](https://github.com/AgnostiqHQ/covalent)
[![python](https://img.shields.io/pypi/pyversions/covalent-awslambda-plugin)](https://github.com/AgnostiqHQ/covalent-awslambda-plugin)
[![tests](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/actions/workflows/tests.yml/badge.svg)](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/AgnostiqHQ/covalent-awslambda-plugin/branch/main/graph/badge.svg?token=QNTR18SR5H)](https://codecov.io/gh/AgnostiqHQ/covalent-awslambda-plugin)
[![agpl](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.en.html)

</div>

## Covalent AWS Lambda Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with [AWS Lambda](https://aws.amazon.com/lambda/) for dispatching computational tasks.

## 1. Installation

To use this plugin with Covalent, install it using `pip`:

```sh
pip install covalent-awslambda-plugin
```

## 2. Usage Example

This is an example of how a workflow can be constructed to use the AWS Lambda executor.
In the example, we train a Support Vector Machine (SVM) and use an instance of the executor
to execute the `train_svm` electron. Note that we also require [DepsPip](https://covalent.readthedocs.io/en/latest/concepts/concepts.html#depspip) which will be required to execute the electrons.

The `AWSLambdaExecutor` requires a container based AWS lambda function to already have been created in the user's AWS account with its `Container image URI` configured properly. Users can use Covalent's public Lambda executor registry i.e. `public.ecr.aws/covalent/covalent-lambda-executor:stable` when creating their Lambda functions.
This public ECR registry holds the base container image the lambda function can use to execute tasks from a workflow.

User's can pass in the name of their Lambda function to the constructor using the `function_name` argument. See our [documentation](https://covalent.readthedocs.io/en/latest/api/executors/awslambda.html) for more details.

```python
from numpy.random import permutation
from sklearn import svm, datasets
import covalent as ct

deps_pip = ct.DepsPip(
        packages=["numpy==1.23.2", "scikit-learn==1.1.2"]
)

executor = ct.executor.AWSLambdaExecutor(
        function_name="my-lambda-function",
        s3_bucket_name="covalent-lambda-job-resources",
)

# Use executor plugin to train our SVM model.
@ct.electron(
    executor=executor,
    deps_pip=deps_pip
)
def train_svm(data, C, gamma):
    X, y = data
    clf = svm.SVC(C=C, gamma=gamma)
    clf.fit(X[90:], y[90:])
    return clf

@ct.electron
def load_data():
    iris = datasets.load_iris()
    perm = permutation(iris.target.size)
    iris.data = iris.data[perm]
    iris.target = iris.target[perm]
    return iris.data, iris.target

@ct.electron
def score_svm(data, clf):
    X_test, y_test = data
    return clf.score(
        X_test[:90], y_test[:90]
    )

@ct.lattice
def run_experiment(C=1.0, gamma=0.7):
    data = load_data()
    clf = train_svm(
        data=data,
        C=C,
        gamma=gamma
    )
    score = score_svm(
        data=data,
        clf=clf
    )
    return score

# Dispatch the workflow.
dispatch_id = ct.dispatch(run_experiment)(
        C=1.0,
        gamma=0.7
)

# Wait for our result and get result value
result = ct.get_result(dispatch_id, wait=True).result

print(result)
```

During the execution of the workflow, one can navigate to the UI to see the status of the workflow. Once completed, the above script should also output a value with the score of our model.

```sh
0.8666666666666667
```
In order for the above workflow to run successfully, one has to provision the required cloud resources as mentioned in the section [Required AWS Resources](#-required-aws-resources).

## 3. Configuration

There are many configuration options that can be passed into the `ct.executor.AWSLambdaExecutor` class or by modifying the [covalent config file](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) under the section `[executors.awslambda]`

For more information about all of the possible configuration values, visit our [read the docs (RTD) guide](https://covalent.readthedocs.io/en/latest/api/executors/awslambda.html)
for this plugin.

## 4. Required AWS Resources

In order for workflows to leverage this executor, users must ensure that all the necessary IAM permissions are properly setup and configured. This executor uses the [S3](https://aws.amazon.com/s3/) and [AWS Lambda](https://aws.amazon.com/lambda/) services to execute an electron, thus the required IAM roles and policies must be configured correctly. Precisely, the following resources are needed for the executor to run any dispatched electrons properly.

| Resource     | Config Name      | Description |
| ------------ | ---------------- | ----------- |
| IAM Role     | lambda_role_name | The IAM role this lambda will assume during execution of your tasks |
| S3 Bucket    | s3_bucket_name   | The name of the S3 bucket that the executor can use to store temporary files |
| AWS Lambda   | function_name     | Name of the pre-configured AWS Lambda function use to run tasks

For exact details on how the above resources can be provisioned, visit our [read the docs (RTD) guide](https://covalent.readthedocs.io/en/latest/api/executors/awslambda.html)
for this plugin.

## Getting Started with Covalent

For more information on how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-awslambda-plugin/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
