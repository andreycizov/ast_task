from asyncio import sleep


from ast_task.runner import fire_chain, subsequent, exception




"""
exit(timeout_c):
 await sleep(timeout_c)

failure_cases(e):
 case BaseException:
  print(e)
 case FollowerException:
  print('no followers')
 exit(timeout_c)

print('a'):
case other(c): X
  -> Success(d)
   case sleep(timeout_a):
    -> Success(d):
      case sleep(timeout_b):
       -> Success(d)
        exit(timeout_c)
       -> Failure(e):
        failure(e)
    -> Failure(e):
      failure(e)
   c = subsequent(main_3)
   (a, b) = await timeout(timeout_b)
  -> Failure(e)
   failure_cases(e)

main_start(timeout_a, timeout_b=2, timeout_c=3):
 print('a')

then! tasks need to know their context and need to know which task follows them

Two types of tasks:
 blocks pass context,
 functions don't

"""


async def other_call(ctx):
    return ctx['x']


async def main_exc(ctx, e):
    if isinstance(e, Exception):
        print(e)
    else:
        raise e


async def main_fin(ctx):
    await sleep(ctx['timeout_c'])


async def main_2(ctx):
    (ctx['a'], ctx['b']) = await sleep(ctx['timeout_a'])
    await sleep(ctx['timeout_b'])


async def main_1(ctx):
    print('a')


main_fin = (main_fin, (None, None))
main_exc = (main_exc, (('curr', main_fin), None))
main_main_2 = (main_2, (('curr', main_fin), ('curr', main_exc)))
task_other = (other_call, (('pop', main_main_2, dict(c='x')), ('pop', main_fin)))
task_main_1 = (main_1, (('push', task_other, dict(x='timeout_a')), None))


# def followed(exc, ok):
#     return x
#
# @followed(None, None)
# async def called_by_main____other_1(x):
#     return x
#
# @followed(None, None)
# async def main_catch(timeout_a, timeout_b, timeout_c, e):
#     if isinstance(e, Exception):
#         print(e)
#     return timeout_a, timeout_b, timeout_c
#
# @followed(None, None)
# async def main_finally(timeout_a, timeout_b, timeout_c):
#     await sleep(timeout_c)
#     return timeout_a, timeout_b, timeout_c
#
# @followed(main_catch, main_finally)
# async def main_3(timeout_a, timeout_b, timeout_c, c):
#     (a, b) = await sleep(timeout_a)
#     await sleep(timeout_b)
#     return timeout_a, timeout_b, timeout_c, c, a, b
#
#
# @followed(None, main_2)
# async def main_1(timeout_a, timeout_b, timeout_c):
#     print('a')
#     return timeout_a, timeout_b, timeout_c




