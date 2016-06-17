# - We need to keep the symbol table (correspondence between the initial location and the produced code)
# - a,b,c
from types import GeneratorType

from ast_task.dsl.language import Ref, Call, Const, Seq, Set, Module, Def, If, Cond, Compare, V, Else, Map
from ast_task.sys.asm import push, pop, jmp, nop, jcmp, set


class Intermediate():
    pass


class RefCtx(Intermediate):
    def __init__(self, name):
        self.name = name
        super().__init__()


class RefCode(Intermediate):
    def __init__(self, ep):
        self.ep = ep
        super().__init__()

    def __str__(self, *args, **kwargs):
        return "%{}".format(self.ep)


RefExit = '__exit'

RefReturn = '__rtn'


def compiler(module):
    return {k: list(translate_any(v)) for k, v in module.names.items()}


def translate_any(item):
    try:
        yield from {
            Seq: translate_seq,
            Set: translate_set,
            Def: translate_def,
            If: translate_if_body
        }[item.__class__](item)
    except KeyError:
        raise


def translate_if_body(item):
    names = ['else' if item.cond is None else 'if{:02d}'.format(i) for i, item in enumerate(item.conds)]
    exit_names = names[1:] + ['exit']

    for name, exit_name, cond in zip(names, exit_names, item.conds):
        if cond.cond is not None:
            yield name + '.ep', jcmp('!' + cond.cond.op, cond.cond.a, cond.cond.b, RefCode(exit_name + '.ep'))
            yield name, translate_any(cond.body)
        else:
            yield name + '.ep', nop()
            yield name, translate_any(cond.body)
        yield name + '.xp', jmp(RefCode('.exit.ep'))

    yield 'exit.ep', nop()


def translate_def(item):
    if isinstance(item.body, Seq):
        yield from translate_seq(item.body)
        yield 'return', jmp(Ref(RefExit))
    else:
        raise ValueError('Body operand of Seq cannot be {}, must be list'.format(item.a.__class__.__name__))


def translate_seq(seq):
    if isinstance(seq.body, list):
        for i, item in enumerate(seq.body):
            yield '{:03d}'.format(i), translate_any(item)
    else:
        raise ValueError('Body operand of Seq cannot be {}, must be list'.format(seq.body.__class__.__name__))


def translate_set(item):
    if isinstance(item.a, Ref):
        if isinstance(item.b, Call):
            yield '0', push({
                **{'__arg{}'.format(i): x for i, x in enumerate(item.b.args)},
                **item.b.kwargs, RefExit: RefCode('2.exit')})
            yield '1', jmp(item.b.name)
            yield '2.exit', pop({item.a.name: Ref(RefReturn)})
        elif isinstance(item.b, Const):
            yield set({item.a.name: item.b})
        elif isinstance(item.b, Ref):
            yield set({item.a: item.b})
        else:
            raise ValueError(
                'Second operand of Set cannot be {}, must be Call, Const or Ref'.format(item.b.__class__.__name__))
    else:
        raise ValueError('First operand of Set cannot be {}, must be Ref'.format(item.a.__class__.__name__))


def consume_compiled(compiled_module):
    def sub_printout(item_name, item):
        if isinstance(item, GeneratorType):
            for i in item:
                if isinstance(i, tuple):
                    yield from sub_printout('.'.join([item_name, i[0]]), i[1])
                else:
                    yield from sub_printout(item_name, i)
        else:
            yield item_name, item

    for k, v in sorted(compiled_module.items()):
        for item in v:
            if isinstance(item, tuple):
                yield from sub_printout('.'.join([k, item[0]]), item[1])
            else:
                yield from sub_printout(k, item)


def printout(compiled_module):
    def sub_printout(item_name, item):
        if isinstance(item, GeneratorType):
            for i in item:
                if isinstance(i, tuple):
                    sub_printout('.'.join([item_name, i[0]]), i[1])
                else:
                    sub_printout(item_name, i)
        else:
            print(item_name.ljust(25), item)

    for k, v in sorted(compiled_module.items()):
        print()
        print('%{}'.format(k))
        for item in v:
            if isinstance(item, tuple):
                sub_printout('.'.join([k, item[0]]), item[1])
            else:
                sub_printout(k, item)


def link(compiled_module, symbol_table):
    pass


def main():
    module = Module("name",
                    a=Seq(
                        V('a').set(module_ext.function(a='BING', kw='ads')),
                        V('___tmp1').set(module_ext.get_accounts(a='ADWORDS', kw='ads')),
                    ),
                    b=Def([V('date')],
                          Seq(
                              V('__tmp0').set(module_ext.get_accounts(date=V('date')))
                          )),
                    c=Def([Ref('date')],
                          Seq(
                              V('__tmp0').set(module_ext.get_accounts(date=V('date'))),
                              If(
                                  Cond(V('___tmp0') == 5, Seq(
                                      V('ab').set(5)
                                  )),
                                  Cond(V('___tmp0') == 6, Seq(
                                      V('ab').set(5)
                                  )),
                                  Else(Seq(
                                      V('ab').set(99999),
                                      If(
                                          Cond(Compare(Ref('___tmp0'), Const(5)), Seq(
                                              V('ab').set(5)
                                          )),
                                          Cond(Compare(Ref('___tmp0'), Const(6)), Seq(
                                              V('ab').set(6)
                                          )),
                                          Else(Seq(
                                              V('ab').set(999)
                                          ))
                                      ),
                                  ))
                              ),

                              If(
                                  Cond(Compare(Ref('___tmp0'), Const(5)), Seq(
                                      Set(Ref('ab'), Const(5))
                                  )),
                                  Cond(Compare(Ref('___tmp0'), Const(6)), Seq(
                                      Set(Ref('ab'), Const(6))
                                  ))
                              )
                          )),
                    )

    compiled_module = compiler(module)


    # for item in consume_compiled(compiled_module):
    #     print(item)

    print('UNLINKED')
    printout(compiled_module)
    # print('LINKED')


if __name__ == '__main__':
    main()


def relative_path(a, b):
    r = list(a)
    b = list(b)

    while len(b):
        item = b[0]
        if item is '':
            r = r[:-1]
            b = b[1:]
        else:
            break

    if len(b):
        r[-1] = b[0]
        b = b[1:]

    return r + b
