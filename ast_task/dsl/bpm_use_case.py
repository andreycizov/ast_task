from ast_task.dsl.compiler import compiler, printout
from ast_task.dsl.language import Module, Def, Seq, Map, V

bpm = \
    Module("bpmms_api_accounts",
           account_list=Def([], Seq(

           )),
           account_load_ftp=Def([V('account')], Seq(

           ))
           )

# We need support for lists as context data
# We could easily support firing up per-account processes directly from the database
# For that we would need to load account lists and then apply functions to them

connection = Module(
    'connexion',
    load_all_accounts=Map(bpm.account_list(priority=0),
        Def([V('account')], Seq(
            bpm.account_load_ftp(V('account'))
        ))))


def main():
    compiled_module = compiler(connection)

    # for item in consume_compiled(compiled_module):
    #     print(item)

    print('UNLINKED')
    printout(compiled_module)
    # print('LINKED')


if __name__ == '__main__':
    main()
