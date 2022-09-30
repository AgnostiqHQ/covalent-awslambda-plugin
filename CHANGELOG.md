# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

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
