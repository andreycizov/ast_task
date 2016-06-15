class DSL():
    pass


class For(DSL):
    def __init__(self, variable, op, body):
        self.variable = variable
        self.op = op
        self.body = body
        super().__init__()


class Map(DSL):
    def __init__(self, op, defn):
        self.op = op
        self.defn = defn
        super().__init__()


class Def(DSL):
    def __init__(self, arguments, body):
        self.arguments = arguments
        self.body = body


class Ref(DSL):
    def __init__(self, name):
        self.name = name

    def __str__(self, *args, **kwargs):
        return '@{}'.format(self.name)


class V(Ref):
    pass


class Const(DSL):
    def __init__(self, value):
        self.value = value

    def __str__(self, *args, **kwargs):
        return '#{}'.format(repr(self.value))


class Extern(Const):
    def __init__(self, value):
        super().__init__(value)

    def __str__(self, *args, **kwargs):
        return '~{}'.format(str(self.value))


class ModuleExtern(Extern):
    def __init__(self, module, item_name):
        super().__init__('.'.join([module.name, item_name]))


class If(DSL):
    def __init__(self, *conds):
        self.conds = conds

        super().__init__()


class Cond(DSL):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body
        super().__init__()


class Else(Cond):
    def __init__(self, body):
        super().__init__(None, body)


class Compare(DSL):
    def __init__(self, a, b):
        self.a = a
        self.b = b
        super().__init__()


class Call(DSL):
    def __init__(self, name, **kwargs):
        if isinstance(name, Extern):
            name = name
        else:
            raise ValueError('name must be Extern or str: {}'.format(name.__class__.__name__))

        self.name = name

        kwargs = {k: v if isinstance(v, Ref) else Const(v) for k, v in kwargs.items()}

        self.kwargs = kwargs

        super().__init__()


class Body(DSL):
    def __init__(self, *stmts):
        self.body = list(stmts)
        super().__init__()


class Seq(Body):
    pass


class Parallel(Body):
    pass


class Set(DSL):
    def __init__(self, a, b):
        if isinstance(a, str):
            a = Ref(a)
        elif isinstance(a, Ref):
            a = a
        else:
            raise ValueError('a must of str, Ref: {}'.format(a.__class__.__name__))

        self.a = a
        self.b = b


class Module(DSL):
    def __init__(self, name, **kwargs):
        assert isinstance(name, str)

        self.name = name
        self.names = kwargs
        super().__init__()

    def __getattr__(self, name):
        if name not in self.names:
            raise ValueError('{} does not exist in module {}'.format(name, self.name))
        return ModuleExtern(self, name)


# If(
#     Cond(Compare(Ref('__tmp123'), Ref('__tmp234')), Seq([])),
#     Cond(None, Seq([]))
# )

# Direct assignments assure that we're capable of translating the code directly to the
# underlining assembly

# Is a call supposed to raise the context?

# Module names
# How do we reference names? We still have got to

# We may "Call" names. But these names have to be translated both by

# Call is a jump with context push

"ast_task.sys.dsl.a"
"ast_task.sys.dsl.b"

# Initial step

# Set('a', Def(['date'], For('a', Call('get_accounts'), Seq([
#     # We suppose there's no reason to allow for dynamic
#     # function addressing (therefore all strings in Call are always references to the name table)
#
#     # On the other hand - it's hard to distinguish between variable lookups
#     # and string constants
#     Call('save_account_start_time', account='a'),
#     Call('load_account_into_ftp', account='a'),
#     Call('save_account_done_time', account='a')
# ]))))
#
# Map(Call('get_accounts', a='BING', kw='ads'), Def(Ref('x'), Seq([
#     Set('x', Call('save_account_start_time', account='x')),
#     Set('y', Call('load_account_into_ftp', account='x'))
# ])))

# Transform constant depending on their context
# No context overlays.

# For needs to extract a value returned
# If we're allowing for many threads, then we need ways of synchronisation

# Set(Ref('a'),
#     Def([Ref('date')],
#         Seq([
#             Set(Ref('__tmp0'), Call(Extern('get_accounts'))),
#             For(Ref('a'),
#                 Ref('__tmp0'), Seq([
#                     Call(Const('save_account_start_time'), date=Ref('date'), account=Ref('a')),
#                     Call(Const('load_account_into_ftp'), date=Ref('date'), account=Ref('a')),
#                     Call(Const('save_account_done_time'), date=Ref('date'), account=Ref('a'))
#                 ]))
#         ])
#         ))
#
# Map(Call(Const('get_accounts'), a=Const('BING'), kw=Const('ads')), Def(Ref('x'), Seq([
#     Set(Ref('x'), Call(Const('save_account_start_time'), account=Ref('x'))),
#     Set(Ref('y'), Call(Const('load_account_into_ftp'), account=Ref('x')))
# ])))
#
# # Transform calls to SSA form
#
#
#
# Seq([
#     Set(Ref('___tmp0'), Call('get_accounts', a='BING', kw='ads')),
#     Map(Ref('___tmp0'),
#         Def(Ref('x'), Seq([
#             Seq([
#                 Set(Ref('___tmp1'), Call('save_account_start_time', account=Ref('x'))),  # Singular operation
#                 Set(Ref('x'), Ref('___tmp1')),  # Singular operation
#             ]),
#             Seq([
#                 Set(Ref('___tmp2'), Call('load_account_into_ftp', account=Ref('x'))),
#                 Set(Ref('y'), Ref('___tmp2'))
#             ])
#         ])))
# ])

# We then may apply our translations to the full sub-trees, depending on the pattern matching algo



Module('GHosting', a=None, b=None)

# Function calls and optimisations to reduce the context size and RTT

# For by itself inherently requires fencing, if we are expected to
