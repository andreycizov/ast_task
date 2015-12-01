import ast
import inspect
import itertools
import sys
from copy import deepcopy
from pprint import pprint
from uuid import uuid4

from recordclass import recordclass

from ast_task.compiler import Unwind
from ast_task.contextdict import ContextDict
from ast_task.task import definition

DEFINITION_NAME = ".".join((definition.__module__, definition.__name__))


def _parent_name(parent_name=None, name=None):
    return '.'.join((parent_name, name) if parent_name else (name,))


def walk_ast(root, name='__root__', parent_name=None, only_fields=None, map_fn=lambda x: x):
    if isinstance(root, list):
        yield 'enter', _parent_name(parent_name, name), root
        root = map_fn(root)

        for i, item in enumerate(root):

            root[i] = map_fn(root[i])
            for subitem in walk_ast(item, name=str(i), parent_name=_parent_name(parent_name, name),
                                    only_fields=only_fields, map_fn=map_fn):
                yield subitem
        yield 'exit', _parent_name(parent_name, name), root
    elif isinstance(root, ast.AST):
        yield 'enter', _parent_name(parent_name, name), root

        root = map_fn(root)

        for field in root._fields:
            if only_fields:
                if field not in only_fields:
                    continue
            setattr(root, field, map_fn(getattr(root, field)))

            for item in walk_ast(getattr(root, field), name=field, parent_name=_parent_name(parent_name, name),
                                 only_fields=only_fields, map_fn=map_fn):
                yield item
        yield 'exit', _parent_name(parent_name, name), root
    else:
        yield 'rtn', _parent_name(parent_name, name), root


def dump_ast(root, depth=0, append_name=None):
    if isinstance(root, list) or isinstance(root, tuple):
        if append_name:
            print("\t" * (depth - 1), append_name, end=" ")
        else:
            print("\t" * (depth), end=" ")
        print('list', len(root))
        for i, item in enumerate(root):
            dump_ast(item, depth=depth + 1, append_name=str(i))
    elif isinstance(root, ast.AST):
        if append_name:
            print("\t" * (depth - 1), append_name, ':', end=" ")
        else:
            print("\t" * depth, end=" ")
        print('<' + str(root.__class__.__name__) + '>',
              *["{}={}".format(attr, getattr(root, attr, None)) for attr in root._attributes if attr not in []])
        for field in root._fields:
            dump_ast(getattr(root, field, None), depth + 2, append_name='`' + field + '`')
    else:
        if append_name:
            print("\t" * (depth - 1), end=" ")
        else:
            print("\t" * (depth), end=" ")
        print(append_name, repr(root))


def get_globals(root):
    pass


def get_import_mapping(root):
    r = dict()
    for item in [x for x in root.body if isinstance(x, ast.Import)]:
        for name in item.names:
            assert (isinstance(name, ast.alias))
            r[name.name if name.asname is None else name.asname] = '.'.join([name.name])

    for item in [x for x in root.body if isinstance(x, ast.ImportFrom)]:
        for name in item.names:
            assert (isinstance(name, ast.alias))
            r[name.name if name.asname is None else name.asname] = '.'.join([item.module, name.name])

    return r


def get_mapper_defs(root, imports):
    r = dict()
    for item in root.body:
        if isinstance(item, ast.AsyncFunctionDef) or isinstance(item, ast.FunctionDef):
            for decorator in item.decorator_list:
                assert (isinstance(decorator, ast.Name))
                assert (isinstance(decorator.ctx, ast.Load))

                if decorator.id in imports:
                    import_item = imports[decorator.id]
                    if import_item == DEFINITION_NAME:
                        r[item.name] = item
    return r


def get_def_signature(node):
    pass


def get_module_globals(module):
    return [name for name in dir(sys.modules[module.__name__]) if not name.startswith('__') or not name.startswith('_')]


def copy_ast(root):
    pass

    # how do we manage for loops?
    # getting the 'next', or iterating over a set of values
    # fire-and-forget (remember!)
    # we do not allow for loops with slicing calls


