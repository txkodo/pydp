# pydp

pythonによるデータパック生成ツール

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

# nbtを使う

以下nbtの型定義とnbt関連のコマンド生成の例

```python
from datapack import Byte, Command, Compound, Int, List, StorageNbt

# ストレージを定義
storage = StorageNbt('foo:bar')
# BlockNbt / EntityNbt もある

# storage foo:bar I1 をInt型として定義
i1 = storage['I1',Int]

# Int型の値を作成
int_value = Int(100)

# I1を100(Int型)にする
i1.set(int_value).export()
# -> data modify storage foo:bar I1 set value 100

# storage foo:bar I2 をInt型として定義
i2 = storage['I1',Int]

# I2をI1にする
# >>> data modify storage foo:bar I2 set from storage foo:bar I1
i2.set(i1)

# say hello world の結果を1倍してI2に(Int型として)格納する
# >>> execute store result storage foo:bar I2 int 1 run say hello world
i2.storeResult(1) + Command.Say('hello world')

# I2が100なら...
# >>> execute if data storage foo:bar {I2:100} run say foo:bar I2 is 100.
i2.isMatch(Int(100)) + Command.Say("foo:bar I2 is 100.")

# I2が100でないなら...
# >>> execute unless data storage foo:bar {I2:100} run say foo:bar I2 is not 100.
i2.notMatch(Int(100)) + Command.Say("foo:bar I2 is not 100.")

# storage foo:bar C1 (Compound型)
c1 = storage['C1',Compound]
c1 = storage['C1'] # 上と等価

# storage foo:bar C1.I3 (Int型)
i3 = c1['I3',Int]

# storage foo:bar L1 (List[Int]型)
l1 = storage['L1',List[Int]]

# storage foo:bar L1[0] (Int型)
i4 = l1[0]

# storage foo:bar L2 (List[Compound]型)
l2 = storage['L2',List[Compound]]

# storage foo:bar L2[] (Compound型)
c2 = l2.all()

# storage foo:bar L2[{a:1b}] (Compound型)
c3 = l2.filterAll(Compound({'a':Byte(1)}))
```

# ファンクションを作る

上の例でも使用したように、Functionクラスでファンクションを新たに作ることができる。

Datapack.export() を実行することで`.mcfunction`が生成される。

```python
from datapack import Command, Datapack, Function

# ファンクション minecraft:main を定義
main_func = Function('minecraft','main')

main_func += Command.Say('this is main')

# ファンクション foo:bar/buz を定義
sub_func = Function('foo','bar/buz')

# >>> function foo:bar/buz
main_func += sub_func.call()

# >>> schedule function foo:bar/buz 1t
main_func += sub_func.schedule(1)

# >>> schedule clear foo:bar/buz
main_func += sub_func.clear_schedule()

# 匿名ファンクションを定義
# ファンクション名はDatapack.expoort()時に自動的に決定される
# デフォルトだと次のようになる pydp:1bka4qp9h3syum9n6oi3o8j5
anonymous_func = Function()

anonymous_func += Command.Say('this is anonymous')

# >>> function {namespace}:{path}
main_func += anonymous_func.call()

# 匿名ファンクションの名前空間と生成先ディレクトリを指定
Datapack.default_namespace = "temp"
Datapack.default_folder = "folder/"

# anonymous_funcの生成先が次のようになる temp:folder/1bka4qp9h3syum9n6oi3o8j5


# データパックを指定した場所に作成
# Datapack.exportの引数でも匿名ファンクションの名前空間と生成先ディレクトリが指定できる
path = '.../saves/myworld/datapacks/mypack'
Datapack.export(path)
```

#### ファイル生成の最適化
データパック生成時に冗長なファンクションのネストを解消する最適化が行われる。
結果として匿名ファンクションが出力されずに、その内容が呼び出し元に直接埋め込まれることがある。

※ 名前の付いたファンクションは必ず生成される。

この処理の結果として匿名ファンクションの実行結果を`store result`したときの挙動が変わることがある。
そのため、匿名ファンクション呼び出しの結果をstoreすることは推奨されない。

上記の例だと`anonymous_func`は出力されず、その内容が下記のように`main_func`に埋め込まれる。

###### minecraft:main

```mcfunction
say this is main
function foo:bar/buz
schedule function foo:bar/buz 1t
schedule clear foo:bar/buz
say this is anonymous
```

# Block

# Item

# Position

# EntitySelector

# ScoreBoard

# JsonText

# データパックライブラリの定義
