&nbsp;

<div align="center">

![covalent lambda plugin](AWS_20Lambda.jpg)

&nbsp;

</div>

## Covalent AWS Lambda Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with AWS [Lambda](https://aws.amazon.com/lambda/) for dispatching compute. In order for workflows to leverage this executor, users must ensure that all the necessary IAM permissions are properly setup and configured


### Executor highlights

This executor leverages the AWS lambda service for dispatching compute. The executor wraps the `function` to be executed within a [Docker](https://www.docker.com/) image, uploads it to ECR, creates a lambda function and invokes it. To executor uses AWS [CodeBuild](https://aws.amazon.com/codebuild/) to build the docker image and upload it to ECR.

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-executor-template/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-executor-template/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
