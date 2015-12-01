import ast


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
        name_arg = self._generate_name('__call_arg_{}')
        name_arg_load = ast.copy_location(ast.Name(id=name_arg, ctx=ast.copy_location(ast.Load(), node)), node)
        name_arg_store = ast.copy_location(ast.Name(id=name_arg, ctx=ast.copy_location(ast.Store(), node)), node)
        name_arg_assign = ast.copy_location(ast.Assign(targets=[name_arg_store], value=self.visit(arg)), node)

        self.ops += [name_arg_assign]
        return name_arg_load

    def visit(self, node):
        if isinstance(node, ast.Call) and node.func.id in self.call_names:
            name_rtn = self._generate_name('__call_rnt_{}')

            new_args = []
            for arg in node.args:
                new_args.append(self._extract_arg(arg, node))
            new_keywords = []
            for kwarg in node.keywords:
                new_keywords.append(ast.keyword(arg=kwarg.arg, value=self._extract_arg(kwarg.value, node)))

            assign_ret_name = ast.copy_location(ast.Name(id=name_rtn, ctx=ast.copy_location(ast.Store(), node)), node)
            call = ast.copy_location(ast.Call(func=node.func, args=new_args, keywords=new_keywords), node)
            assign_ret = ast.copy_location(ast.Assign(targets=[assign_ret_name], value=call), node)

            self.ops.append(assign_ret)

            load = ast.copy_location(ast.Name(id=name_rtn, ctx=ast.copy_location(ast.Load(), node)), node)

            return load
        elif isinstance(node, ast.stmt):
            if self.past_stmt:
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
        self.is_stmt_top = False

    def visit(self, node):
        if isinstance(node, ast.stmt):
            subtransformer = ReplaceCall(self.count, self.call_names)
            node = subtransformer.visit(node)
            r = subtransformer.ops + [node]
            self.count = subtransformer.count
            self.generic_visit(node)
            return r
        else:
            return self.generic_visit(node)
