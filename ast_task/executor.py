import sys
import traceback
import uuid
from collections import namedtuple
from pprint import pprint

from ast_task.asm import push, pop, exec, jump, ctx, after, build_symbol_table, asm_link, body, label, ref, \
    pprint_module

task = namedtuple('task', ['ctx', 'ep'])


class ExecutorError(RuntimeError):
    pass


class ContextKeyError(ExecutorError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class StackUnderflowError(ExecutorError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def get_ctx(db, ctx_id, id):
    try:
        return db[ctx_id][id]
    except KeyError as e:
        raise ContextKeyError(e)


def set_ctx(db, ctx_id, map):
    try:
        for id, v in map.items():
            db[ctx_id][id] = v
    except KeyError as e:
        raise ContextKeyError(*e.args)


def get_ctx_resolve(db, ctx_id, values):
    return [v for v in values if not isinstance(v, ctx)] + [get_ctx(db, ctx_id, v.id) for v in values if
                                                            isinstance(v, ctx)]


def get_ctx_resolve_kwargs(db, ctx_id, values):
    return dict(zip([k for k in sorted(values.keys())],
                    [get_ctx_resolve(db, ctx_id, [values[k]])[0] for k in sorted(values.keys())]))


def exec_instruction(label, ctx_id, ctx_db, prog_db, exec_db):
    if isinstance(prog_db[label], after):
        cmd, next = prog_db[label].opcode, prog_db[label].eps
    else:
        cmd, next = prog_db[label], []

    try:
        r = []
        if isinstance(cmd, push):
            new_ctx_id = str(uuid.uuid4())[:10]
            resolved_map = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.map)
            resolved_map.update({
                '$p': ctx_id,
                '$ep': label
            })
            ctx_db[new_ctx_id] = resolved_map
            ctx_id = new_ctx_id
        elif isinstance(cmd, pop):
            resolved_old_ctx, = get_ctx_resolve(ctx_db, ctx_id, [ctx('$p')])
            if resolved_old_ctx is None:
                raise StackUnderflowError()
            resolved_map = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.map)
            set_ctx(ctx_db, resolved_old_ctx, resolved_map)
            ctx_id = resolved_old_ctx
        elif isinstance(cmd, jump):
            resolved_ep, = get_ctx_resolve(ctx_db, ctx_id, [cmd.ep])
            r += [task(ctx_id, resolved_ep)]
        elif isinstance(cmd, exec):
            resolved_get = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.get)
            rtn = exec_db[cmd.task](**resolved_get)
            rtn = [] if rtn is None else list(rtn)
            set_ctx(ctx_db, ctx_id, dict([(k, rtn[v]) for k, v in cmd.set.items()]))
        else:
            raise NotImplementedError('Wrong opcode')

        resolved_next = get_ctx_resolve(ctx_db, ctx_id, next)
        r += [task(ctx_id, sys_next) for sys_next in resolved_next if sys_next is not None] if resolved_next else []
        return r
    except:
        et, ei, tb = sys.exc_info()

        set_ctx(ctx_db, ctx_id, {
            '$ec': '.'.join([et.__module__, et.__name__]),
            '$eo': ei,
            '$tb': tb
        })

        try:
            resolved_failure, = get_ctx_resolve(ctx_db, ctx_id, [ctx('$f')])

            next_failure = resolved_failure

            if next_failure is None:
                traceback.print_exception(et, ei, tb, file=sys.stdout)

            return [task(ctx_id, next_failure)] if next_failure else []
        except ContextKeyError:
            traceback.print_exception(et, ei, tb, file=sys.stdout)
            return []


def create_task(ctx_db, ep, ctx):
    ctx_id = str(uuid.uuid4())[:10]
    ctx_db[ctx_id] = ctx

    return task(ctx_id, ep)


def exec_tasks(code_db, ctx_db, exec_db, tasks):
    while len(tasks):
        task_obj, tasks = tasks[0], tasks[1:]
        print(task_obj, code_db.get(task_obj.ep, None))
        tasks += exec_instruction(task_obj.ep, task_obj.ctx, ctx_db, code_db, exec_db)
        # if '__et' in ctx_db[task_obj.ctx]:
        #     traceback.print_exception(ctx_db[task_obj.ctx]['__et'], ctx_db[task_obj.ctx]['__eo'], ctx_db[task_obj.ctx]['__etb'], file=sys.stdout)
        # print('\t', len(tasks_pending), 'ctx', ctx_db[task_obj.ctx])


def main():

    def log(et, ei, tb):
        traceback.print_exception(et, ei, tb, file=sys.stdout)
        return []


    def raiser():
        raise ValueError('eab')

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

    asm_code = body([
        label('proc_a', body([

            label('a', after(push({'$f': ref('failure.0')}), [ref('0')])),
            label('0', after(exec('task_a', {'a': 0, 'c': 9}, {'a': 0}), [ref('1')])),
            label('1', after(push({'a': ctx('a'), 'c': ctx('a'), '$s': ref('3'), '$f': ref('failure.0')}), [ref('2')])),
            label('2', jump(ref('..main.proc_b.0'))),
            label('3', after(pop({'$r': None}), [ref('4')])),
            label('4', after(exec('raiser', {}, {}), [ref('5')])),
            label('5', after(pop({}), [ctx('$s')])),

            label('failure', body([
                label('0', after(jump(ref('1')), [ref('1'), ref('1'), ref('1')])),
                # label('0', n(pop({'__et': ctx('__et'), '__eo': ctx('__eo'), '__etb': ctx('__etb')}), ref('1'))),
                label('1', exec('log', {'et': ctx('$ec'), 'ei': ctx('$eo'), 'tb': ctx('$tb')}, {}))
            ])),
        ])),
        label('proc_b', body([
            label('0', after(exec('task', {'a': ctx('a'), 'b': 'b'}, {'c': 0}), [ctx('$s')])),
        ]))
    ])

    x = dict(list(build_symbol_table(asm_code)))



    # exit()

    prog_db = asm_link({'main': x, })

    pprint_module(prog_db)
    ctx_db = {
        '__root': {
            '$f': None,
            '$p': None
        }
    }

    exec_tasks(prog_db, ctx_db, CONTEXT_WORKER['bodies'], [create_task(ctx_db, 'main.proc_a.a', {
        '$f': None,
        '$s': None,
        '$p': None,
        '$ep': None
    })])

if __name__ == '__main__':
    main()
