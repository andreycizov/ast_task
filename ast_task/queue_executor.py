# Take a task from RabbitMQ
# Execute it
# Fuck over.

# - Receive a message with a Redis ID
# - Run the task
# - Create a subsequent task in Redis
# - Create a subsequent task in Redis
# - Mark this task as completed in Redis <- stop this task from being run again
# - Publish a subsequent task in MQ
# - Publish a subsequent task in MQ
#
#
# - Persist a message in Redis
import json
import logging
import time
import uuid

import stomp

logger = logging.getLogger(__name__)


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

    def __init__(self, what, to_return):
        self.what = what
        self.to_return = to_return
        super().__init__()

    def __str__(self, *args, **kwargs):
        return '{} {}->{}'.format(super().__str__(*args, **kwargs), self.what, self.to_return)


class jnz(Command):
    opcode = 'JNZ'

    def __init__(self, what, to_if_true, to_if_false):
        self.what = what
        self.to_if_true = to_if_true
        self.to_if_false = to_if_false
        super().__init__()

    def __str__(self, *args, **kwargs):
        return '{} {}?{}:{}'.format(super().__str__(*args, **kwargs), self.what, self.to_if_true, self.to_if_false)




class jmp(Command):
    opcode = 'JMP'

    def __init__(self, to):
        self.to = to
        super().__init__()


PYTHON_CALLABLES = {
    'queue.test.python_callable': lambda: print('/queue/test/python_callable'),
    'queue.test.python_callable_exit': lambda: print('/queue/test/python_callable_exit'),
    'queue.test.python_callable_false': lambda: print('/queue/test/python_callable_false')
}

# create an ID of a current fence
# try to lock a lock with this ID
# Have an object with all IDs

# A: UPDATE locks SET done = True WHERE id = lock_id
# (a,b,c,d,e,f,g,h)
# (lock_id_a, lock_id_b, lock_id_c, ...)
# (True, False, True, ...)

# v0.1alpha: we need to be able to decide upfront, to which queue the command should be added

# Program memory directly represents the queues where we are supposed to send the messages
# The queue runners are essentially simple CPUs with added capabilities via run command

# Passing arguments to the subprograms
# These subprograms are deployed to Redis later
MEMORY_PROGRAM = {
    'deploy.python': None,  # deployment part of the executor

    'python.v3.bpmms.python_callable': call('python_callable', ''),  # supposed to be run by a python executor

    'test.a': call('queue.test.python_callable', 'test.b'),  # system task runner
    'test.b': jnz('queue.test.python_callable_false', 'test.c', 'test.b1'),
    'test.b1': call('queue.test.python_callable_exit', 'test.b2'),
    'test.b2': nop(),
    'test.d': jmp(['queue.test.a', 'queue.test.a', 'test.a'])
}


def main():
    subscriber_id = uuid.uuid4()
    subscriber_local_id = uuid.uuid4()

    class MyListener(stomp.ConnectionListener):
        def on_error(self, headers, message):
            print('received an error "%s"' % message)

        def on_message(self, headers, message):
            tid = conn.begin()
            try:
                msg = json.loads(message)

                conn.ack(headers['message-id'], subscriber_id, transaction=tid)

                to_exec = MEMORY_PROGRAM[msg['$ip']]

                print('[{2}] @{4}: {3} {1}'.format(headers, message, time.time(), to_exec, msg['$ip']))

                if isinstance(to_exec, nop):
                    pass
                elif isinstance(to_exec, call):
                    PYTHON_CALLABLES[to_exec.what]()
                    conn.send(to_exec.to_return, json.dumps({**msg, '$ip': to_exec.to_return}), transaction=tid)
                elif isinstance(to_exec, jnz):
                    if PYTHON_CALLABLES[to_exec.what]():
                        conn.send(to_exec.to_if_true, json.dumps({**msg, '$ip': to_exec.to_if_true}), transaction=tid)
                    else:
                        conn.send(to_exec.to_if_false, json.dumps({**msg, '$ip': to_exec.to_if_false}), transaction=tid)
                elif isinstance(to_exec, jmp):
                    for item in to_exec.to:
                        conn.send(item, json.dumps({**msg, '$ip': item}), transaction=tid)
                else:
                    raise ValueError('Unknown Command')

            except:
                # conn.ack(headers['message-id'], subscriber_id, transaction=tid)
                # conn.commit(tid)
                conn.nack(headers['message-id'], subscriber_id, transaction=tid)
                conn.abort(tid)
                logger.exception('Raised')
            else:
                conn.commit(tid)

    conn = stomp.Connection()
    conn.set_listener('', MyListener())
    conn.start()
    print('Connecting to ActiveMQ')
    conn.connect('admin', 'admin', wait=True)

    conn.subscribe(destination='test.*', id=subscriber_id, ack='client-individual')
    conn.subscribe(destination='local.{}'.format(subscriber_local_id), id=subscriber_local_id, ack='client-individual')
    # conn.send(body='a', destination='/queue/test')
    # conn.

    time.sleep(10000)

    conn.disconnect()


def main_pub():
    conn = stomp.Connection()
    conn.start()
    print('Connecting to ActiveMQ')
    conn.connect('admin', 'admin', wait=True)

    while True:
        msg = input().split(' ')
        command, args = msg[0], msg[1:]
        args = dict([x.split('=') for x in args])

        message = {
            **args,
            **{'$ip': command}
        }

        conn.send(body=json.dumps(message), destination=command)

    conn.disconnect()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'publish':
        main_pub()
    else:
        main()
