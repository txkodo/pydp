# pydp

pythonによるデータパック生成ツール


```python
from datapack import Command, Function, Datapack

func = Function('minecraft','test')
func += Command.Say('hello world')

path = 'C:.../saves/myworld/datapacks/mypack'

Datapack.export(path)
```