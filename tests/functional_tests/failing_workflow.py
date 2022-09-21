import covalent as ct
from covalent._shared_files import logger
from utils.executor_instance import executor

app_log = logger.app_log
log_stack_info = logger.log_stack_info


@ct.electron(executor="awslambda")
def failing_task(a, b):
    raise NotImplementedError("Not implemented!!!")


@ct.lattice
def failing_workflow(a, b):
    failing_task(a, b)


dispatch_id = ct.dispatch(failing_workflow)(1, 2)
app_log.debug(f"AWS Lambda functional test `failing_workflow.py` dispatch id: {dispatch_id}")

result = ct.get_result(dispatch_id, wait=True)
assert result.status == ct.status.FAILED
