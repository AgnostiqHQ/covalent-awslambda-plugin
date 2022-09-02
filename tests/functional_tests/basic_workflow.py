import covalent as ct
from utils.executor_instance import executor


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
result = ct.get_result(dispatch_id, wait=True)
status = str(result.status)

print(result)

assert status == str(ct.status.COMPLETED)
