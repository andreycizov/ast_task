class Command():
    opcode = None

    def __str__(self, *args, **kwargs):
        return '{opcode}'.format(opcode=self.opcode)


class nop(Command):
    opcode = 'NOP'

    def __init__(self):
        super().__init__()


class call(Command):
    opcode = 'CALL'

    def __init__(self, what, **kwargs):
        self.what = what
        super().__init__()

    def __str__(self, *args, **kwargs):
        return '{} {}->{} ({})'.format(super().__str__(*args, **kwargs), self.what, self.to_return,
                                       ','.join(['='.join((k, v)) for k, v in self.kwargs.items()]))


class jmp(Command):
    opcode = 'JMP'

    def __init__(self, to):
        self.to = to
        super().__init__()

    def __str__(self, *args, **kwargs):
        return super().__str__(*args, **kwargs) + ' ' + str(self.to)


class jnz(jmp):
    opcode = 'JNZ'

    def __init__(self, test, to):
        self.test = test
        super().__init__(to)

    def __str__(self, *args, **kwargs):
        return '{} {} {}'.format(super().__str__(*args, **kwargs), self.test, self.to, self)


class jcmp(jmp):
    opcode = 'JCMP'

    def __init__(self, fn, a, b, to):
        self.fn = fn
        self.a = a
        self.b = b
        super().__init__(to)

    def __str__(self, *args, **kwargs):
        return '{} {}{}{} {}'.format(self.opcode, self.a, self.fn, self.b, self.to, self.to)


class jeq(jmp):
    opcode = 'JEQ'

    def __init__(self, a, b, to):
        self.a = a
        self.b = b
        super().__init__(to)

    def __str__(self, *args, **kwargs):
        return '{} {} {} {}'.format(self.opcode, self.a, self.b, self.to, self.to)


class CtxCommand(Command):
    def __init__(self, kwargs):
        self.kwargs = kwargs
        super().__init__()

    def __str__(self, *args, **kwargs):
        return super().__str__(*args, **kwargs) + ' ' + ','.join(
            ['='.join([str(a), str(b)]) for a, b in self.kwargs.items()])


class set(CtxCommand):
    opcode = 'SET'


class pop(CtxCommand):
    opcode = 'POP'


class push(CtxCommand):
    opcode = 'PUSH'


class fork(jmp):
    opcode = 'FORK'
