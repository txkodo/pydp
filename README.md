# pydp

pythonによるデータパック生成ツール


```python
from datapack import Command, Function, Datapack
from pathlib import Path

func = Function('minecraft','test')
func += Command.Say('hello world')

path = Path('C:.../saves/myworld/datapacks/mypack')

Datapack.export(path)
```