
# ファンクションを使う

Functionクラスでファンクションを新たに作ることができる。

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

[目次](../README.md)

[ブロックを使う](./block.md)