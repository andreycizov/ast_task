class ContextDict(object):
    def __init__(self, initial=None):
        if initial:
            self._dict = [dict(initial)]
        else:
            self._dict = [dict()]

    def push(self, initial=None):
        if initial:
            self._dict.append(dict(initial))
        else:
            self._dict.append(dict())

    def pop(self):
        self._dict.pop()
        if len(self._dict) == 0:
            raise OverflowError('Context underflow')

    def __setitem__(self, key, item):
        self._dict[-1][key] = item

    def __getitem__(self, key):
        for d in self._dict:
            if key in d:
                return d[key]
        raise KeyError(key)



