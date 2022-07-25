
# executeを使う

サブコマンドはメソッドチェーンまたは'+'で連結できる

`サブコマンド.run(コマンド)` または `サブコマンド + コマンド` とすることで`execute ... run ...`ができる

サブコマンド単体ではコマンドとしては使用できないが、
ConditionSubCommandクラス(execute if/unless のためのクラス)のみ単体でコマンドとして使用できる

サブコマンドと結合したコマンドも`export()`メソッドを使うことで文字列化できる

```python
from datapack import Command, Execute, Function

func = Function('minecraft','test')

# 下の二つは等価
execute = Execute.In('minecraft:nether').Align('xyz').Run(Command.Say('hello world'))
execute = Execute.In('minecraft:nether') + Execute.Align('xyz') + Command.Say('hello world')

print(execute.export()) # -> execute in minecraft:nether align xyz run say hello world

func += execute

```

[目次](../README.md)

[nbtを使う](./nbt.md)