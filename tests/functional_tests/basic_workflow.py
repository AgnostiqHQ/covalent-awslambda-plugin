import covalent as ct
from covalent._shared_files import logger
from utils.executor_instance import executor

app_log = logger.app_log
log_stack_info = logger.log_stack_info


@ct.electron(executor=executor)
def join_words(a, b):
    return ", ".join([a, b])


@ct.electron(executor=executor)
def excitement(a):
    return f"{a}!"


@ct.lattice
def simple_workflow(a, b):
    phrase = join_words(a, b)
    return excitement(phrase)


dispatch_id = ct.dispatch(simple_workflow)("Hello", "World")
app_log.debug(f"AWS Lambda functional test `basic_workflow.py` dispatch id: {dispatch_id}")

result = ct.get_result(dispatch_id, wait=True)
status = str(result.status)

assert status == str(ct.status.COMPLETED)