def get_chunkable_blocks(node):
    r = []
    current = []
    for action, name, item in walk_ast(node, only_fields=['body']):

        if action == 'exit':
            continue
        if isinstance(item, list):
            continue

        bodies = None
        if any([isinstance(item, ast.FunctionDef), isinstance(item, ast.AsyncFunctionDef)]):
            bodies = [item.body]
        elif isinstance(item, ast.Try):
            bodies = [item.body, item.orelse, item.finalbody] + [h.body for h in item.handlers]
        else:
            current.append(item)
            continue

        for body in bodies:
            for expr in body:
                if isinstance(expr, ast.Try):
                    r.append(current)
                    current = []
                elif any([isinstance(expr, ast.FunctionDef), isinstance(expr, ast.AsyncFunctionDef)]):
                    pass
                else:
                    current.append(expr)
    r.append(current)
    return [x for x in r if len(x)]


class RewriteName(ast.NodeTransformer):
    def __init__(self, count=0, split_names=[]):
        self.split_names = split_names
        self.count = count
        self.returns = dict()
        self.return_order = []
        super().__init__()

    def _assign_arg(self, rewriter, node, arg):
        name = '__call_arg_{}'.format(self.count)
        self.count += 1

        name_store = ast.copy_location(ast.Name(id=name, ctx=ast.copy_location(ast.Store(), node)), node)
        name_load = ast.copy_location(ast.Name(id=name, ctx=ast.copy_location(ast.Load(), node)), node)
        assign = ast.copy_location(ast.Assign(targets=[name_store], value=rewriter.visit(arg)), node)

        self.returns[name] = ('create', assign)
        self.return_order.append(name)

        return name_load

    def _assign_args(self, node):
        rewriter = RewriteName(self.count, self.split_names)
        for i, arg in enumerate(node.args):
            node.args[i] = self._assign_arg(rewriter, node, arg)
        for i, kwarg in enumerate(node.keywords):
            assert isinstance(kwarg, ast.keyword)
            node.keywords[i].value = self._assign_arg(rewriter, node, kwarg.value)
        self.returns.update(rewriter.returns)
        self.return_order = rewriter.return_order + self.return_order

    def visit_Call(self, node):
        if node.func.id in self.split_names:
            name = '__call_rnt_{}'.format(self.count)
            self.count += 1

            self._assign_args(node)
            assign_name_store = ast.copy_location(ast.Store(), node)
            assign_name = ast.copy_location(ast.Name(id=name, ctx=assign_name_store), node)
            assign = ast.copy_location(ast.Assign(targets=[assign_name], value=node), node)

            self.returns[name] = ('call', assign)
            self.return_order.append(name)

            load = ast.copy_location(ast.Load(), node)
            r = ast.copy_location(ast.Name(id=name, ctx=load), node)
            return r
        else:
            return node


def replace_chunk_blocks(body, name, split_at_names):
    to_replace = []
    to_replace_current = []

    def name_fn(additional=None):
        if not additional:
            return "{name}_{idx}".format(name=name, idx=len(to_replace))
        else:
            return "{name}__{add}".format(name=name_fn(), add=additional)

    def append_current(type, to_replace, to_replace_current, name=None):
        if name is None:
            name = name_fn()

        to_replace.append([type, name, to_replace_current])

    value_count = 0

    for expr in body:
        if any([isinstance(expr, ast.FunctionDef), isinstance(expr, ast.AsyncFunctionDef)]):
            append_current('code', to_replace, to_replace_current)
            to_replace_current = []

            block_name = name_fn(additional=expr.name)
            replace_chunk_blocks(expr.body, block_name, split_at_names)
            append_current(to_replace, expr, block_name)
        elif isinstance(expr, ast.Try):

            append_current('code', to_replace, to_replace_current)
            to_replace_current = []

            replace_chunk_blocks(expr.body, name_fn(additional='try_body'), split_at_names)
            replace_chunk_blocks(expr.finalbody, name_fn(additional='try_finalbody'), split_at_names)
            replace_chunk_blocks(expr.orelse, name_fn(additional='try_orelse'), split_at_names)
            for i, handler in enumerate(expr.handlers):
                assert isinstance(handler, ast.ExceptHandler)
                replace_chunk_blocks(handler.body, name_fn(additional='try_handler_{}'.format(i)), split_at_names)

            append_current('try', to_replace, expr, name_fn(additional='try'))
        else:
            rewriter = RewriteName(value_count, split_at_names)
            expr = rewriter.visit(expr)
            if len(rewriter.returns):
                if len(to_replace_current):
                    append_current('code', to_replace, to_replace_current)
                to_replace_current = []
                for type, values in [(type, list(x)) for type, x in
                                     itertools.groupby([rewriter.returns[idx] for idx in rewriter.return_order],
                                                       lambda x: x[0])]:
                    to_replace.append([type, name_fn(), [x for _, x in values]])
            value_count = rewriter.count
            to_replace_current.append(expr)

    append_current('code', to_replace, to_replace_current)

    body.clear()
    body += [(t, name, x) for t, name, x in to_replace]


