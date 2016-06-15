# - We need to keep the symbol table (correspondence between the initial location and the produced code)
# - a,b,c
from types import GeneratorType

from ast_task.dsl.language import Ref, Call, Const, Seq, Set, Module, Def, Extern, If, Cond, Compare, V, Else
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
            yield name + '.ep', jcmp('!=', cond.cond.a, cond.cond.b, RefCode(exit_name + '.ep'))
            yield name, translate_any(cond.body)
        else:
            yield name + '.ep', nop()
            yield name, translate_any(cond.body)

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
            yield '0', push({**item.b.kwargs, RefExit: RefCode('2.exit')})
            yield '1', jmp(item.b.name)
            yield '2.exit', pop({item.a.name: Ref(RefReturn)})
        elif isinstance(item.b, Const):
            yield set({item.a: item.b})
        elif isinstance(item.b, Ref):
            yield set({item.a: item.b})
        else:
            raise ValueError(
                'Second operand of Set cannot be {}, must be Call, Const or Ref'.format(item.b.__class__.__name__))
    else:
        raise ValueError('First operand of Set cannot be {}, must be Ref'.format(item.a.__class__.__name__))


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


    module_ext = \
        Module("moreover",
               function=Def(['name'], Seq()),
               get_accounts=Def(['date'], Seq()))

    module = Module("name",
                    a=Seq(
                        Set('___tmp0', Call(module_ext.function, a='BING', kw='ads')),
                        Set('___tmp1', Call(module_ext.get_accounts, a='ADWORDS', kw='ads')),
                    ),
                    b=Def([Ref('date')],
                          Seq(
                              Set(Ref('__tmp0'), Call(module_ext.get_accounts, date=V('date')))
                          )),
                    c=Def([Ref('date')],
                          Seq(
                              Set(Ref('__tmp0'), Call(module_ext.get_accounts, date=V('date'))),
                              If(
                                  Cond(Compare(Ref('___tmp0'), Const(5)), Seq(
                                      Set(Ref('ab'), Const(5))
                                  )),
                                  Cond(Compare(Ref('___tmp0'), Const(6)), Seq(
                                      Set(Ref('ab'), Const(6))
                                  )),
                                  Else(Seq(
                                      Set(Ref('ab'), Const(999)),
                                      If(
                                          Cond(Compare(Ref('___tmp0'), Const(5)), Seq(
                                              Set(Ref('ab'), Const(5))
                                          )),
                                          Cond(Compare(Ref('___tmp0'), Const(6)), Seq(
                                              Set(Ref('ab'), Const(6))
                                          )),
                                          Else(Seq(
                                              Set(Ref('ab'), Const(999))
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

    print('UNLINKED')
    printout(compiled_module)
    #print('LINKED')


if __name__ == '__main__':
    main()
