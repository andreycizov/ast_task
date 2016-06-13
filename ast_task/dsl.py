class DSL():
    pass


class For(DSL):
    def __init__(self, variable, op, body):
        self.variable = variable
        self.op = op
        self.body = body
        super().__init__()


class Def(DSL):
    def __init__(self, arguments, seq):
        self.arguments = arguments


class Ref(DSL):
    def __init__(self, name):
        self.name = name


class Call(DSL):
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        super().__init__()


class Seq(DSL):
    def __init__(self, body):
        self.body = body
        super().__init__()


class Parallel(DSL): # Parallel(..., ...) -> (..., ...)
    def __init__(self, what, body):
        self.what = what
        self.body = body


# For by itself inherently requires fencing, if we are expected to
Def(Ref('date'), For(Ref('a'), Call('get_accounts'), Seq([
    Call('save_account_start_time', account=Ref('a')),
    Call('load_account_into_ftp', account=Ref('a')),
    Call('save_account_done_time', account=Ref('a'))
])))
