import ast
import os

import ast_task.tasks
from ast_task.mapper import mapper


def dump_ast(root, depth=0):
    if isinstance(root, list):
        for item in root:
            dump_ast(item, depth=depth+1)
    elif isinstance(root, ast.AST):
        print("\t"*depth, '<' + str(root.__class__.__name__) + '>', *["{}={}".format(attr, getattr(root, attr)) for attr in root._attributes])
        for field in root._fields:
            print("\t"*(depth+1), field, ':')
            dump_ast(getattr(root, field), depth+2)
    else:
        print("\t"*depth, repr(root))


def get_locals(root):
    node_ids = []
    for node in ast.walk(root):
        if isinstance(node, ast.Name):
            if node.id not in node_ids:
                node_ids.append(node.id)
    return node_ids


def map_ast(root):
    for leaf in root:
        pass

# def create_ast(root, depth=0):



if __name__ == '__main__':
    filename = os.path.join(os.path.dirname(__file__), 'tasks.py')
    with open(filename, 'r') as f:
        tree = ast.parse(f.read(), filename)
        # dump_ast(tree)
        # compile(tree, filename, 'exec')
        # print(get_locals(tree))
        module = ast_task.tasks
        mapper(module)