def get_chunk_locals(body, globals):
    names_set = []
    names_get = []
    for action, name, expr in walk_ast(body):
        if isinstance(expr, ast.Name):
            if isinstance(expr.ctx, ast.Store):
                if name in globals:
                    raise SyntaxError("Globals are not allowed to be set")
                else:
                    if expr.id not in names_set:
                        names_set.append(expr.id)
            elif isinstance(expr.ctx, ast.Load):
                if expr.id not in names_get and expr.id not in globals:
                    names_get.append(expr.id)
            else:
                raise NotImplementedError("Expression type is not definite: {}".format(expr.ctx))
        elif isinstance(expr, ast.Return):
            if '___rtn' not in names_set:
                names_set.append('___rtn')
    return names_get, names_set


ChunkMapping = recordclass('ChunkMapping', ['type', 'chunk', 'success', 'failure'])


def get_chunks(body):
    chunk_map = dict()

    for type, name, chunk in body:
        if any([isinstance(chunk, ast.FunctionDef), isinstance(chunk, ast.AsyncFunctionDef)]):
            chunk_map.update(get_chunks(chunk.body))
        elif isinstance(chunk, ast.Try):
            chunk_map.update(get_chunks(chunk.body))
        else:
            chunk_map[name] = (type, chunk)

    return chunk_map


FunctionChunk = recordclass('FunctionChunk', ['async', 'body'])
TryChunk = recordclass('TryChunk', ['body', 'finalbody', 'orelse', 'handlers'])
HandlerChunk = recordclass('HandlerChunk', ['body', 'type', 'name'])
BlockChunk = recordclass('BlockChunk', ['body', 'gargs', 'sargs'])
PushChunk = recordclass('PushChunk', ['body', 'gargs', 'sargs'])
CallChunk = recordclass('CallChunk', ['return_to', 'args', 'keywords', 'body'])


def replace_handler_chunks(handlers, globals):
    r = []
    for chunk in handlers:
        assert isinstance(chunk, ast.ExceptHandler)

        r.append(HandlerChunk(replace_chunks(chunk.body, globals), chunk.type, chunk.name))
    return r


def replace_chunks(body, globals):
    r = []

    for type, name, chunk in body:
        if any([isinstance(chunk, ast.FunctionDef), isinstance(chunk, ast.AsyncFunctionDef)]):
            r.append(FunctionChunk(not isinstance(chunk, ast.FunctionDef), replace_chunks(chunk.body)))
        elif isinstance(chunk, ast.Try):
            r.append(TryChunk(replace_chunks(chunk.body, globals), replace_chunks(chunk.finalbody, globals), replace_chunks(chunk.orelse, globals),
                              replace_handler_chunks(chunk.handlers, globals)))
        elif type == 'call':
            # r.append(CallChunk(None, None, None))
            assert isinstance(chunk[0].targets[0].ctx, ast.Store)
            args = []
            for arg in chunk[0].value.args:
                assert isinstance(arg, ast.Name)
                assert isinstance(arg.ctx, ast.Load)
                args += [arg.id]
            kwargs = []
            for kwarg in chunk[0].value.keywords:
                assert isinstance(kwarg, ast.keyword)
                assert isinstance(kwarg.value.ctx, ast.Load)
                kwargs += [(kwarg.arg, kwarg.value.id)]
            r.append(CallChunk(chunk[0].targets[0].id, args, dict(kwargs), chunk[0].value.func.id))
        elif type == 'create':
            r.append(PushChunk(name, *get_chunk_locals(chunk, globals)))
        else:
            r.append(BlockChunk(name, *get_chunk_locals(chunk, globals)))

    return r

