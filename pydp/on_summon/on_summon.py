"""
新しく生成されたエンティティに対して発動するファンクションタグ #minecraft:summon を追加する
summonコマンド呼び出し直後(コマンドによって生成されたエンティティ)と、毎チックのはじめ(自然スポーンしたエンティティ)に対し実行する
"""
from pydp.on_install import OnInstall
from pydp.datapack import Command, ICommand, Function, FunctionTag, Objective
from pydp.on_install.on_install import OnUninstall
from pydp.predicate import EntityScores
from pydp.selector import Selector

_obj = Objective('OnSummon')

OnSummon = FunctionTag('#minecraft:summon')
"""
召喚時トリガーのファンクションタグ
実行者は召喚されたエンティティ
"""

_general = Function()
OnSummon.append(_general)
_general += _obj.score(Selector.S()).Set(0)
_pred = EntityScores({_obj:(None,None)})

def accessor(cmd:ICommand):
  f = Function()
  f += cmd
  f += Selector.E(predicate={_pred:False}).As().At(Selector.S()) + OnSummon.call()
  return f.Call()

Command.Summon.default_accessor = accessor

_tick = Function()
FunctionTag.tick.append(_tick)

_tick += Selector.E(predicate={_pred:False}).As().At(Selector.S()) + OnSummon.call()

OnInstall += _obj.Add()
OnUninstall += _obj.Remove()
