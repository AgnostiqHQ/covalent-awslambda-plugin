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

"""This is an example of a custom Covalent executor plugin."""

# The covalent logger module is a simple wrapper around the
# These modules are used to capture print/logging statements
# inside electron definitions.
import io
from contextlib import redirect_stderr, redirect_stdout

# multiprocessing Queue objects are used for sharing variables across processes.
from multiprocessing import Queue as MPQ

# For type-hints
from typing import Any, Dict, List, Tuple

# The current status of the execution can be kept up-to-date with Covalent Result objects.
from covalent._results_manager.result import Result

# Covalent logger
from covalent._shared_files import logger

# DispatchInfo objects are used to share info of a dispatched computation between different
# tasks (electrons) of the workflow (lattice).
from covalent._shared_files.util_classes import DispatchInfo

# The function to be computed is in the form of a Covalent TransportableObject.
# This import is not strictly necessary, as it is only used for type-hints.
from covalent._workflow.transport import TransportableObject

# All executor plugins inherit from the BaseExecutor base class.
from covalent.executor import BaseExecutor

app_log = logger.app_log
log_stack_info = logger.log_stack_info

# The plugin class name must be given by the EXECUTOR_PLUGIN_NAME attribute. In case this
# module has more than one class defined, this lets Covalent know which is the executor class.
EXECUTOR_PLUGIN_NAME = "CustomExecutor"

_EXECUTOR_PLUGIN_DEFAULTS = {
    "executor_input1": "",
    "executor_input2": "",
}


class CustomExecutor(BaseExecutor):
    def __init__(
        # Inputs to an executor can be positional or keyword arguments.
        self,
        executor_input1: str,
        executor_input2: int = 0,
        **kwargs,
    ) -> None:
        self.executor_input1 = executor_input1
        self.executor_input2 = executor_input2
        self.kwargs = kwargs

        # Call the BaseExecutor initialization:
        # There are a number of optional arguments to BaseExecutor
        # that could be specfied as keyword inputs to CustomExecutor.
        base_kwargs = {}
        for key, _ in self.kwargs.items():
            if key in [
                "conda_env",
                "cache_dir",
                "current_env_on_conda_fail",
            ]:
                base_kwargs[key] = self.kwargs[key]

        super().__init__(**base_kwargs)

    def execute(
        self,
        function: TransportableObject,
        args: List,
        kwargs: Dict,
        info_queue: MPQ,
        task_id: int,
        dispatch_id: str,
        results_dir: str,
    ) -> Any:

        """
        Executes the input function and returns the result.

        Args:
            function: The input (serialized) python function which will be executed and
                whose result is ultimately returned by this function.
            args: List of positional arguments to be used by the function.
            kwargs: Dictionary of keyword arguments to be used by the function.
            info_queue: A multiprocessing Queue object used for shared variables across
                processes. Information about, eg, status, can be stored here.
            task_id: The ID of this task in the bigger workflow graph.
            dispatch_id: The unique identifier of the external lattice process which is
                calling this function.
            results_dir: The location of the results directory.

        Returns:
            output: The result of the executed function.
        """

        # Convert the function to be executed, which is in the form of
        # a Covalent TransportableObject, to a 'standard' Python function:
        fn = function.get_deserialized()
        app_log.debug(type(fn))

        # In this block is where operations specific to your custom executor
        # can be defined. These operations could manipulate the function, the
        # inputs/outputs, or anything that Python allows.
        external_object = ExternalClass(3)
        app_log.debug(external_object.multiplier)

        # Store the current status to this shared-between-processes object.
        info_dict = {"STATUS": Result.RUNNING}
        info_queue.put_nowait(info_dict)

        result = None
        exception = None

        with self.get_dispatch_context(DispatchInfo(dispatch_id)), redirect_stdout(
            io.StringIO()
        ) as stdout, redirect_stderr(io.StringIO()) as stderr:
            # Here we simply execute the function on the local machine.
            # But this could be sent to a more capable machine for the operation,
            # or a different Python virtual environment, or more.
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                exception = e

        # Other custom operations can be applied here.
        if result is not None:
            result = self.helper_function(result)

        debug_message = f"Function '{fn.__name__}' was executed on node {task_id}"
        app_log.debug(debug_message)

        # Update the status:
        info_dict = info_queue.get()
        info_dict["STATUS"] = Result.FAILED if result is None else Result.COMPLETED
        info_queue.put(info_dict)

        return (result, stdout.getvalue(), stderr.getvalue(), exception)

    def helper_function(self, result):
        """An example helper function."""

        return 2 * result

    def get_status(self, info_dict: dict) -> Result:
        """
        Get the current status of the task.

        Args:
            info_dict: a dictionary containing any neccessary parameters needed to query the
                status. For this class (LocalExecutor), the only info is given by the
                "STATUS" key in info_dict.

        Returns:
            A Result status object (or None, if "STATUS" is not in info_dict).
        """

        return info_dict.get("STATUS", Result.NEW_OBJ)

    def cancel(self, info_dict: dict = {}) -> Tuple[Any, str, str]:
        """
        Cancel the execution task.

        Args:
            info_dict: a dictionary containing any neccessary parameters
                needed to halt the task execution.

        Returns:
            Null values in the same structure as a successful return value (a 4-element tuple).
        """

        return (None, "", "", InterruptedError)


# This class can be used in the custom executor, but will be ignored by the
# plugin-loader, since it is not designated as the plugin class.
class ExternalClass:
    """An example external class."""

    def __init__(self, multiplier: int):
        self.multiplier = multiplier