prev_context = {
    'id': uuid4(),
}

current_context = {
    'id': uuid4(),
    '_prev': prev_context['id']
}

Run = recordclass('Run', ['body', 'gargs', 'sargs', 'success', 'failure'])
Push = recordclass('Push', ['body', 'gargs', 'sargs', 'success', 'failure'])
Call = recordclass('Call', ['body', 'return_to', 'args', 'kwargs', 'success', 'failure'])
Parallel = recordclass('Parallel', ['body', 'return_to', 'success', 'failure'])
Handlers = recordclass('Handlers', ['bodies', 'success', 'failure'])
HandlersExit = recordclass('HandlersExit', ['success', 'failure'])
Wait = recordclass('Wait', ['ids', 'success', 'failure'])
Return = recordclass('Return', ['body', 'args'])


def compile_chunk_objects(chunk_branch, block_name='', failure=None):
    dep = dict()

    first = None
    last = None
    for name, item in [("{}_{}".format(block_name, i), item) for i, item in enumerate(chunk_branch)]:
        if not first:
            first = name
        if isinstance(item, FunctionChunk):
            dep.update(compile_chunk_objects(item.body, name))
        elif isinstance(item, TryChunk):
            name_body = "{}__b".format(name)
            name_finalbody_success = "{}__fin_S".format(name)
            name_finalbody_failure = "{}__fin_F".format(name)
            name_orelse = "{}__orls".format(name)
            name_handlers = "{}__hdlr".format(name)

            orelse_first, orelse_last, new_dep = compile_chunk_objects(item.orelse, name_orelse, failure)
            dep.update(new_dep)

            finalbody_S_first, finalbody_S_last, new_dep = compile_chunk_objects(item.finalbody, name_finalbody_success,
                                                                                 failure)
            dep.update(new_dep)

            finalbody_F_first, finalbody_F_last, new_dep = compile_chunk_objects(item.finalbody, name_finalbody_failure,
                                                                                 failure)
            dep.update(new_dep)

            body_first, body_last, new_dep = compile_chunk_objects(item.body, name_body, name_handlers)
            dep.update(new_dep)

            handler_prev = None

            handlers_kw = dict()
            for name_handler, handler in [("{}_{}".format(name_handlers, i), item) for i, item in
                                          enumerate(item.handlers)]:
                handler_first, handler_last, new_dep = compile_chunk_objects(handler.body, name_handler, failure)
                dep.update(new_dep)

                if handler.type is not None:
                    assert isinstance(handler.type.ctx, ast.Load)
                    handlers_kw[handler.type.id] = handler_first
                else:
                    handlers_kw[handler.type] = handler_first

                dep[handler_last].success = finalbody_S_first

                if handler_prev:
                    dep[handler_prev].failure = handler_first

                handler_prev = handler_last

            dep[name_handlers] = Handlers(handlers_kw, finalbody_S_first, finalbody_F_first)
            dep[name_handlers] = HandlersExit(handlers_kw, finalbody_S_first, finalbody_F_first)

            if handler_prev:
                dep[handler_prev].failure = finalbody_F_first
            dep[finalbody_F_last].success = failure
            dep[orelse_last].success = finalbody_S_first
            dep[body_last].success = orelse_first

            if last:
                dep[last].success = body_first

            last = finalbody_S_last
        elif isinstance(item, BlockChunk) or isinstance(item, CallChunk) or isinstance(item, PushChunk):
            if isinstance(item, BlockChunk):
                dep[name] = Run(item.body, item.gargs, item.sargs, None, failure)
            elif isinstance(item, PushChunk):
                dep[name] = Push(item.body, item.gargs, item.sargs, None, failure)
            else:
                dep[name] = Call(item.body, item.return_to, item.args, item.keywords, None, failure)

            if last:
                dep[last].success = name

            last = name
        else:
            raise NotImplementedError(item)

    return first, last, dep

# Compiler then decides when we may allow to do operations on the current stack


