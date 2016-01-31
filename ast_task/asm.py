from collections import namedtuple


class opcode():
    pass


# References ctx variables
class ctx(namedtuple('ctx', ['id']), opcode):
    def __repr__(self):
        return "@({})".format(str(self.id))


class ref(namedtuple('ref', ['label']), opcode):
    def __repr__(self):
        return "#({})".format(str(self.label))


def repr_dict(d, sep=',', sepeq='='):
    return sep.join(['{}{}{}'.format(k, sepeq, repr(v)) for k, v in sorted(d.items())])


class jump(namedtuple('jump', ['ep']), opcode):
    def __repr__(self):
        return "> {}".format(repr(self.ep))



class jumpcmp(namedtuple('jumpcmp', ['name', 'op', 'map']), opcode):
    def __repr__(self):
        return "jc {}{}[{}]".format(repr(self.name), self.op, repr_dict(self.map, sep='|', sepeq=' > '))


# Push the current context, copy current context id into __p
class push(namedtuple('push', ['map']), opcode):
    def __repr__(self):
        return "push [{}]".format(repr_dict(self.map))


# Pop current context, copy variables from it
class pop(namedtuple('pop', ['map']), opcode):
    def __repr__(self):
        return "pop [{}]".format(repr_dict(self.map))


class exec(namedtuple('exec', ['task', 'get', 'set']), opcode):
    def __repr__(self):
        return "e {}[{}][{}]".format(self.task, repr_dict(self.get), repr_dict(self.set))


class nop(namedtuple('nop', []), opcode):
    def __repr__(self):
        return "nop".format()


class after(namedtuple('after', ['opcode', 'eps']), opcode):
    def __repr__(self):
        return "{} > {}".format(repr(self.opcode), ','.join([repr(x) for x in self.eps]))


class codeorg(opcode):
    pass


# code organisation
class label(namedtuple('label', ['name', 'body']), codeorg):
    def __repr__(self):
        if isinstance(self.body, body):
            return "{}:\n".format(self.name) + "\n".join(["\t{}".format(repr(item)) for item in self.body.items])
        else:
            return "{}: {}".format(self.name, repr(self.body))


# code organisation
class body(namedtuple('body', ['items']), codeorg):
    def to_repr(self, add_tabs):
        return "\n".join(["\t" * add_tabs + repr(item) for item in self.items])

    def __repr__(self):
        return "\n".join([repr(item) for item in self.items])


def pprint_module(module):
    for lbl, opcode in sorted(module.items()):
        print(lbl, opcode, sep='\t')


def _pprint(node, d=0):
    if isinstance(node, body):
        for item in node.items:
            yield from _pprint(item, d=d)
    elif isinstance(node, label):
        if isinstance(node.body, body):
            yield d, node.name, None
            for item in node.body.items:
                yield from _pprint(item, d=d+1)
        else:
            yield d, node.name, node.body
    else:
        yield d, '---', node
        return
        raise NotImplementedError('Heaven')


def pprint_body(node, depth=0):
    for d, name, expr in _pprint(node):
        print('\t' * (d + depth), name + ':', expr if expr is not None else '')


def resolve_ref_path(current, relative):
    new_name = list(current)
    for item in relative:
        if item is '':
            try:
                if new_name[-1] is not None:
                    del new_name[-1]
                else:
                    raise IndexError('Relative path')
            except IndexError:
                new_name.append(None)
        else:
            new_name.append(item)
    return '.'.join([x if x is not None else '' for x in new_name])


def resolve_ref(current, expr, ref_fn=lambda initial, x: ref(x)):
    if isinstance(expr, ref):
        return ref_fn(expr, resolve_ref_path(current[:-1], expr.label.split('.')))
    elif isinstance(expr, dict):
        new_dict = dict()
        for k, v in expr.items():
            new_dict[k] = resolve_ref(current, v, ref_fn=ref_fn)
        return new_dict
    elif isinstance(expr, list):
        new_list = list()
        for item in expr:
            new_list.append(resolve_ref(current, item, ref_fn=ref_fn))
        return new_list
    elif isinstance(expr, opcode):
        new_expr_args = dict()
        for field, value in [(field, getattr(expr, field)) for field in expr._fields]:
            new_expr_args[field] = resolve_ref(current, value, ref_fn=ref_fn)
        return expr.__class__(**new_expr_args)
    else:
        return expr


def build_symbol_table(item, ns=None):
    if ns is None:
        ns = list()

    if isinstance(item, body):
        for item in item.items:
            yield from build_symbol_table(item, ns)
    elif isinstance(item, label):
        if isinstance(item.body, body):
            for subitem in item.body.items:
                assert isinstance(subitem, label)
                yield from build_symbol_table(subitem, ns=ns + item.name.split('.'))
        elif isinstance(item.body, opcode):
            name = ns + item.name.split('.')
            yield '.'.join(name), resolve_ref(name, item.body)
        else:
            raise NotImplementedError('Label body can only be a list of label statements or an opcode')


def asm_link(modules):
    namespace = dict()
    for module_name, module in modules.items():
        for k, v in module.items():
            new_k_joined = (module_name, k)
            assert new_k_joined not in namespace
            namespace[new_k_joined] = v

    namespace_returned = dict()

    for (module_name, line_name), v in namespace.items():
        def ref_fn(initial, to):
            if initial.label.startswith('.'):
                return ref(resolve_ref_path(module_name.split('.'), initial.label.split('.')))
            else:
                return ref('.'.join(module_name.split('.') + to.split('.')))

        namespace_returned['.'.join(module_name.split('.') + line_name.split('.'))] = resolve_ref([], v, ref_fn=ref_fn)

    for k, v in namespace_returned.items():
        def ref_fn(initial, to):
            if to not in namespace_returned:
                raise KeyError('Cannot find label name: {}'.format(to))
            else:
                return to

        namespace_returned[k] = resolve_ref([], v, ref_fn=ref_fn)
    return namespace_returned
