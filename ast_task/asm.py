import sys
import traceback
from collections import namedtuple


class opcode():
    pass

# References ctx variables
ctx = type('ctx', (namedtuple('ctx', ['id']), opcode), {})

# References code labels (we could easily generalise that to the K-V storage memory and allow arbitrary operations over variables)
ref = namedtuple('ref', ['label'])

# Jumps to an opcode
jump = type('jump', (namedtuple('jump', ['ep']), opcode), {})
jumpcmp = type('jumpcmp', (namedtuple('jumpcmp', ['map']), opcode), {})

# Push the current context, copy current context id into __p
push = type('push', (namedtuple('push', ['map']), opcode), {})
# Pop current context, copy variables from it
pop = type('pop', (namedtuple('pop', ['map']), opcode), {})
# Executes an arbitrary script
exec = type('exec', (namedtuple('exec', ['task', 'get', 'set']), opcode), {})
# Jump to a task after this command
after = type('after', (namedtuple('after', ['opcode', 'eps']), opcode), {})

# code organisation
label = namedtuple('label', ['name', 'body'])
body = namedtuple('body', ['items'])


class ContextKeyError(KeyError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class StackUnderflowError(IndexError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def log(et, ei, tb):
    traceback.print_exception(et, ei, tb, file=sys.stdout)
    return []


def raiser():
    raise ValueError('eab')

# What if each task is as well expected to have an affinity (?)
# Specifically, what about purely local objects: for example, sockets or at least temporary files
# We should keep the

LOCAL_MEMORY = {
    'uuid' : "/fff//fff/fff/ffff",
    'uuid2': "iterator_instance" ,
}

CONTEXT_WORKER = {
    'bodies': {
        'task_a': lambda a, c: (a,),
        'task': lambda a, b: (a * b,),
        'log': log,
        'raiser': raiser
    }
}

asm_ = body([
    label('proc_a', body([
        label('0', after(exec('task_a', {'a': 0, 'c': 9}, {'a': 0}), [ref('1')])),
        label('1', after(push({'a': ctx('a'), 'c': ctx('a'), '__s': ref('3'), '__f': ctx('__f')}), [ref('2')])),
        label('2', jump(ref('.proc_b.0'))),
        label('3', after(exec('raiser', {}, {}), [ref('4')])),
        label('4', after(pop({'__r': None}), [ctx('__s')])),

        label('failure', body([
            # label('0', n(pop({'__et': ctx('__et'), '__eo': ctx('__eo'), '__etb': ctx('__etb')}), ref('1'))),
            label('0', exec('log', {'et': ctx('__et'), 'ei': ctx('__eo'), 'tb': ctx('__etb')}, {}))
        ])),
    ])),
    label('proc_b', body([
        label('0', after(exec('task', {'a': ctx('a'), 'b': 'b'}, {'c': 0}), [ctx('__s')])),
    ]))
])


def solve_namespace(current, relative):
    new_name = list(current[:-1])
    for item in relative:
        if item is '':
            del new_name[-1]
        else:
            new_name.append(item)
    return '.'.join(new_name)


def rename_ref(current, expr, ref_fn=lambda initial, x: ref(x)):
    if isinstance(expr, ref):
        return ref_fn(expr, solve_namespace(current, expr.label.split('.')))
    elif isinstance(expr, dict):
        new_dict = dict()
        for k, v in expr.items():
            new_dict[k] = rename_ref(current, v, ref_fn=ref_fn)
        return new_dict
    elif isinstance(expr, list):
        new_list = list()
        for item in expr:
            new_list.append(rename_ref(current, item, ref_fn=ref_fn))
        return new_list
    elif isinstance(expr, opcode):
        new_expr_args = dict()
        for field, value in [(field, getattr(expr, field)) for field in expr._fields]:
            new_expr_args[field] = rename_ref(current, value, ref_fn=ref_fn)
        return expr.__class__(**new_expr_args)
    else:
        return expr


def asm_compile(item, namespace=None):
    if namespace is None:
        namespace = list()

    if isinstance(item, body):
        for item in item.items:
            yield from asm_compile(item, namespace)
    elif isinstance(item, label):
        if isinstance(item.body, body):
            for subitem in item.body.items:
                assert isinstance(subitem, label)
                yield from asm_compile(subitem, namespace=namespace + item.name.split('.'))
        elif isinstance(item.body, opcode):
            name = namespace + item.name.split('.')
            yield '.'.join(name), rename_ref(name, item.body)
        else:
            raise NotImplementedError('Label body can only be a list of label statements or an opcode')


def asm_link(modules):
    namespace = dict()
    for module_name, module in modules.items():
        for k, v in module.items():
            namespace[solve_namespace(module_name.split('.'), k.split('.'))] = v

    for k, v in namespace.items():
        def ref_fn(initial, to):
            if initial.label.startswith('.'):
                initial.label.split('.')
            else:
                return to
        namespace[k] = rename_ref([], v, ref_fn=ref_fn)
    return namespace
