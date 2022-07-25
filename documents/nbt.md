
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

# storage foo:bar {自動生成id} (Compound型)
# 自動生成idの例: ":FgE9vZym"
c2 = storage[Compound] 


# storage foo:bar C1.I3 (Int型)
i3 = c1['I3',Int]

# storage foo:bar L1 (List[Int]型)
l1 = storage['L1',List[Int]]

# storage foo:bar L1[0] (Int型)
i4 = l1[0]

# storage foo:bar L2 (List[Compound]型)
l2 = storage['L2',List[Compound]]

# storage foo:bar L2[] (Compound型)
c3 = l2.all()

# storage foo:bar L2[{a:1b}] (Compound型)
c4 = l2.filterAll(Compound({'a':Byte(1)}))
```

[目次](../README.md)

[ファンクションを使う](./function.md)
