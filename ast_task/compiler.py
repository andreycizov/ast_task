import ast
import inspect
import sys
import uuid

from ast_task import tasks, asm
from ast_task.mapper import dump_ast, walk_ast
from ast_task.task import definition

DEFINITION_NAME = ".".join((definition.__module__, definition.__name__))


class CustomStmt(ast.stmt):
    _attributes = (
        'lineno',
        'col_offset'
    )
    _fields = ()


class CallArgAssign(CustomStmt):
    _fields = (
        'to',
        'expr',
    )


class CallArg(CustomStmt):
    _fields = (
        'name',
    )


class ExternCall(ast.Call):
    _fields = list(ast.Call._fields) + ['return_to']


class NodeTransformer(ast.NodeTransformer):
    pass


class ReplaceCall(NodeTransformer):
    def __init__(self, count, call_names):
        self.call_names = call_names
        self.count = count

        self.ops = []
        self.past_stmt = False

    def _generate_name(self, pattern):
        r = pattern.format(self.count)
        self.count += 1
        return r

    def _extract_arg(self, arg, node):
        name_arg = self._generate_name('&arg{}')
        # name_arg_load = ast.copy_location(ast.Name(id=name_arg, ctx=ast.copy_location(ast.Load(), node)), node)
        # name_arg_store = ast.copy_location(ast.Name(id=name_arg, ctx=ast.copy_location(ast.Store(), node)), node)
        # name_arg_assign = ast.copy_location(ast.Assign(targets=[name_arg_store], value=self.visit(arg)), node)

        name_arg_load = ast.copy_location(CallArg(name=name_arg), node)
        name_arg_assign = ast.copy_location(CallArgAssign(to=name_arg, expr=self.visit(arg)), node)
        self.ops += [name_arg_assign]
        return name_arg_load

    def visit(self, node):
        # Copy everything but the list fields (because they imply statements)
        # Then traverse that.
        new_node = ast.copy_location(node.__class__(), node)

        if isinstance(node, ast.Call) and node.func.id in self.call_names:
            name_rtn = self._generate_name('&rtn{}')

            new_args = []
            for arg in node.args:
                new_args.append(self._extract_arg(arg, node))
            new_keywords = []
            for kwarg in node.keywords:
                new_keywords.append(ast.keyword(arg=kwarg.arg, value=self._extract_arg(kwarg.value, node)))

            # assign_ret_name = ast.copy_location(ast.Name(id=name_rtn, ctx=ast.copy_location(ast.Store(), node)), node)
            # call = ast.copy_location(ast.Call(func=node.func, args=new_args, keywords=new_keywords), node)
            # assign_ret = ast.copy_location(ast.Assign(targets=[assign_ret_name], value=call), node)
            #
            # self.ops.append(assign_ret)

            assign_ret = ast.copy_location(
                ExternCall(func=node.func, args=new_args, keywords=new_keywords, return_to=name_rtn), node)
            self.ops.append(assign_ret)

            load = ast.copy_location(ast.Name(id=name_rtn, ctx=ast.copy_location(ast.Load(), node)), node)

            return load
        elif isinstance(node, ast.stmt):
            if self.past_stmt:
                self.past_stmt = False
                return node
            else:
                self.past_stmt = True
                return self.generic_visit(node)
        else:
            return self.generic_visit(node)


class Unwind(NodeTransformer):
    def __init__(self, call_names):
        self.count = 0
        self.call_names = call_names

    def visit(self, node):
        exprs = []
        bodies = []
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # node.body, node.decorator_list
            bodies += ['body']
        elif isinstance(node, ast.ClassDef):
            raise NotImplementedError()
        elif isinstance(node, ast.Return):
            exprs += ['value']
        elif isinstance(node, ast.Delete):
            exprs += ['targets']
        elif isinstance(node, ast.Assign):
            exprs += ['value']
        elif isinstance(node, ast.AugAssign):
            exprs += ['value']
        elif isinstance(node, ast.For) or isinstance(node, ast.AsyncFor):
            exprs += ['target', 'iter']
            bodies += ['body', 'orelse']
        elif isinstance(node, ast.If) or isinstance(node, ast.While):
            exprs += ['test']
            bodies += ['body', 'orelse']
        elif isinstance(node, ast.With) or isinstance(node, ast.AsyncWith):
            exprs += ['items']
            bodies += ['body']
        elif isinstance(node, ast.Raise):
            raise NotImplementedError('a')
        elif isinstance(node, ast.Try):
            bodies += ['body', 'handlers', 'orelse', 'finalbody']
        elif isinstance(node, ast.Assert):
            exprs += ['test', 'msg']
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            raise NotImplementedError('a')
        elif isinstance(node, ast.Global):
            raise NotImplementedError('b')
        elif isinstance(node, ast.expr) or isinstance(node, ast.Expr):
            exprs = None
        elif isinstance(node, ast.Pass):
            pass
        elif isinstance(node, ast.ExceptHandler):
            bodies += ['body']
        else:
            raise NotImplementedError(repr(node))

        subtransformer = ReplaceCall(self.count, self.call_names)
        if exprs is not None:
            for expr in exprs:
                old_expr_field = getattr(node, expr)

                new_expr_field = None
                if isinstance(old_expr_field, list):
                    new_expr_field = list()
                    for item in new_expr_field:
                        new_expr_field.append(subtransformer.visit(item))
                elif isinstance(old_expr_field, ast.AST):
                    new_expr_field = subtransformer.visit(old_expr_field)
                else:
                    raise NotImplementedError('f')

                setattr(node, expr, new_expr_field)
        else:
            node = subtransformer.visit(node)

        for body in bodies:
            old_body_field = getattr(node, body)

            if isinstance(old_body_field, list):
                new_body_field = list()
                for i, item in enumerate(old_body_field):
                    new_body_field_item = self.visit(item)
                    if isinstance(new_body_field_item, list):
                        new_body_field += new_body_field_item
                    else:
                        new_body_field.append(new_body_field_item)
            else:
                raise NotImplementedError('')
            setattr(node, body, new_body_field)
        return subtransformer.ops + [node]


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