# We may only have an automatic iep if the commands are written in a sequence
# But we already operate on a per-sequence basis
# All of these operations are supposed to be atomic

# Assembler itself allows for atomicity of operations,
# Does not mean that operations themselves provide you with any means of control over race conditions
# This should be done on a higher level
# At least, operations have to be repeatable

push = recordclass('push', ['map', 'next'])
set_ctx = recordclass('set_ctx', ['map', 'next'])
pop = recordclass('pop', ['map', 'next'])
jump = recordclass('jump', ['name', 'next']) # Here, we may either set next to something, creating a separate thread or just leave it to NULL
tnjump = recordclass('tjump', ['map', 'false', 'next'])
decrtjump = recordclass('decrtjump', ['map', 'test', 'true', 'next'])
exec = recordclass('exec', ['body_name', 'next'])



# Any exception raised during operation is dropped into the __e context variable and then the execution jumps
# into the __f handler

code = {
    '1': push(dict(a='b', c='d', __s='7'), None),
    '2': jump('call', '3'),
    '3': pop(dict(), None),
    '7': pop(dict(a='__rtn_0'), '8'),
    '8': decrtjump(dict(__rtn_0_ctr=1), dict(__rtn_0_ctr=0), '9', None),
    '9': exec('body_using__rtn_0', None),
    'call': 0
}




# ctx
ctx = {
    '__s': None,
    '__f': None
}

# Anything that reaches the top of the stack is supposed to be terminated


def compile_chunk_objects_2(chunk_branch, block_name='', failure=None):
    dep = dict()

    first = None
    last = None
    for name, item in [("{}_{}".format(block_name, i), item) for i, item in enumerate(chunk_branch)]:
        if not first:
            first = name
        if isinstance(item, FunctionChunk):
            dep.update(compile_chunk_objects_2(item.body, name))
        elif isinstance(item, TryChunk):
            name_set = "{}__a".format(name)
            name_body = "{}__b".format(name)
            name_finalbody_success = "{}__fin_S".format(name)
            name_finalbody_failure = "{}__fin_F".format(name)
            name_orelse = "{}__orls".format(name)
            name_handlers = "{}__hdlr".format(name)



            orelse_first, orelse_last, new_dep = compile_chunk_objects_2(item.orelse, name_orelse, failure)
            dep.update(new_dep)

            finalbody_S_first, finalbody_S_last, new_dep = compile_chunk_objects_2(item.finalbody, name_finalbody_success,
                                                                                 failure)
            dep.update(new_dep)



            finalbody_F_first, finalbody_F_last, new_dep = compile_chunk_objects_2(item.finalbody, name_finalbody_failure,
                                                                                 failure)
            dep.update(new_dep)

            body_first, body_last, new_dep = compile_chunk_objects_2(item.body, name_body, name_handlers)
            dep.update(new_dep)

            dep[name_set] = push(dict(__f=finalbody_S_first), body_first)

            handler_prev = None

            handlers_kw = dict()
            for name_handler, handler in [("{}_{}".format(name_handlers, i), item) for i, item in
                                          enumerate(item.handlers)]:
                handler_first, handler_last, new_dep = compile_chunk_objects_2(handler.body, name_handler, failure)
                dep.update(new_dep)

                if handler.type is not None:
                    assert isinstance(handler.type.ctx, ast.Load)
                    handlers_kw[handler.type.id] = handler_first
                else:
                    handlers_kw[handler.type] = handler_first

                if hasattr(handler_last, 'success'):
                    dep[handler_last].success = finalbody_S_first
                else:
                    dep[handler_last].next = finalbody_S_first

                # if handler_prev:
                #     dep[handler_prev].failure = handler_first

                handler_prev = handler_last

            dep[name_handlers] = Handlers(handlers_kw, finalbody_S_first, finalbody_F_first)
            # dep[name_handlers] = HandlersExit(handlers_kw, finalbody_S_first, finalbody_F_first)

            # if handler_prev:
            #     dep[handler_prev].failure = finalbody_F_first
            # dep[finalbody_F_last].success = failure
            # dep[orelse_last].success = finalbody_S_first
            # dep[body_last].success = orelse_first

            # if last:
            #     dep[last].success = body_first

            last = finalbody_S_last
        elif isinstance(item, BlockChunk) or isinstance(item, CallChunk) or isinstance(item, PushChunk):
            if isinstance(item, BlockChunk):
                dep[name] = exec(item.body, None)
            elif isinstance(item, PushChunk):
                name_exec = name + '_e'
                name_push = name + '_p'

                if first == name:
                    first = name_exec

                name_success = name + '_s'
                dep[name_exec] = exec(item.body, name_push)
                dep[name_push] = push(dict([('__s', name_success)] + [(x, i) for i, x in enumerate(item.sargs)]), None)
                dep[name_success] = pop(item.sargs, None)
                name = name_push


            else:
                dep[name] = jump(item.body, None)

                # dep[name] = Call(item.body, item.return_to, item.args, item.keywords, None, failure)

            if last:
                if hasattr(dep[last], 'success'):
                    dep[last].success = name
                else:
                    dep[last].next = name

            last = name
        else:
            raise NotImplementedError(item)

    return first, last, dep


