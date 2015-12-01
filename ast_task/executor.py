import traceback
import uuid
from collections import namedtuple

import sys
from pprint import pprint

from ast_task.asm import ContextKeyError, push, pop, exec, StackUnderflowError, jump, ctx, after, asm_compile, asm_, \
    CONTEXT_WORKER, asm_link

task = namedtuple('task', ['ctx', 'ep'])


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
    return [v for v in values if not isinstance(v, ctx)] + [get_ctx(db, ctx_id, v.id) for v in values if isinstance(v, ctx)]

def get_ctx_resolve_kwargs(db, ctx_id, values):
    return dict(zip([k for k in sorted(values.keys())], [get_ctx_resolve(db, ctx_id, [values[k]])[0] for k in sorted(values.keys())]))

def run_opcode(label, ctx_id, db, prog_db, exec_db):
    try:
        if isinstance(prog_db[label], after):
            cmd, next = prog_db[label].opcode, prog_db[label].eps
        else:
            cmd, next = prog_db[label], []


        r = []

        if isinstance(cmd, push):
            new_ctx_id = str(uuid.uuid4())[:10]
            resolved_map = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.map)
            db[new_ctx_id] = dict([('__p', ctx_id), ('__ep', label)] + list(resolved_map.items()))
            ctx_id = new_ctx_id
        elif isinstance(cmd, pop):
            resolved_old_ctx, = get_ctx_resolve(ctx_db, ctx_id, [ctx('__p')])
            if resolved_old_ctx is None:
                raise StackUnderflowError()
            resolved_map = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.map)
            set_ctx(db, resolved_old_ctx, resolved_map)
            ctx_id = resolved_old_ctx
        elif isinstance(cmd, jump):
            resolved_ep, = get_ctx_resolve(ctx_db, ctx_id, [cmd.ep])
            r += [task(ctx_id, resolved_ep)]
        elif isinstance(cmd, exec):
            resolved_get = get_ctx_resolve_kwargs(ctx_db, ctx_id, cmd.get)
            rtn = exec_db[cmd.task](**resolved_get)
            rtn = [] if rtn is None else list(rtn)
            set_ctx(db, ctx_id, dict([(k, rtn[v]) for k, v in cmd.set.items()]))
        else:
            raise NotImplementedError('Wrong opcode')

        resolved_next = get_ctx_resolve(ctx_db, ctx_id, next)

        r += [task(ctx_id, sys_next) for sys_next in resolved_next] if resolved_next else []

        return r
    except:
        et, ei, tb = sys.exc_info()
        set_ctx(db, ctx_id, dict([('__et', et), ('__eo', ei), ('__etb', tb)]))

        try:
            resolved_failure, = get_ctx_resolve(db, ctx_id, [ctx('__f')])

            next_failure = resolved_failure
            return [task(ctx_id, next_failure)] if next_failure else []
        except ContextKeyError:
            return []


def run_opcodes(prog_db, ctx_db, exec_db, ep, initial_ctx):
    ctx_init_id = str(uuid.uuid4())[:10]
    ctx_db[ctx_init_id] = initial_ctx

    tasks_pending = [task(ctx_init_id, ep)]
    while len(tasks_pending):
        task_obj, tasks_pending = tasks_pending[0], tasks_pending[1:]
        print(task_obj)
        tasks_pending += run_opcode(task_obj.ep, task_obj.ctx, ctx_db, prog_db, exec_db)
        # if '__et' in ctx_db[task_obj.ctx]:
        #     traceback.print_exception(ctx_db[task_obj.ctx]['__et'], ctx_db[task_obj.ctx]['__eo'], ctx_db[task_obj.ctx]['__etb'], file=sys.stdout)
        # print('\t', len(tasks_pending), 'ctx', ctx_db[task_obj.ctx])

        # return ctx_db[]

    del ctx_db[ctx_init_id]


if __name__ == '__main__':
    prog_db = asm_link({'main': dict(list(asm_compile(asm_))), })
    ctx_db = {
        '__root': {
            '__f': None,
            '__p': None
        }
    }

    pprint(prog_db)

    run_opcodes(prog_db, ctx_db, CONTEXT_WORKER['bodies'], 'proc_a.0', {
        '__f': 'proc_a.failure.0',
        '__s': None,
        '__p': None,
        '__ep': None
    })
