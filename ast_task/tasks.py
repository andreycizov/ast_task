from asyncio import sleep

from ast_task.task import definition
import asyncio

"""
I would like to generate task function definitions
So that each function could be run on a separate node
The idea is that using the familiar python syntax for
Error handling/etc. is easier than just trying to use any of the
familiar frameworks for that reason.

We only need that for certain functions (e.g. task definitions are only the functions on which we should 'split')

We've got an AST and a way to store task call data in the database. It's arguments, exception and return value is stored in the database

Each subsequent call requires passing of variables only required for calling that function

In python, the context is passed automagically (we may then optimise which part of the context is going to be passed further to the function)

Every task receives arguments to it and it's follow-up tasks (success and failure)
"""

# How do we do If's?
# Comprehensions should be unwound
#

@definition
def helper(a):
    def mocker(d):
        return d

    if a == 'b':
        other(a)
    elif a == 'c':
        print('dd')
    elif a == 'c':
        print('cc')
    else:
        print('gg')
    return other(b)

    try:
        pass
    except:
        pass

@definition
async def other(*x, logger=None):
    return x


@definition
async def main(timeout_a, timeout_b=2, timeout_c=3, *args, **kwargs):
    print('a')
    try:
        (a, b) = await other('a'), await other('b')
        try:
            pass
        except Exception:
            pass
        c = await other(a, await other(b, 2*2, logger='asd', **kwargs))
        (a, b) = await sleep(timeout_a)
        await sleep(timeout_b)
    except Exception as e:
        print(e)
    except BaseException as e:
        print(e, e)
        await other('c')
        return timeout_a
    finally:
        await sleep(timeout_c)
