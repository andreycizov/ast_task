- A reeeealy simple DSL to define tasks
- A Python API to define tasks for task running servers
 * Python logging module hijacks in order to get output from them Jenkins-like
 + Some of these APIs may be run in priveleged mode in order to manage API servers
 + I guess it's mostly in the DSL part of the config (where the code is located)
- All of that is part of the infrastructure run in Docker
 + Python API servers
 + System-specific code: execution of the instructions
 + 

+ Task-running microcode is deployed to the API servers in order to support versioning
  - We've got to realise that this is a crucial step that otherwise would be implemented as just direct task calls to the API servers
+ Tasks are supposed to be idempotent
+ Tasks are directly used to manipulate database data in order to change state in the UI

CPU:
- RabbitMQ-backed: Consumers,Producers with ack=True
 + What if the consumer is killed? We need a database for that
- Instructions: for the first versions instructions are sent with the queue
- Registers: could be sent as part of the messages

- Server system registers
 * Start listening on an IP address
    

JT's sake

- Object Table <- Traffic.select(api_name='BING', accountid='2423432').groupby('api_name', 'accountid').aggregate( dict(cpc='sum', latestcpc='list')).sort(accountid)
- Object Table.write('filename_obj.txt')



