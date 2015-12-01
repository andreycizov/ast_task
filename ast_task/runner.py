def fire_chain(x):
    x()

def subsequent(*x):
    return x

def exception(*x):
    return x