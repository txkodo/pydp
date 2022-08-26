from abc import abstractmethod
from typing import Any
from datapack.datapack import IRecipe, Item
from datapack.mcpath import McPath

class RecipeItemGroup:
  """
  RecipeShaped専用のアイテムリスト

  与えられた枠内なら順不同にでよい場合に使う

  以下のようにすると石の上下左右をダイヤモンド/エメラルド/レッドストーン/ラピスラズリで囲むレシピができる

  宝石は上下左右の枠内ならどの順で並べても問題ないが必ずひとつづつ必要
  --------
  ```
  stone = ItemList.stone
  jewel = RecipeItemGroup([ItemList.diamond,ItemList.emerald,ItemList.redstone,ItemList.lapis_lazuli])

  RecipeShaped(
    [
      [None, jewel,None ],
      [jewel,stone,jewel],
      [None, jewel,None ]
    ],
    ItemList.ancient_debris
  )
  ```
  """
  def __init__(self,items:list[Item]) -> None:
    self._items = items
  
  def export_list(self):
    result:list[dict[str, str]] = []
    for i in self._items:
      if i.id.istag:
        result.append({'tag':i.id.str_hashless()})
      else:
        result.append({'item':i.id.str_hashless()})
    return result

class RecipeShaped(IRecipe):
  def __init__(self,
    pattern:list[list[Item|RecipeItemGroup|None]],
    result:Item,
    count:int|None=None,
    group:str|None=None,
    path:str|McPath|None=None
    ) -> None:
    self._pattern = pattern
    self._count = count
    self._result = result
    super().__init__(path,group)

  @abstractmethod
  def export_dict(self) -> dict[str,Any]:
    ids = list('876543210')
    item_str_map:dict[Item|RecipeItemGroup,str] = {}
    str_item_map:dict[str,dict[str,str]|list[dict[str,str]]] = {}

    def convert(item:Item|RecipeItemGroup|None) -> str:
      if item in item_str_map:
        return item_str_map[item]
      if item is None:
        return ' '
      id = ids.pop(-1)
      match item:
        case Item():
          if item.id.istag:
            str_item_map[id] = {'tag':item.id.str_hashless()}
          else:
            str_item_map[id] = {'item':item.id.str_hashless()}
        case RecipeItemGroup():
          str_item_map[id] = item.export_list()
      item_str_map[item] = id
      return id
    
    pattern = [''.join(convert(item) for item in l) for l in self._pattern]

    r:dict[str,str|int] = {'item':self._result.id.str}
    if self._count is not None: r['count'] = self._count

    result = {
      'pattern':pattern,
      'key':str_item_map,
      'result':r
    }
    return result
