# pydp

pythonによるデータパック生成ツール


```python
from datapack.datapack import MC, Function, DataPack
from pathlib import Path

func = Function('minecraft','test')
func += MC.Say('hello world')

path = Path('C:.../saves/myworld/datapacks/mypack')
DataPack.export(path)
```