def get_chunk_mapping(body, current_failure=None):
    map = dict()
    chunk_map = dict()

    first_chunk_name = None
    prev_chunk_name = None

    for type, name, chunk in body:
        chunk_map[name] = chunk

        if first_chunk_name is None:
            first_chunk_name = name

        if any([isinstance(chunk, ast.FunctionDef), isinstance(chunk, ast.AsyncFunctionDef)]):
            _, _, new_map = get_chunk_mapping(chunk.body)
            map.update(new_map)
        elif isinstance(chunk, ast.Try):
            first_chunk_name_finalbody, prev_chunk_name_finalbody, new_map, new_chunk_map = get_chunk_mapping(
                chunk.finalbody,
                current_failure)
            map.update(new_map)

            first_chunk_name_orelse, prev_chunk_names_orelse, new_map = get_chunk_mapping(chunk.orelse, current_failure)
            map.update(new_map)

            first_handler_chunk_name = None
            prev_handler_chunk_name = None
            for handler in chunk.handlers:
                first_handler_name, prev_handler_name, new_map = get_chunk_mapping(handler.body, current_failure)
                map.update(new_map)

                if prev_handler_chunk_name:
                    map[prev_handler_chunk_name].failure = first_handler_name
                    map[prev_handler_chunk_name].success = first_chunk_name_finalbody

                if first_handler_chunk_name is None:
                    first_handler_chunk_name = first_handler_name

                prev_handler_chunk_name = prev_handler_name

            first_chunk_name_body, prev_chunk_name_body, new_map = get_chunk_mapping(chunk.body,
                                                                                     first_handler_chunk_name)
            map.update(new_map)
            map[prev_chunk_name_body].success = first_chunk_name_finalbody
            map[first_chunk_name_orelse].success = first_chunk_name_finalbody

            map[prev_handler_chunk_name].success = prev_chunk_name_finalbody
            map[prev_handler_chunk_name].failure = prev_chunk_name_finalbody

            if prev_chunk_name:
                map[prev_chunk_name].success = first_chunk_name_body

            prev_chunk_name = prev_chunk_name_finalbody
        else:
            if prev_chunk_name:
                map[prev_chunk_name].success = name
            map[name] = ChunkMapping(type, chunk, None, current_failure)
            prev_chunk_name = name
    return first_chunk_name, prev_chunk_name, map, chunk_map


def build_dependecy_tree():
    pass


def get_all_chunkable_blocks():
    pass


def accumulate_expr_while(body, fn):
    for item in body:
        if fn(item):
            return
        yield item
#
#
# Function = recordclass('Function', ['name', 'chunk', 'entry_point'])
# Call = recordclass('Call', ['name', 'func_name', 'return_to', 'pargs', 'args', 'success', 'failure', 'chunk'])
# Statement = recordclass('Statement', ['name', 'pargs', 'args', 'success', 'failure', 'chunk'])


