# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

## [0.34.0] - 2023-10-13

### Changed

- Updated license to Apache 2.0

## [0.33.0] - 2023-10-11

### Added

- Added the lambda terraform files to `covalent_awslambda_plugin` folder from terraform repo ( including license blocks )

### Changed

- Modified the MANIFEST.in to include the newly added plugin files
- Added terraform ignore file paths to `.gitignore`

## [0.32.0] - 2023-04-26

### Changed

- Setting `COVALENT_PLUGIN_LOAD=false` in base executor image to avoid multiprocessing issue in lambda

## [0.31.0] - 2023-04-26

### Changed

- Added configurable covalent version in `docker` workflow to build base executor image

## [0.30.0] - 2023-04-26

### Added

- Print statements to functional tests.

## [0.29.0] - 2023-02-27

### Changed

- Removed execution_role from the executor defaults.

## [0.28.0] - 2023-02-09

### Changed

- Current path env variable in tests workflow.

## [0.27.1] - 2023-02-09

### Fixed

- Adding safe directory flag to execute git commands in the tests workflow.

## [0.27.0] - 2023-02-09

### Added
- Adding a `repository_dispatch` trigger to enable triggering this workflow from workflows in other repository

## [0.26.1] - 2023-02-09

### Fixed

- Fix broken Centos tests workflow by updating Git version.
- License checker workflow.

### Operations

- Updates for pre-commit hooks.

## [0.26.0] - 2023-02-07

### Fixed

- Broken release.yml workflow.

### Changed

- Fixed ECR repo URI in docker workflow

## [0.25.0] - 2023-01-20

### Changed

- Changed trigger from `pull_request` to `push`

### Added

- Added `pull_request` trigger to `docker` workflow for testing

### Changed

- Updated docker workflow to install covalent pre-releases, syntax fixes
- Added docker image build job to the `release.yml` workflow
- Update `Dockerfile` to include `PYTHONPATH` for aws lambda
- Update `Dockerfile` to install pre-release versions of `covalent`

## [0.24.0] - 2022-12-15

### Changed

- Removed references to `.env` file in the functional test README.

## [0.23.0] - 2022-12-06

### Changed

- Using executor aliases instead of classes for functional tests

## [0.22.0] - 2022-11-22

### Changed

- Not setting default values for profile, region, and credentials_file

## [0.21.0] - 2022-11-22

### Changed

- Functional tests using pytest and .env file configuration

## [0.20.0] - 2022-10-28

### Changed

- Bumped aws plugins version to new stable release

## [0.19.0] - 2022-10-27

### Changed

- Added Alejandro to paul blart group

## [0.18.1] - 2022-10-27

### Fixed

- Make `function_name` and `s3_bucket_name` variables optional.

## [0.18.0] - 2022-10-27

### Changed

- Updated base aws lambda executor image to explicitly install covalent assuming python slim-buster `COVALENT_BASE_IMAGE` used.

## [0.17.0] - 2022-10-25

### Changed

- Pinned version of covalent-aws-plugins to be gt than 0.7.0rc0

## [0.16.1] - 2022-10-21

### Fixed

- Remove unused file.

## [0.16.0] - 2022-10-21

### Changed

- Make function pickling async compatible.

## [0.15.0] - 2022-10-18

### Changed

- Pre-commit auto update.

## [0.14.0] - 2022-10-18

### Docs

- Updated `README` to reflect executor UX changes
### Changed

- Made `AWSLambdaExecutor` async compatible

### Added

- new methods to the Lambda executor to upload exception json files to S3 bucket
- updated polling to poll for both result/exception file
- added timeout to `_poll_task`

## [0.13.0] - 2022-10-15

### Changed

- Updated `AWSLambdaExecutor` to use an existing lambda function to execute tasks using the lambda base docker image
- Removed `setup/teardown` and `DeploymentPackageBuilder`

### Tests

- Updated the lambda unit tests

## [0.12.0] - 2022-10-14

### Added

- Adding `Dockerfile` to build the base Lambda executor image
- Update lambda `exec.py` to extract task specific metadata from the `event` input

## [0.11.2] - 2022-10-06

### Fixed

- Store `BASE_COVALENT_AWS_PLUGINS_ONLY` in a temporary file rather than storing it as an environment variable.

## [0.11.1] - 2022-10-05


### Fixed

- Falling back to config file defaults when using executor via instantiation of executor class

### Docs

- Updated docs to include more information about required/optional config values, and provide information about each cloud resource that needs to be provisioned.


## [0.11.0] - 2022-10-03


### Changed

- Revert: updated pinned covalent version for lambda zip file, and pinned to covalent-aws-plugins pre-release

## [0.10.0] - 2022-09-30

### Changed

- Updated pinned covalent version for lambda zip file, and pinned to covalent-aws-plugins pre-release

## [0.9.0] - 2022-09-30

### Added

-  Logic to specify that only the base covalent-aws-plugins package is to be installed.

### Operations

- Added license workflow

## [0.8.3] - 2022-09-22

### Fixed

- Reverted temporarily to old RemoteExecutor API
- Moved uploading deployment archive off the main thread

## [0.8.2] - 2022-09-20

### Fixed

- Function errors no longer cause the executor to poll indefinitely
- Exceptions in Lambda handler are returned
- Moved blocking steps off the main thread

## [0.8.1] - 2022-09-16

### Fixed

- Added missing await to asyncio.sleep statements

### Updated

- Added asyncio.sleep to unblock main thread when polling

## [0.8.0] - 2022-09-15

### Changed

- Updated requirements.txt to pin aws executor plugins to pre-release version 0.1.0rc0

## [0.7.1] - 2022-09-13

### Fixed

- Removed the temporary `AWSExecutor` and now using the correct `AWSExecutor` from its repository

## [0.7.0] - 2022-09-07

### Changed

- Inheriting from `AWSExecutor` now instead fof `BaseExecutor` directly

### Tests

- Updated tests to reflect above changes

## [0.6.0] - 2022-09-06


### Added

- Added live functional tests for CI pipeline

### Tests

- Enabled Codecov

## [0.5.0] - 2022-08-25

### Changed

- Changed covalent version in templated Dockerfile to correspond to 0.177.0

## [0.4.0] - 2022-08-17

### Changed

- Pinning `covalent` version to the latest stable release `0.177.0`

## [0.3.2] - 2022-08-16

### Fixed

- Make the version of Covalent required flexible
- Fixed path to Lambda JPG banner image

## [0.3.1] - 2022-08-16

### Fixed

- Fixed CI workflow
- Updated tests

## [0.3.0] - 2022-08-13

### Added

- Workflow files for release

### Tests

- Added basic unit tests for executor

## [0.2.2] - 2022-04-14

### Added

- Added unit tests for the custom executor template.

## [0.2.1] - 2022-04-13

### Fixed

- The executor no longer tries to manipulate the return value of the function if function execution failed.

## [0.2.0] - 2022-04-13

### Changed

- Slight refactor for the Covalent microservices refactor.

## [0.1.0] - 2022-03-31

### Changed

- Fixed package structure, so that the plugin is found by Covalent after installing the plugin.
- Added global variable _EXECUTOR_PLUGIN_DEFAULTS, which is now needed by Covalent.
- Changed global variable executor_plugin_name -> EXECUTOR_PLUGIN_NAME in executors to conform with PEP8.

## [0.0.1] - 2022-03-02

### Added

- Core files for this repo.
- CHANGELOG.md to track changes (this file).
- Semantic versioning in VERSION.
- CI pipeline job to enforce versioning.