class Compile(NodeTransformer):
    def __init__(self, call_names, globals):
        self.call_names = call_names
        self.globals = globals

    def visit(self, node):
        return node

        # If we may represent the given as a context mapping.
        # E.g. A depends on B, then every statement is a subsequent function over context

        # Function handlers should automatically receive a context
        if isinstance(node, ast.ExceptHandler):
            to_pop = {node.name: asm.ctx('$eo'), '$eo': asm.ctx('$eo')} if node.name else {'$eo': asm.ctx('$eo')}
            return asm.body([
                asm.label('entry', asm.after(asm.pop(to_pop), [asm.ref('body.0')])),
                asm.label('body', self.visit(node.body)),
                asm.label('exit', asm.jump(asm.ref('..3_fina.S')))
            ])
        elif isinstance(node, ast.Assign) or isinstance(node, ast.Expr):
            gets, sets = get_chunk_locals(node, list(self.globals.keys()))
            return asm.exec(str(uuid.uuid4())[:7], {name: asm.ref(name) for name in gets},
                            {name: asm.ref(name) for name in sets})
        elif isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
            node.body = asm.body([
                asm.label('ep', self.visit(node.body))
            ])

            return node
        elif isinstance(node, list):
            new_items = list()
            last_i = 0
            for i, item in enumerate(node[:-1]):
                item = self.visit(item)
                the_item = asm.after(item, [asm.ref(str(i + 1))]) if not isinstance(item, asm.body) else item
                new_items += [asm.label(str(i), the_item)]
                last_i = i
            if len(node):
                item = self.visit(node[-1])
                the_item = asm.after(item, [asm.ref('.exit')]) if not isinstance(item, asm.body) else item
                new_items += [asm.label(str(last_i + 1), the_item)]
            return asm.body(new_items)
        elif isinstance(node, ast.Pass):
            return asm.nop()
        elif isinstance(node, ast.Try):
            # We know that external calls require context, while any of the current operations allow to change
            # The exception handler inline.

            # How do we know the proper exit
            # Reducing the amount of variables transferred between contexts
            # We may just re-run compile for the sub-block and accumulate the required variables there.
            # We do not want to do pop/push for anything that is in the current context

            ops_child = []

            ops_body = []

            # handler.type.id



            handlers = {'.'.join([self.globals[handler.type.id].__module__, self.globals[
                handler.type.id].__name__]) if handler.type is not None else None: handler for handler in node.handlers}

            default_handler = handlers.get(None)

            handlers_compiled = {name: self.visit(node) for name, node in handlers.items()}
            handlers_labels = {name: 'entry{}'.format(i) for i, (name, node) in enumerate(handlers.items())}

            # Exit from a body should imply exit from


            body = asm.body([asm.label('try', asm.body([
                asm.label('0_body', asm.body(
                    [asm.label('enter', asm.after(asm.push({'$f': asm.ref('.1_hdlr.entry')}), [asm.ref('body.0')]))] +
                    [asm.label('body', self.visit(node.body))] +
                    [asm.label('exit', asm.after(asm.pop({}), asm.ref('.2_else')))]
                )),
                asm.label('1_hdlr', asm.body(
                    # handler must always return to finally, but should check if the
                    [asm.label('entry', asm.jumpcmp(asm.ctx('$ec'), '==',
                                                    {k: asm.ref(v) for k, v in handlers_labels.items()}))] +
                    [asm.label(label, self.visit(handlers_compiled[name])) for name, label in handlers_labels.items()]
                )),
                asm.label('2_else', asm.body([
                    asm.label('0', self.visit(node.orelse)),
                ])),
                asm.label('3_fina', asm.body([
                    asm.label('S', asm.body([

                    ])),
                    asm.label('F', asm.body([

                    ]))
                ]))
            ]))])

            # r = [asm.label('enter', asm.push({'$f': asm.ref('hdlr')})),




            return body
        else:
            return self.generic_visit(node)


def compile_module_def(root, globals, split_objs):
    # dump_ast(root)
    unwound = Unwind(call_names=split_objs.keys()).visit(root)[0]
    # dump_ast(unwound)
    dump_ast(Compile(split_objs.keys(), globals).visit(unwound))


def get_module_globals(module):
    return [name for name in dir(sys.modules[module.__name__]) if not name.startswith('__') or not name.startswith('_')]


def get_module_import_mapping(root):
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


def get_module_compilable_defs(root, imports):
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


def build_module(module):
    get_module_globals(module)

    module_root = ast.parse(inspect.getsource(module), module.__file__)

    module_imports = get_module_import_mapping(module_root)

    module_compilable_defs = get_module_compilable_defs(module_root, get_module_import_mapping(module_root))
    module_globals = get_module_globals(module) + list(module.__builtins__.keys())

    split_objs = dict([(name, '.'.join([module.__name__, name])) for name in module_compilable_defs.keys()])
    compiled_defs = dict()

    # print(module.main)
    # print(dis.dis(module.main))

    module_globals = dict(module.__builtins__)
    module_globals.update(get_module_import_mapping(module_root))

    for name, item in module_compilable_defs.items():
        compiled_defs[name] = compile_module_def(item, module_globals, split_objs)

    return compiled_defs


def main():
    build_module(tasks)


if __name__ == '__main__':
    main()
