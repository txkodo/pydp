# pydp

pythonによるデータパック生成ツール

詳しくは[Wiki](https://github.com/txkodo/pydp/wiki)参照

### 動作バージョン

python 3.10+

minecraft 1.19+


# 基本の使い方

以下のようにすることでdatapackが生成できる

```python
from datapack import Command, Function, Datapack

func = Function('minecraft','test')
func += Command.Say('hello world')

path = '.../saves/myworld/datapacks/mypack'

Datapack.export(path)
```

#### 生成結果

###### .../saves/myworld/datapacks/mypack/pack.mcmeta

```json
{
  "pack":{
    "pack_format":9,
    "description":"pydp auto generated datapack"
    }
}
```
###### .../saves/myworld/datapacks/mypack/data/minecraft/functions/test.mcfunction

```mcfunction
say hello world
```