def update_pargs(names, e, globals):
    if not names[e].pargs:
        names[e].pargs = []

    sargs, gargs = get_chunk_locals(names[e].chunk, globals)

    new_pargs = list()
    if names[e].success:
        new_pargs += update_pargs(names, names[e].success, globals)
    if names[e].failure:
        new_pargs += update_pargs(names, names[e].failure, globals)

    new_pargs = [np for np in new_pargs if np not in sargs]

    pargs = list(set(names[e].pargs + [parg for parg in new_pargs if parg not in gargs]))

    names[e].pargs = pargs

    return gargs + pargs


def get_def_mapping(node, my_globals, split_at):
    # dump_ast(node)
    dump_ast(Unwind(split_at).visit(node))

    return
    arg_names = []
    arg_names = []
    for arg in node.args.args:
        assert (isinstance(arg, ast.arg))
        arg_names.append(arg.arg)
    for arg in node.args.kwonlyargs:
        assert (isinstance(arg, ast.arg))
        arg_names.append(arg.arg)
    if node.args.vararg is not None:
        arg_names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        arg_names.append(node.args.kwarg.arg)
    context_vars = ContextDict(dict([(k, None) for k in arg_names]))
    context_success = [None]
    context_try = [None]

    # walk_node_body(node, context_vars, None)
    # for item in walk_ast(node):
    #     print(item)

    # pprint(get_chunkable_blocks(node))
    # new_node = deepcopy(node)
    # replace_chunk_blocks(new_node.body, node.name, split_at)
    # # dump_ast(new_node)
    #
    # entry_point, exit_point, chunk_mapping = get_chunk_mapping(new_node.body)
    #
    # function_ast = ast.FunctionDef() if isinstance(node, ast.FunctionDef) else ast.AsyncFunctionDef()
    #
    # function_ast = ast.copy_location(function_ast, node)
    # function_ast.name = node.name
    # function_ast.args = node.args.args
    # function_ast.kwonlyargs = node.args.kwonlyargs
    # function_ast.kw_defaults = node.args.kw_defaults
    # function_ast.kwarg = node.args.kwarg
    # function_ast.defaults = node.args.defaults
    # function_ast.returns = node.returns
    #
    # # dump_ast(node)
    # r = []
    # r.append(Function(node.name, function_ast, entry_point))
    # pprint(r[-1])

    my_ast = dict()

    new_node = deepcopy(node)
    replace_chunk_blocks(new_node.body, new_node.name, split_at)
    r = replace_chunks(new_node.body, my_globals)
    pprint(r)

    r2 = compile_chunk_objects_2(r, new_node.name, '<DUMMMY>')
    pprint(r2)

    # for name, (type, chunk, success, failure) in sorted(chunk_mapping.items()):
    #     assert success is None or success in chunk_mapping
    #     assert failure is None or failure in chunk_mapping
    #
    #     if type == 'call':
    #         # assert len(chunk) == 1
    #         # assert len(chunk[0].targets) == 1
    #
    #         chunk_args = []
    #         kw_args = []
    #         r.append(Call(name, chunk[0].value.func.id, chunk[0].targets[0].id, [], get_chunk_locals(chunk, my_globals),
    #                       success,
    #                       failure, chunk))
    #         my_ast[name] = r[-1]
    #     else:
    #         r.append(Statement(name, [], get_chunk_locals(chunk, my_globals), success, failure, chunk))
    #         my_ast[name] = r[-1]
    #
    #         # pprint(r[-1])
    #         # dump_ast(chunk)
    #
    # update_pargs(my_ast, entry_point, my_globals)
    #
    # for k, item in sorted(my_ast.items()):
    #     pprint(my_ast[k])
    #     dump_ast(item.chunk)

    return r


def mapper(module):
    root = ast.parse(inspect.getsource(module), module.__file__)
    # dump_ast(root)
    print(get_module_globals(module))
    print(get_import_mapping(root))

    # We've got to import tasks that are imported from other modules

    external = dict(other_func='dummy.module.task')
    internal = dict(
        [(name, '.'.join([module.__name__, name])) for name in get_mapper_defs(root, get_import_mapping(root))])

    for name, item in sorted(get_mapper_defs(root, get_import_mapping(root)).items()):
        get_def_mapping(item, get_module_globals(module) + list(module.__builtins__.keys()),
                        dict(list(external.items()) + list(internal.items())))
