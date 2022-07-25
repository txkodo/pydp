
# コマンドを使う

コマンドはCommandクラスを使って生成する。

いくつかのコマンドはCommandクラスのstaticmethodとして定義してある。

使いたいコマンドがstaticmethodにない場合はCommandインスタンスを直接生成する。

`Function += Command`とすることでファンクションにコマンドを追加できる

コマンドは`export()`メソッドを使うことで文字列化できる

```python
from datapack import Command, Function

func = Function('minecraft','test')

# 組み込み済みのコマンド
command = Command.Say("hello world1")
print(command.export()) # -> say hello world1
func += command

# コマンドの自己定義
command = Command("say hello world2")
print(command.export()) # -> say hello world2
func += command

```