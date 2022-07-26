from __future__ import annotations
from abc import ABCMeta, abstractmethod
from copy import copy
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Literal, Protocol, TypeAlias, TypeGuard, TypeVar, final, get_args, overload, Union, runtime_checkable
from typing_extensions import Self
from enum import Enum, auto
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
from uuid import UUID, uuid4

from datapack.mcpath import McPath
from datapack.util import float_to_str, gen_id





class McUUID:
  __slots__ = ('_bytes')

  def __init__(self,arg:str|tuple[int,int,int,int]|None=None) -> None:
    match arg:
      case str():
        if '-' in arg:
          arg = ''.join( b.zfill(l) for b,l in zip(arg.split('-'),(8,4,4,4,12)))
        uuid = UUID(arg)
      case tuple():
        num = 0
        for i in arg:
          if not 0 <= i < 2**32:
            raise ValueError('ints items must be in range 0..2**32-1')
          num = (num << 32) + i
        uuid = UUID(int=num)
      case None:
        uuid = uuid4()
    self._bytes = uuid.bytes

  def __hash__(self) -> int:
    return hash(self._bytes)

  def __eq__(self, __o: object) -> bool:
    if isinstance(__o,McUUID):
      return self._bytes == __o._bytes
    return False

  def __str__(self):
    bs = self._bytes
    i = 0
    result:list[str] = []
    for j in (4,2,2,2,6):
      result.append(f'{int.from_bytes(bs[i:i+j],"big"):x}')
      i += j
    return '-'.join(result)

  def intArray(self):
    bs = self._bytes
    ints = [Int(int.from_bytes(bs[i:i+4],"big",signed=True)) for i in range(0,16,4)]
    return IntArray(ints)






class Position:
  @dataclass
  class IPosition:
    x:float
    y:float
    z:float

    @classmethod
    @abstractmethod
    def prefix(cls) -> str:
      pass

    def __str__(self):
      return self.expression()

    @classmethod
    def origin(cls):
      return cls(0,0,0)
    
    def tuple(self):
      return (self.x,self.y,self.z)

    def expression(self):
      def expr(value:float):
        v = "" if self.prefix() and value == 0 else str(value)
        return self.prefix() + v
      return f'{expr(self.x)} {expr(self.y)} {expr(self.z)}'

    def Positioned(self):
      return Execute.Positioned(self)

    def IfBlock(self,block:Block):
      return Execute.IfBlock(self,block)

    def UnlessBlock(self,block:Block):
      return Execute.UnlessBlock(self,block)
    
    def Facing(self):
      return Execute.Facing(self)

    def Nbt(self):
      return BlockNbt(self)

    def __add__(self,diff:tuple[float,float,float]):
      return self.__class__(self.x+diff[0],self.y+diff[1],self.z+diff[2])

    def __iadd__(self,diff:tuple[float,float,float]):
      self.x+=diff[0]
      self.y+=diff[1]
      self.z+=diff[2]
      return self

    def __sub__(self,diff:tuple[float,float,float]):
      return self.__class__(self.x-diff[0],self.y-diff[1],self.z-diff[2])

    def __isub__(self,diff:tuple[float,float,float]):
      self.x-=diff[0]
      self.y-=diff[1]
      self.z-=diff[2]
      return self

    def __neg__(self):
      return self.__class__(-self.x,-self.y,-self.z)

  @dataclass
  class Local(IPosition):
    """^x ^y ^z"""
    @classmethod
    def prefix(cls) -> str:
      return "^"

  @dataclass
  class World(IPosition):
    """x y z"""
    @classmethod
    def prefix(cls) -> str:
      return ""

  @dataclass
  class Relative(IPosition):
    """~x ~y ~z"""
    @classmethod
    def prefix(cls) -> str:
      return "~"

class ISubCommandSegment(metaclass=ABCMeta):
  def __init__(self) -> None:
    self.accessor:None|Callable[[ICommand],ICommand] = None

  def export_subcommand(self) -> str:
    raise NotImplementedError

  def copy_without_accessor(self):
    result = copy(self)
    result.accessor = None
    return result

class IStoreSubCommandSegment(ISubCommandSegment):
  _store_nbt:Byte

  @classmethod
  @property
  def store_nbt(cls) -> Byte:
    if not hasattr(cls,'_store_nbt'):
      cls._store_nbt = _pydp_storage['store',Byte]
    return cls._store_nbt

  def __init__(self,is_result:bool) -> None:
    super().__init__()
    self.is_result = is_result

  @property
  def prefix(self) -> str:
    return 'store result ' if self.is_result else 'store success '

class IConditionSubCommandSegment(ISubCommandSegment):
  def __init__(self,condition:bool) -> None:
    super().__init__()
    self.condition = condition
  
  def invert(self):
    result = copy(self)
    result.condition = not self.condition
    return result
  
  def __inv__(self):
    return self.invert()

  @property
  def prefix(self) -> str:
    return 'if ' if self.condition else 'unless '

class SubCommandSegment:
  class As(ISubCommandSegment):
    def __init__(self,entity:ISelector) -> None:
      super().__init__()
      self.entity = entity

    def export_subcommand(self) -> str:
      return "as " + self.entity.expression()

  class At(ISubCommandSegment):
    def __init__(self,entity:ISelector) -> None:
      super().__init__()
      self.entity = entity
    
    def export_subcommand(self) -> str:
      return "at " + self.entity.expression()

  class Positioned(ISubCommandSegment):
    def __init__(self,pos:Position.IPosition) -> None:
      super().__init__()
      self.pos = pos
    
    def export_subcommand(self) -> str:
      return f"positioned {self.pos.expression()}"
    
    class As(ISubCommandSegment):
      def __init__(self,entity:ISelector) -> None:
        super().__init__()
        self.entity = entity

      def export_subcommand(self) -> str:
        return "positioned as " + self.entity.expression()

  class Align(ISubCommandSegment):
    def __init__(self,axes:Literal['x','y','z','xy','yz','xz','xyz']) -> None:
      super().__init__()
      self.axes = axes
    
    def export_subcommand(self) -> str:
      return "align " + self.axes

  class Facing(ISubCommandSegment):
    def __init__(self,pos:Position.IPosition) -> None:
      super().__init__()
      self.pos = pos
    
    def export_subcommand(self) -> str:
      return f"facing {self.pos.expression()}"
    
    class Entity(ISubCommandSegment):
      def __init__(self,entity:ISelector) -> None:
        super().__init__()
        self.entity = entity

      def export_subcommand(self) -> str:
        return "facing entity " + self.entity.expression()

  class Rotated(ISubCommandSegment):
    def __init__(self,yaw:float,pitch:float) -> None:
      super().__init__()
      self.yaw = yaw
      self.pitch = pitch
    
    def export_subcommand(self) -> str:
      return f'rotated {float_to_str(self.yaw)} {float_to_str(self.pitch)}'

    class As(ISubCommandSegment):
      def __init__(self,entity:ISelector) -> None:
        super().__init__()
        self.entity = entity

      def export_subcommand(self) -> str:
        return "rotated as  " + self.entity.expression()

  class In(ISubCommandSegment):
    def __init__(self,dimension:McPath|str) -> None:
      super().__init__()
      self.dimension = McPath(dimension)
      assert not self.dimension.istag

    def export_subcommand(self) -> str:
      return f'in ' + self.dimension.str

  class Anchored(ISubCommandSegment):
    def __init__(self,anchor:Literal['feet','eyes']) -> None:
      super().__init__()
      self.anchor = anchor

    def export_subcommand(self) -> str:
      return f'anchored ' + self.anchor

  class Condition:
    class Nbt(IConditionSubCommandSegment):
      @classmethod
      def If(cls,nbt:INbt):
        return cls(nbt,True)

      @classmethod
      def Unless(cls,nbt:INbt):
        return cls(nbt,False)

      def __init__(self,nbt:INbt,condition:bool) -> None:
        super().__init__(condition)
        self.nbt = nbt

      def export_subcommand(self) -> str:
        return super().prefix + 'data ' + str(self.nbt.path)

      class Matches(IConditionSubCommandSegment):
        @classmethod
        def If(cls,nbt:NBT,value:Value[NBT]):
          return cls(nbt,value,True)

        @classmethod
        def Unless(cls,nbt:NBT,value:Value[NBT]):
          return cls(nbt,value,False)

        def __init__(self,nbt:NBT,value:Value[NBT],condition:bool) -> None:
          super().__init__(condition)
          self.nbt = nbt
          self.value = value

        def export_subcommand(self) -> str:
          return super().prefix + 'data ' + str(self.nbt.path.match(self.value))


    class Entity(IConditionSubCommandSegment):
      @classmethod
      def If(cls,entity:ISelector):
        return cls(entity,True)

      @classmethod
      def Unless(cls,entity:ISelector):
        return cls(entity,True)

      def __init__(self,entity:ISelector,condition:bool) -> None:
        super().__init__(condition)
        self.entity = entity
      
      def export_subcommand(self) -> str:
        return super().prefix + "entity " + self.entity.expression()

    class Block(IConditionSubCommandSegment):
      @classmethod
      def If(cls,pos:Position.IPosition,block:Block):
        return cls(pos,block,True)

      @classmethod
      def Unless(cls,pos:Position.IPosition,block:Block):
        return cls(pos,block,True)

      def __init__(self,pos:Position.IPosition,block:Block,condition:bool) -> None:
        super().__init__(condition)
        self.pos = pos
        self.block = block
      
      def export_subcommand(self) -> str:
        return super().prefix + f'block {self.pos.expression()} {self.block.expression()}'

    class Blocks(IConditionSubCommandSegment):
      @classmethod
      def If(cls,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
        return cls(begin,end,destination,method,True)

      @classmethod
      def Unless(cls,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
        return cls(begin,end,destination,method,True)

      def __init__(self,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked'],condition:bool) -> None:
        super().__init__(condition)
        self.begin = begin
        self.end = end
        self.destination = destination
        self.method = method
      
      def export_subcommand(self) -> str:
        return super().prefix + f'blocks {self.begin.expression()} {self.end.expression()} {self.destination.expression()} {self.method}'

    class Score(IConditionSubCommandSegment):
      @classmethod
      def If(cls,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
        return cls(target,source,operator,True)

      @classmethod
      def Unless(cls,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
        return cls(target,source,operator,True)

      def __init__(self,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>'],condition:bool) -> None:
        super().__init__(condition)
        self.target = target
        self.source = source
        self.operator = operator
      
      def export_subcommand(self) -> str:
        return super().prefix + f'score {self.target.expression()} {self.operator} {self.source.expression()}'

      class Matches(IConditionSubCommandSegment):
        @classmethod
        def If(cls,target:Scoreboard,start:int,stop:int|None=None):
          return cls(target,start,stop,True)

        @classmethod
        def Unless(cls,target:Scoreboard,start:int,stop:int|None=None):
          return cls(target,start,stop,True)

        def __init__(self,target:Scoreboard,start:int,stop:int|None,condition:bool) -> None:
          super().__init__(condition)
          self.target = target
          self.start = start
          self.stop = stop

        def export_subcommand(self) -> str:
          if self.stop is None:
            return super().prefix + f'score {self.target.expression()} matches {self.start}'
          else:
            return super().prefix + f'score {self.target.expression()} matches {self.start}..{self.stop}'
  
  class Store:
    class Nbt(IStoreSubCommandSegment):
      @classmethod
      def Result(cls,nbt:INum[Any],scale:float=1):
        return cls(nbt,scale,True)

      @classmethod
      def Success(cls,nbt:INum[Any],scale:float=1):
        return cls(nbt,scale,False)

      def __init__(self,nbt:INum[Any],scale:float,is_result:bool) -> None:
        super().__init__(is_result)
        self.nbt = nbt
        self.scale = scale

      def export_subcommand(self) -> str:
        return super().prefix + f'{self.nbt.path} {self.nbt.mode} {float_to_str(self.scale)}'

    class Score(IStoreSubCommandSegment):
      @classmethod
      def Result(cls,scoreboard:Scoreboard):
        return cls(scoreboard,True)

      @classmethod
      def Success(cls,scoreboard:Scoreboard):
        return cls(scoreboard,False)

      def __init__(self,scoreboard:Scoreboard,is_result:bool) -> None:
        super().__init__(is_result)
        self.scoreboard = scoreboard

      def export_subcommand(self) -> str:
        return super().prefix + f'score {self.scoreboard.expression()}'

    class Bossbar(IStoreSubCommandSegment):
      @classmethod
      def Result(cls,id:str,case:Literal['value','max']):
        return cls(id,case,True)

      @classmethod
      def Success(cls,id:str,case:Literal['value','max']):
        return cls(id,case,False)

      def __init__(self,id:str,case:Literal['value','max'],is_result:bool) -> None:
        super().__init__(is_result)
        self.id = id
        self.case = case

      def export_subcommand(self) -> str:
        return super().prefix + f'bossbar {self.id} {self.case}'

class ICommandMeta(ABCMeta):
  _default_accessor:None|Callable[[ICommand],ICommand] = None

  @property
  def default_accessor(cls):
    return cls._default_accessor
  
  @default_accessor.setter
  def default_accessor(cls,value:None|Callable[[ICommand],ICommand]):
    cls._default_accessor = value

class ICommand(metaclass=ICommandMeta):
  """ any minecraft command """
  def __init__(self) -> None:
    self.subcommands:list[ISubCommandSegment] = []
    self.accessor:None|Callable[[ICommand],ICommand] = type(self).default_accessor

  @property
  def has_accessor(self):
    return self.accessor is not None

  def export_command(self) -> str:
    raise NotImplementedError

  def _copy_without_accessor(self):
    s = copy(self)
    s.accessor = None
    return s

  def flatten_accessor(self) -> ICommand:
    has_accessor = self.has_accessor

    store_count = 0
    for sub in self.subcommands:
      has_accessor = has_accessor or (sub.accessor is not None)
      if isinstance(sub,IStoreSubCommandSegment):
        store_count += 1

    if not has_accessor:
      return self

    # 先頭のコマンド
    head = self._copy_without_accessor()
    head.subcommands = []
    if store_count != 0:
      head = IStoreSubCommandSegment.store_nbt.storeResult(1) + head

    # 自分自身にアクセッサがある場合
    accessor = self.accessor
    if accessor is not None:
      head = accessor(head)

    for sub in reversed(self.subcommands):
      accesssor = sub.accessor
      if isinstance(sub,IStoreSubCommandSegment):
        store_count -= 1
        f = Function()
        if store_count == 0:
          f += sub.store_nbt.remove()
        f += head
        if accesssor is None:
          f += SubCommand(sub) + (sub.store_nbt.getValue() if sub.is_result else sub.store_nbt.isExists())
        else:
          f += accesssor(SubCommand(sub.copy_without_accessor()) + (sub.store_nbt.getValue() if sub.is_result else sub.store_nbt.isExists()))
        head = f.Call()
      elif accesssor is not None:
        head = accesssor(SubCommand(sub.copy_without_accessor()) + head)
      else:
        head = SubCommand(sub) + head
    return head

  def export(self) -> str:
    result = self.export_command()
    if self.subcommands:
      return "execute " + " ".join(sub.export_subcommand() for sub in self.subcommands) + " run " + result
    else:
      return result

class SubCommand:
  """ at / positioned / in / as / rotated / store ..."""
  def __init__(self,content:ISubCommandSegment|None=None) -> None:
    self.subcommands:list[ISubCommandSegment] = []
    if content is not None:
      self.subcommands.append( content )

  @overload
  def __add__(self,other:ConditionSubCommand) -> ConditionSubCommand:pass
  
  @overload
  def __add__(self,other:SubCommand) -> SubCommand:pass

  @overload
  def __add__(self,other:ICommand) -> ICommand:pass
  
  def __add__(self,other:SubCommand|ICommand):
    if isinstance(other,ConditionSubCommand):
      result = ConditionSubCommand()
      result.subcommands = self.subcommands + other.subcommands
      return result
    elif isinstance(other,SubCommand):
      result = SubCommand()
      result.subcommands = self.subcommands + other.subcommands
      return result
    else:
      result = copy(other)
      result.subcommands = self.subcommands + other.subcommands
      return result

  def __iadd__(self,other:SubCommand):
    self.subcommands.extend(other.subcommands)
    return self

  def As(self,entity:ISelector):
    """ execute as @ """
    return self + Execute.As(entity)

  def At(self,entity:ISelector):
    """ execute at @ """
    return self + Execute.At(entity)

  def Positioned(self,pos:Position.IPosition):
    """ execute positioned ~ ~ ~ """
    return self + Execute.Positioned(pos)

  def PositionedAs(self,entity:ISelector):
    """ execute positioned as @ """
    return self + Execute.PositionedAs(entity)

  def Align(self,axes:Literal['x','y','z','xy','yz','xz','xyz']):
    """ execute align xyz """
    return self + Execute.Align(axes)
    
  def Facing(self,pos:Position.IPosition):
    """ execute facing ~ ~ ~ """
    return self + Execute.Facing(pos)

  def FacingEntity(self,entity:ISelector):
    """ execute facing entity @ """
    return self + Execute.FacingEntity(entity)

  def Rotated(self,yaw:float,pitch:float):
    """ execute rotated ~ ~ """
    return self + Execute.Rotated(yaw,pitch)

  def RotatedAs(self,target:ISelector):
    """ execute rotated as @ """
    return self + Execute.RotatedAs(target)

  def In(self,dimension:str):
    """ execute in {dimension} """
    return self + Execute.In(dimension)

  def Anchored(self,anchor:Literal['feet','eyes']):
    """ execute anchored feet|eyes """
    return self + Execute.Anchored(anchor)

  def IfBlock(self,pos:Position.IPosition,block:Block):
    """ execute if block ~ ~ ~ {block} """
    return self + Execute.IfBlock(pos,block)

  def UnlessBlock(self,pos:Position.IPosition,block:Block):
    """ execute unless block ~ ~ ~ {block} """
    return self + Execute.UnlessBlock(pos,block)

  def IfBlocks(self,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute if blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return self + Execute.IfBlocks(begin,end,destination,method)

  def UnlessBlocks(self,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute unless blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return self + Execute.UnlessBlocks(begin,end,destination,method)

  def IfEntity(self,entity:ISelector):
    """ execute if entity {entity} """
    return self + Execute.IfEntity(entity)

  def UnlessEntity(self,entity:ISelector):
    """ execute unless entity {entity} """
    return self + Execute.UnlessEntity(entity)

  def IfScore(self,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute if score {entity} {operator} {source} """
    return self + Execute.IfScore(target,source,operator)

  def IfScoreMatch(self,target:Scoreboard,start:int,stop:int|None=None):
    """ execute if score {entity} matches {start}..{stop} """
    return self + Execute.IfScoreMatch(target,start,stop)

  def UnlessScore(self,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute unless score {entity} {operator} {source} """
    return self + Execute.UnlessScore(target,source,operator)  

  def UnlessScoreMatch(self,target:Scoreboard,start:int,stop:int|None=None):
    """ execute unless score {entity} matches {start}..{stop} """
    return self + Execute.UnlessScoreMatch(target,start,stop)

  def StoreResultNbt(self,nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    """ execute store result {nbt} {scale} """
    return self + Execute.StoreResultNbt(nbt,scale)

  def StoreSuccessNbt(self,nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    """ execute store success {nbt} {scale} """
    return self + Execute.StoreSuccessNbt(nbt,scale)

  def StoreResultScore(self,score:Scoreboard):
    """ execute store result score {score} """
    return self + Execute.StoreResultScore(score)

  def StoreSuccessScore(self,score:Scoreboard):
    """ execute store success score {score} """
    return self + Execute.StoreSuccessScore(score)

  def StoreResultBossbar(self,id:str,case:Literal['value','max']):
    """ execute store result bossbar {id} value|max {score} """
    return self + Execute.StoreResultBossbar(id,case)

  def StoreSuccessBossbar(self,id:str,case:Literal['value','max']):
    """ execute store success bossbar {id} value|max {score} """
    return self + Execute.StoreSuccessBossbar(id,case)

  def Run(self,command:ICommand):
    """ execute run {command} """
    return self + Execute.Run(command)

class ConditionSubCommand(SubCommand,ICommand):
  def __init__(self, content: ISubCommandSegment | None = None) -> None:
    super().__init__(content)
    self.accessor = None

  """ if / unless """
  def export(self) -> str:
    assert self.subcommands
    assert isinstance(self.subcommands[-1],IConditionSubCommandSegment)
    return "execute " + " ".join(sub.export_subcommand() for sub in self.subcommands)

  def invert(self):
    if len(self.subcommands) != 1:
      return ValueError('cannot invert multiple subcommands')
    result = copy(self)
    head = self.subcommands[-1]
    assert isinstance(head,IConditionSubCommandSegment)
    result.subcommands = [head.invert()]
    return result

  def __inv__(self):
    return self.invert()

  def flatten_accessor(self) -> ICommand:
    has_accessor = False

    store_count = 0
    for sub in self.subcommands:
      has_accessor = has_accessor or (sub.accessor is not None)
      if isinstance(sub,IStoreSubCommandSegment):
        store_count += 1

    if not has_accessor:
      return self

    # 先頭のコマンド
    head = ConditionSubCommand(self.subcommands[-1])
    if store_count != 0:
      head = IStoreSubCommandSegment.store_nbt.storeResult(1) + head

    # 自分自身にアクセッサがある場合
    accessor = self.accessor
    if accessor is not None:
      head = accessor(head)

    for sub in reversed(self.subcommands[:-1]):
      accesssor = sub.accessor
      if isinstance(sub,IStoreSubCommandSegment):
        f = Function()
        store_count -= 1
        if store_count == 0:
          f += sub.store_nbt.remove()
        f += head
        if accesssor is None:
          f += SubCommand(sub) + (sub.store_nbt.getValue() if sub.is_result else sub.store_nbt.isExists())
        else:
          f += accesssor(SubCommand(sub) + (sub.store_nbt.getValue() if sub.is_result else sub.store_nbt.isExists()))
        head = f.Call()
      elif accesssor is not None:
        head = accesssor(SubCommand(sub) + head)
      else:
        head = SubCommand(sub) + head

    return head

class Command:
  class Reload(ICommand):
    def export_command(self) -> str:
      return 'reload'

  class Function(ICommand):
    def __init__(self,function:IFunction) -> None:
      super().__init__()
      self.function = function

    def export_command(self) -> str:
      return f'function {self.function.path}'

  class Schedule:
    class Function(ICommand):
      def __init__(self,function:IFunction,tick:int,append:bool=False) -> None:
        super().__init__()
        self.function = function
        self.tick = tick
        self.append = append

      def export_command(self) -> str:
        return f'schedule function {self.function.path}' + (' append' if self.append else '')

    class Clear(ICommand):
      def __init__(self,function:IFunction) -> None:
        super().__init__()
        self.function = function

      def export_command(self) -> str:
        return 'schedule clear ' + str(self.function.path)

  class Say(ICommand):
    def __init__(self,content:str) -> None:
      super().__init__()
      self.content = content

    def export_command(self) -> str:
      return f'say {self.content}'
  
  class Tellraw(ICommand):
    def __init__(self,selector:ISelector,*value:jsontext) -> None:
      super().__init__()
      self.selector = selector
      self.values = value
    
    def export_command(self) -> str:
      match len(self.values):
        case 0:
          v = ''
        case 1:
          v = evaljsontext(self.values[0])
        case _:
          v = list(self.values)
      return f'tellraw {self.selector.expression()} {json.dumps(v)}'

  class Summon(ICommand):
    def __init__(self,type:str,pos:Position.IPosition,**nbt:Value[INbt]):
      super().__init__()
      self.type = type
      self.pos = pos
      self.nbt = nbt

    def export_command(self) -> str:
      if self.nbt:
        return f'summon {self.type} {self.pos.expression()} {Compound(self.nbt).str()}'
      return f'summon {self.type} {self.pos.expression()}'

  class Kill(ICommand):
    def __init__(self,selector:ISelector) -> None:
      super().__init__()
      self.selector = selector
    
    def export_command(self) -> str:
      return f'kill {self.selector.expression()}' 

  class Tag:
    class List(ICommand):
      def __init__(self,entity:ISelector) -> None:
        super().__init__()
        self.entity = entity
      
      def export_command(self) -> str:
        return f'tag {self.entity.expression()} list'

    class Add(ICommand):
      def __init__(self,entity:ISelector,tag:str) -> None:
        super().__init__()
        self.entity = entity
        self.tag = tag

      def export_command(self) -> str:
        return f'tag {self.entity.expression()} add {self.tag}'

    class Remove(ICommand):
      def __init__(self,entity:ISelector,tag:str) -> None:
        super().__init__()
        self.entity = entity
        self.tag = tag

      def export_command(self) -> str:
        return f'tag {self.entity.expression()} remove {self.tag}'

  class SetBlock(ICommand):
    def __init__(self,block:Block,pos:Position.IPosition,mode:Literal['destroy','keep','replace']|None=None) -> None:
      super().__init__()
      self.block = block
      self.pos = pos
      self.mode = mode
    
    def export_command(self) -> str:        
      if self.mode:
        return f'setblock {self.pos.expression()} {self.block.expression()} {self.mode}'
      return f'setblock {self.pos.expression()} {self.block.expression()}'
  
  class Fill(ICommand):
    def __init__(self,start:Position.IPosition,end:Position.IPosition,block:Block,mode:Literal['destroy','hollow','keep','outline','replace']|None=None,oldblock:Block|None=None) -> None:
      super().__init__()
      self.start = start
      self.end = end
      self.block = block
      self.oldblock = oldblock
      self.mode = mode
    
    def export_command(self) -> str:
      if self.mode == 'replace':
        if self.oldblock is None:
          raise ValueError('fill mode "replace" needs argument "oldblock"')
        return f'fill {self.start.expression()} {self.end.expression()} {self.block.expression()} replace {self.oldblock.expression()}'
      if self.oldblock is not None:
        raise ValueError(f'''fill mode "{self.mode}" doesn't needs argument "oldblock"''')
      return f'fill {self.start.expression()} {self.end.expression()} {self.block.expression()} {self.mode}'

  @staticmethod
  class Clone(ICommand):
    def __init__(
      self,
      start:Position.IPosition,
      end:Position.IPosition,
      target:Position.IPosition,
      maskmode:Literal['replace','masked','filtered']|None=None,
      clonemode:Literal['normal','force','move']|None=None,
      filterblock:Block|None=None
    ) -> None:
      super().__init__()
      self.start = start
      self.end = end
      self.target = target
      self.maskmode = maskmode
      self.clonemode = clonemode
      self.filterblock = filterblock
      
    def export_command(self) -> str:
      clonemode_suffix = '' if self.clonemode is None else ' '+self.clonemode
      if self.maskmode == 'filtered':
        if self.filterblock is None:
          raise ValueError('clone mode "replace" needs argument "filterblock"')
        return f'clone {self.start.expression()} {self.end.expression()} {self.target.expression()} filtered {self.filterblock.expression()}' + clonemode_suffix

      if self.filterblock is not None:
        raise ValueError(f'''clone mode "{self.maskmode}" doesn't needs argument "filterblock"''')
      if self.maskmode is None:
        if self.clonemode is not None:
          raise ValueError(f'"clonemode" argument needs to be used with "maskmode" argument')
        return f'clone {self.start.expression()} {self.end.expression()} {self.target.expression()}'
      return f'clone {self.start.expression()} {self.end.expression()} {self.target.expression()} {self.maskmode}'+clonemode_suffix

  
  class Give(ICommand):
    def __init__(self,item:Item,count:int) -> None:
      super().__init__()
      self.item = item
      self.count = count
    
    def export_command(self) -> str:
      return f'give {self.item.expression()} {self.count}'

  class Clear(ICommand):
    def __init__(self,entity:ISelector,item:Item|None=None,maxcount:int|None=None) -> None:
      super().__init__()
      self.entity = entity
      self.item = item
      self.maxcount = maxcount
    
    def export(self) -> str:
      cmd = f'clear {self.entity.expression()}'
      if self.item:
        cmd += f' {self.item.expression()}'
        if self.maxcount:
          cmd += f' {self.maxcount}'
      return cmd
    
  class Particle(ICommand):
    def __init__(self,id:str,pos:Position.IPosition,dx:float,dy:float,dz:float,speed:float,count:int,mode:Literal['force','normal']|None=None,entity:ISelector|None=None) -> None:
      super().__init__()
      self.id = id
      self.pos = pos
      self.dx = dx
      self.dy = dy
      self.dz = dz
      self.speed = speed
      self.count = count
      self.mode = mode
      self.entity = entity
    
    def export_command(self) -> str:
      cmd = f'particke {self.id} {self.pos.expression()} {self.dx} {self.dy} {self.dz} {self.speed} {self.count}'
      if self.mode:
        cmd += ' '+self.mode
      if self.entity:
        cmd += ' '+self.entity.expression()
      return cmd 
    
    @staticmethod
    def Color(id:Literal['entity_effect','ambient_entity_effect'],pos:Position.IPosition,colorcode:str,mode:Literal['force','normal']|None=None,entity:ISelector|None=None):
      """
      colorcode:
        "#000000"
      """
      Command.Particle(id,pos,int(colorcode[1:3])/100,int(colorcode[3:5])/100,int(colorcode[5:7],16)/100,1,0,mode,entity) 

  class Data:
    class Get(ICommand):
      def __init__(self,nbt:INbt,scale:float|None=None) -> None:
        super().__init__()
        self.accessor = nbt.accessor
        self.nbt = nbt
        self.scale = scale

      def export_command(self) -> str:
        if self.scale:
          return f'data get {self.nbt.path} {float_to_str(self.scale)}'
        return f'data get {self.nbt.path}'

    class Remove(ICommand):
      def __init__(self,nbt:INbt,scale:float|None=None) -> None:
        super().__init__()
        self.accessor = nbt.accessor
        self.nbt = nbt
        self.scale = scale

      def export_command(self) -> str:
        if self.scale:
          return f'data remove {self.nbt.path} {float_to_str(self.scale)}'
        return f'data remove {self.nbt.path}'
 
    class Modify:
      class Set(ICommand):
        def __new__(cls: type[Self],target:NBT,source:Value[NBT]|NBT) -> ICommand:
          if isinstance(source,Value):
            return Command.Data.Modify.Set.Value(target,source)
          else:
            return Command.Data.Modify.Set.From(target,source)

        def __init__(self,*_:Any,**__:Any) -> None: raise NotImplementedError

        class Value(ICommand):
          def __init__(self,target:NBT,value:Value[NBT]) -> None:
            super().__init__()
            self.accessor = target.accessor
            self.target = target
            self.value = value

          def export_command(self) -> str:
            return f'data modify {self.target.path} set value {self.value.str()}'

        class From(ICommand):
          def __init__(self,target:NBT,source:NBT) -> None:
            super().__init__()

            self.target = target
            self.source = source

            match (target.accessor,source.accessor):
              case (None,None):
                self.accessor = None
              case (None,src):
                self.accessor = src
              case (tgt,None):
                self.accessor = tgt
              case (tgt,src):
                assert tgt is not None
                assert src is not None
                temp = _pydp_storage['tmp',target.cls]
                def accessor(cmd:ICommand):
                  func = Function()
                  func += temp.remove()
                  func += Command.Data.Modify.Set.From(temp,source).flatten_accessor()
                  func += Command.Data.Modify.Set.From(target,temp).flatten_accessor()
                  func += cmd
                  func += src(cmd)
                  return func.Call()
                self.accessor = accessor

          def export_command(self) -> str:
            return f'data modify {self.target.path} set from {self.source.path}'
      
      class Merge(ICommand):
        def __new__(cls: type[Self],target:Compound,source:Value[Compound]|Compound) -> ICommand:
          if isinstance(source,Value):
            return Command.Data.Modify.Merge.Value(target,source)
          else:
            return Command.Data.Modify.Merge.From(target,source)

        def __init__(self,*_:Any,**__:Any) -> None: raise NotImplementedError

        class Value(ICommand):
          def __init__(self,target:Compound,value:Value[Compound]) -> None:
            super().__init__()
            self.target = target
            self.value = value

          def export_command(self) -> str:
            return f'data modify {self.target.path} merge value {self.value.str()}'

        class From(ICommand):
          def __init__(self,target:Compound,source:Compound) -> None:
            super().__init__()
            self.target = target
            self.source = source

            match (target.accessor,source.accessor):
              case (None,None):
                self.accessor = None
              case (None,src):
                self.accessor = src
              case (tgt,None):
                self.accessor = tgt
              case (tgt,src):
                assert tgt is not None
                assert src is not None
                temp = _pydp_storage['tmp',target.cls]
                _source = source.copy()
                _source.accessor = None
                _target = target.copy()
                _target.accessor = None
                def accessor(cmd:ICommand):
                  func = Function()
                  func += temp.remove()
                  func += Command.Data.Modify.Set.From(temp,_source).flatten_accessor()
                  func += Command.Data.Modify.Merge.From(_target,temp).flatten_accessor()
                  func += cmd
                  func += src(cmd)
                  return func.Call()
                self.accessor = accessor

          def export_command(self) -> str:
            return f'data modify {self.target.path} merge from {self.source.path}'

      class Append(ICommand):
        def __new__(cls: type[Self],target:IArray[NBT],source:Value[IArray[NBT]]|IArray[NBT]) -> ICommand:
          if isinstance(source,Value):
            return Command.Data.Modify.Append.Value(target,source)
          else:
            return Command.Data.Modify.Append.From(target,source)

        def __init__(self,*_:Any,**__:Any) -> None: raise NotImplementedError

        class Value(ICommand):
          def __init__(self,target:IArray[NBT],value:Value[IArray[NBT]]) -> None:
            super().__init__()
            self.target = target
            self.value = value

          def export_command(self) -> str:
            return f'data modify {self.target.path} append value {self.value.str()}'

        class From(ICommand):
          def __init__(self,target:IArray[NBT],source:IArray[NBT]) -> None:
            super().__init__()
            self.target = target
            self.source = source

            match (target.accessor,source.accessor):
              case (None,None):
                self.accessor = None
              case (None,src):
                self.accessor = src
              case (tgt,None):
                self.accessor = tgt
              case (tgt,src):
                assert tgt is not None
                assert src is not None
                temp = _pydp_storage['tmp',target.cls]
                _source = source.copy()
                _source.accessor = None
                _target = target.copy()
                _target.accessor = None
                def accessor(cmd:ICommand):
                  func = Function()
                  func += temp.remove()
                  func += Command.Data.Modify.Set.From(temp,_source).flatten_accessor()
                  func += Command.Data.Modify.Append.From(_target,temp).flatten_accessor()
                  func += cmd
                  func += src(cmd)
                  return func.Call()
                self.accessor = accessor

          def export_command(self) -> str:
            return f'data modify {self.target.path} append from {self.source.path}'

      class Prepend(ICommand):
        def __new__(cls: type[Self],target:IArray[NBT],source:Value[IArray[NBT]]|IArray[NBT]) -> ICommand:
          if isinstance(source,Value):
            return Command.Data.Modify.Prepend.Value(target,source)
          else:
            return Command.Data.Modify.Prepend.From(target,source)

        def __init__(self,*_:Any,**__:Any) -> None: raise NotImplementedError

        class Value(ICommand):
          def __init__(self,target:IArray[NBT],value:Value[IArray[NBT]]) -> None:
            super().__init__()
            self.target = target
            self.value = value

          def export_command(self) -> str:
            return f'data modify {self.target.path} prepend value {self.value.str()}'

        class From(ICommand):
          def __init__(self,target:IArray[NBT],source:IArray[NBT]) -> None:
            super().__init__()
            self.target = target
            self.source = source

            match (target.accessor,source.accessor):
              case (None,None):
                self.accessor = None
              case (None,src):
                self.accessor = src
              case (tgt,None):
                self.accessor = tgt
              case (tgt,src):
                assert tgt is not None
                assert src is not None
                temp = _pydp_storage['tmp',target.cls]
                _source = source.copy()
                _source.accessor = None
                _target = target.copy()
                _target.accessor = None
                def accessor(cmd:ICommand):
                  func = Function()
                  func += temp.remove()
                  func += Command.Data.Modify.Set.From(temp,_source).flatten_accessor()
                  func += Command.Data.Modify.Prepend.From(_target,temp).flatten_accessor()
                  func += cmd
                  func += src(cmd)
                  return func.Call()
                self.accessor = accessor

          def export_command(self) -> str:
            return f'data modify {self.target.path} prepend from {self.source.path}'

      class Insert(ICommand):
        def __new__(cls: type[Self],target:IArray[NBT],index:int,source:Value[IArray[NBT]]|IArray[NBT]) -> ICommand:
          if isinstance(source,Value):
            return Command.Data.Modify.Insert.Value(target,index,source)
          else:
            return Command.Data.Modify.Insert.From(target,index,source)

        def __init__(self,*_:Any,**__:Any) -> None: raise NotImplementedError

        class Value(ICommand):
          def __init__(self,target:IArray[NBT],index:int,value:Value[IArray[NBT]]) -> None:
            super().__init__()
            self.target = target
            self.value = value
            self.index = index

          def export_command(self) -> str:
            return f'data modify {self.target.path} insert {self.index} value {self.value.str()}'

        class From(ICommand):
          def __init__(self,target:IArray[NBT],index:int,source:IArray[NBT]) -> None:
            super().__init__()
            self.target = target
            self.source = source
            self.index = index

            match (target.accessor,source.accessor):
              case (None,None):
                self.accessor = None
              case (None,src):
                self.accessor = src
              case (tgt,None):
                self.accessor = tgt
              case (tgt,src):
                assert tgt is not None
                assert src is not None
                temp = _pydp_storage['tmp',target.cls]
                _source = source.copy()
                _source.accessor = None
                _target = target.copy()
                _target.accessor = None
                def accessor(cmd:ICommand):
                  func = Function()
                  func += temp.remove()
                  func += Command.Data.Modify.Set.From(temp,_source).flatten_accessor()
                  func += Command.Data.Modify.Insert.From(_target,index,temp).flatten_accessor()
                  func += cmd
                  func += src(cmd)
                  return func.Call()
                self.accessor = accessor

          def export_command(self) -> str:
            return f'data modify {self.target.path} insert {self.index} from {self.source.path}'

  class Scoreboard:
    class Objectives:
      class Add(ICommand):
        def __init__(self,objective:Objective,condition:str='dummy',display:str|None=None) -> None:
          super().__init__()
          self.objective = objective
          self.condition = condition
          self.display = display
        
        def export_command(self) -> str:
          if self.display is None:
            return f'scoreboard objectives add {self.objective.id} {self.condition}'
          return f'scoreboard objectives add {self.objective.id} {self.condition} {self.display}'

      class List(ICommand):
        def __init__(self) -> None:
          super().__init__()
        
        def export_command(self) -> str:
          return f'scoreboard objectives list'

      class Modify:
        class Rendertype(ICommand):
          def __init__(self,objective:Objective,rendertype:Literal['hearts','integer']) -> None:
            super().__init__()
            self.objective = objective
            self.rendertype = rendertype
          
          def export_command(self) -> str:
            return f'scoreboard objectives modify {self.objective.id} rendertype {self.rendertype}'

        class Displayname(ICommand):
          def __init__(self,objective:Objective,displayname:str) -> None:
            super().__init__()
            self.objective = objective
            self.displayname = displayname
          
          def export_command(self) -> str:
            return f'scoreboard objectives modify {self.objective.id} displayname {self.displayname}'

      class Remove(ICommand):
        def __init__(self,objective:Objective) -> None:
          super().__init__()
          self.objective = objective

        def export_command(self) -> str:
          return f'scoreboard objectives remove {self.objective.id}'

      class Setdisplay(ICommand):
        @classmethod
        def clear(cls,slot:str):
          return cls(None,slot)

        def __init__(self,objective:Objective|None,slot:str) -> None:
          super().__init__()
          self.objective = objective
          self.slot = slot

        def export_command(self) -> str:
          if self.objective is None:
            return f'scoreboard objectives setdisplay {self.slot}'
          return f'scoreboard objectives setdisplay {self.slot} {self.objective.id}'

    class Players:
      class Add(ICommand):
        def __init__(self,score:Scoreboard,value:int) -> None:
          super().__init__()
          assert 0 <= value <= 2147483647
          self.score = score
          self.value = value

        def export_command(self) -> str:
          return f'scoreboard players add {self.score.expression()} {self.value}'

      class Remove(ICommand):
        def __init__(self,score:Scoreboard,value:int) -> None:
          super().__init__()
          assert 0 <= value <= 2147483647
          self.score = score
          self.value = value

        def export_command(self) -> str:
          return f'scoreboard players remove {self.score.expression()} {self.value}'

      class Set(ICommand):
        def __init__(self,score:Scoreboard,value:int) -> None:
          super().__init__()
          assert -2147483648 <= value <= 2147483647
          self.score = score
          self.value = value

        def export_command(self) -> str:
          return f'scoreboard players set {self.score.expression()} {self.value}'

      class Get(ICommand):
        def __init__(self,score:Scoreboard) -> None:
          super().__init__()
          self.score = score

        def export_command(self) -> str:
          return f'scoreboard players get {self.score.expression()}'

      class Reset(ICommand):
        def __init__(self,score:Scoreboard) -> None:
          super().__init__()
          self.score = score

        def export_command(self) -> str:
          return f'scoreboard players reset {self.score.expression()}'

      class Enable(ICommand):
        def __init__(self,score:Scoreboard) -> None:
          super().__init__()
          self.score = score

        def export_command(self) -> str:
          return f'scoreboard players enable {self.score.expression()}'

      class List(ICommand):
        def __init__(self,selector:IScoreHolder|None) -> None:
          super().__init__()
          self.selector = selector

        def export_command(self) -> str:
          if self.selector is None:
            return f'scoreboard players list *'
          return f'scoreboard players list {self.selector.expression()}'

      class Operation(ICommand):
        def __init__(self,target:Scoreboard,operator:Literal['+=','-=','*=','/=','%=','=','<','>','><'],source:Scoreboard) -> None:
          super().__init__()
          self.operator = operator
          self.target = target
          self.source = source

        def export_command(self) -> str:
          return f'scoreboard players operation {self.target.expression()} {self.operator} {self.source.expression()}'

class IDatapackLibrary:
  """
  データパックライブラリ用クラス

  このクラスを継承すると出力先データパックに自動で導入される
  """
  using = True

  @classmethod
  def install(cls,datapack_path:Path,datapack_id:str) -> None:
    """
    ライブラリを導入

    データパック出力時に cls.using == True なら呼ばれる

    導入済みでも呼ばれる

    datapack_path : saves/{worldname}/datapacks/{datapack}

    datapack_id : 出力データパックのID
    """
    raise NotImplementedError

  @staticmethod
  def rmtree(path:Path):
    """ アクセス拒否を解消したshutil.rmtree """
    def onerror(func:Callable[[Path],None], path:Path, exc_info:Any):
      """
      Error handler for ``shutil.rmtree``.

      If the error is due to an access error (read only file)
      it attempts to add write permission and then retries.

      If the error is for another reason it re-raises the error.

      Usage : ``shutil.rmtree(path, onerror=onerror)``
      """
      import stat
      if not os.access(path, os.W_OK):
          # Is the error an access error ?
          os.chmod(path, stat.S_IWUSR)
          func(path)
      else:
          raise
    shutil.rmtree(path,onerror=onerror)
  
  @classmethod
  def uninstall(cls,datapack_path:Path) -> None:
    """
    ライブラリを削除

    未導入でも呼ばれる

    datapack_path : saves/{worldname}/datapacks/{datapack}
    """
    raise NotImplementedError

class _DatapackMeta(type):
  _default_path= McPath('minecraft:pydp')

  @property
  def default_path(cls) -> McPath:
    return cls._default_path

  @default_path.setter
  def default_path(cls,value:McPath|str):
    cls._default_path = McPath(value)

  _description:str|None=None
  @property
  def description(cls):
    return cls._description

  @description.setter
  def description(cls,value:None|str):
    cls._description = value
  
  export_imp_doc = True

class FunctionAccessModifier(Enum):
  WITHIN = "within"
  PRIVATE = "private"
  INTERNAL = "internal"
  PUBLIC = "public"
  API = "api"

class Datapack(metaclass=_DatapackMeta):
  """
  データパック出力時の設定

  attrs
  ---
  default_namespace:
    匿名ファンクションの出力先の名前空間

  default_folder:
    匿名ファンクションの出力先のディレクトリ階層

  description:
    データパックの説明 (pack.mcmetaのdescriptionの内容)

  export_imp_doc:
    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc) を出力するか否か
  """
  created_paths:list[Path] = []

  @staticmethod
  def export(
    path:str|Path,
    id:str,
    default_path:str|McPath|None=None,
    description:str|None=None,
    export_imp_doc:bool|None=None
    ):
    """
    データパックを指定パスに出力する

    必ず一番最後に呼ぶこと

    params
    ---
    path: Path
      データパックのパス ...\\saves\\\\{world_name}\\datapacks\\\\{datapack_name}

    id: Str
      データパックのID(半角英数)

    default_namespace: str = '_'
      自動生成されるファンクションの格納先の名前空間

      例 : '_', 'foo'

    default_folder: str = ''
      自動生成されるファンクションの格納先のディレクトリ階層 空文字列の場合は名前空間直下に生成

      例 : '', 'foo/', 'foo/bar/'
    
    description: str|None = None
      データパックのpack.mcmetaのdescriptionの内容

    export_imp_doc:
      [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc) を出力するか否か
    """

    path = Path(path)

    if default_path is not None: Datapack.default_path = McPath(default_path)
    if description is not None: Datapack.description = description
    if export_imp_doc is not None: Datapack.export_imp_doc = export_imp_doc

    pydptxt = (path/"pydp.txt")
    if pydptxt.exists():
      for s in reversed(pydptxt.read_text().split('\n')):
        p = (path / s)
        if not p.exists():
          continue
        if p.is_file():
          p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
          p.rmdir()


    for library in IDatapackLibrary.__subclasses__():
      if library.using:
        library.install(path,id)
      else:
        library.uninstall(path)


    if not path.exists():
      Datapack.created_paths.append(path)
      path.mkdir(parents=True)

    mcmeta = path/"pack.mcmeta"
    if not mcmeta.exists() or Datapack.description is not None:
      description = "pydp auto generated datapack" if Datapack.description is None else Datapack.description
      mcmeta.write_text(f"""{{
  "pack":{{
    "pack_format":10,
    "description":{description}
  }}
}}""")

    for p in IPredicate.predicates:
      p.export(path)

    for f in Function.functions:
      # functionのアクセッサを展開
      f.flatten_accessor()

    for f in FunctionTag.functiontags:
      # function.taggedをTrueにする
      f.check_call_relation()

    for f in Function.functions:
      # 呼び出し構造の解決
      f.check_call_relation()

    for f in Function.functions:
      # 書き出しか埋め込みかを決定する
      f.define_state()

    for f in Function.functions:
      # 埋め込みが再帰しないように解決
      f.recursivecheck()

    for f in FunctionTag.functiontags:
      # ファンクションタグ出力
      f.export(path)

    for f in Function.functions:
      # ファンクション出力
      f.export(path)

    pathstrs:list[str] = []
    for p in Datapack.created_paths:
      relpath = p.relative_to(path)
      pathstrs.append(str(relpath))
    pydptxt.write_text('\n'.join(pathstrs))
  
  @staticmethod
  def mkdir(path:Path,delete_on_regenerate:bool=True):
    """
    ディレクトリを生成する
    """
    if delete_on_regenerate:
      paths:list[Path] = []
      _path = path
      while not _path.exists():
        paths.append(_path)
        _path = _path.parent
      Datapack.created_paths.extend(reversed(paths))

    if path.is_dir():
      path.mkdir(parents=True,exist_ok=True)
    else:
      path.parent.mkdir(parents=True,exist_ok=True)



class IFunction(metaclass=ABCMeta):
  def __init__(self) -> None:
    pass

  def Call(self) -> ICommand:
    return Command.Function(self)

  def Schedule(self,tick:int,append:bool=False) -> ICommand:
    self._scheduled = True
    return Command.Schedule.Function(self,tick,append)

  def ScheduleClear(self) -> ICommand:
    self._scheduled = True
    return Command.Schedule.Clear(self)

  @property
  @abstractmethod
  def path(self) -> McPath: pass

class ExternalFunction(IFunction):
  def __init__(self,path:str|McPath) -> None:
    super().__init__()
    self._path = McPath(path)
    if self._path.istag: raise ValueError("ExternalFunctionTag path must not starts with '#'")

  @property
  def path(self) -> McPath:
    return self._path

class ExternalFunctionTag(IFunction):
  def __init__(self,path:str|McPath) -> None:
    super().__init__()
    self._path = McPath(path)
    if not self._path.istag: raise ValueError("ExternalFunctionTag path must starts with '#'")

  @property
  def path(self) -> McPath:
    return self._path

class _FuncState(Enum):
  NEEDLESS = auto()
  FLATTEN = auto()
  SINGLE = auto()
  EXPORT = auto()

class Function(IFunction):
  """
  新規作成するmcfunctionをあらわすクラス

  既存のmcfunctionを使う場合はExistFunctionクラスを使うこと

  `Function += Command`でコマンドを追加できる。

  マイクラ上では`function {namespace}:{name}`となる。

  `namespace`,`name`を省略するとデフォルトの名前空間のデフォルトのフォルダ内に`"{自動生成id}.mcfunction"`が生成される。
  ただし、最適化によってmcfunctionファイルが生成されない場合がある。

  デフォルトの名前空間とデフォルトのフォルダはFunction.exportAll()の引数で設定可能。

  params
  ---
  namespace: Optional[str] = None
    ファンクション名前空間

    省略するとデフォルトの名前空間となる (Function.exportAll()の引数で設定可能) 

    例: `"minecraft"` `"mynamespace"`

  name: Optional[str] = None
    ファンクションのパス 空白や'/'で終わる場合はファンクション名が`".mcfunction"`となる

    省略するとデフォルトのフォルダ内の`{自動生成id}.mcfunction`となる (Function.exportAll()の引数で設定可能) 

    例: `""` `"myfync"` `"dir/myfunc"` `"dir/subdir/"`
  
  access_modifier: Optional[FunctionAccessModifier]
    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc)のファンクションアクセス修飾子を指定

    Datapack.export_imp_doc == False の場合機能しない

    デフォルト: 匿名ファンクションの場合 WITHIN, 名前付きの場合 API
  
  description: Optional[str]
    functionの説明文 複数行可能

    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc)に記載する

    Datapack.export_imp_doc == False の場合機能しない
  
  delete_on_regenerate:
    データパック再生成時にファンクションを削除するかどうか
    基本的にTrue

  commands: list[Command] = []
    コマンドのリスト

    += で後からコマンドを追加できるので基本的には与えなくてよい

  example
  ---

  ```python
  func1 = Function('minecraft','test/func')
  func1 += MC.Say('hello')

  func2 = Function()

  func1 += func2.call()
  ```

  """

  functions:list[Function] = []

  @classmethod
  def nextPath(cls) -> str:
    """無名ファンクションのパスを生成する"""
    return gen_id(upper=False,length=24)

  callstate:_FuncState
  default_access_modifier:FunctionAccessModifier = FunctionAccessModifier.API

  _path:McPath|None

  @overload
  def __init__(self,path:str|McPath,access_modifier:FunctionAccessModifier|None=None,description:str|None=None,delete_on_regenerate:bool=True,*_,commands:None|list[ICommand]=None) -> None:pass
  @overload
  def __init__(self,path:str|McPath,*_,commands:None|list[ICommand]=None) -> None:pass
  @overload
  def __init__(self,*_,commands:None|list[ICommand]=None) -> None:pass
  def __init__(self,path:str|McPath|None=None,access_modifier:FunctionAccessModifier|None=None,description:str|None=None,delete_on_regenerate:bool=True,*_,commands:None|list[ICommand]=None) -> None:


    self.delete_on_regenerate = delete_on_regenerate

    self.functions.append(self)
    self.commands:list[ICommand] = [*commands] if commands else []
    self._path = None if path is None else McPath(path)
    self._children:set[Function] = set()

    self._hasname = self._path is not None
    self._scheduled = False
    self.tagged = False
    self.subcommanded = False
    self.used = False
    self.visited = False

    self.description = description

    self.calls:set[Function] = set()

    self.within:set[Function|FunctionTag] = set()

    if access_modifier is None:
      if self._hasname:
        access_modifier = Function.default_access_modifier
      else:
        access_modifier = FunctionAccessModifier.WITHIN
    self.access_modifier = access_modifier

  def set_path(self,path:str|McPath):
    self._path = McPath(path)
    self._hasname = True

  @property
  def path(self) -> McPath:
    if self._path is None:
      self._path = Datapack.default_path/self.nextPath()
    return self._path

  def __iadd__(self,value:ICommand):
    self.append(value)
    return self

  def append(self,command:ICommand):
    if isinstance(command,Command.Function):
      func = command.function
      if isinstance(func,Function):
        self._children.add(func)
    self.commands.append(command)

  def extend(self,commands:Iterable[ICommand]):
    for command in commands:
      self.append(command)

  @property
  def expression(self) -> str:
    return self.path.str

  def _isempty(self):
    for cmd in self.commands:
      if isinstance(cmd,Command.Function):
        func = cmd.function
        if isinstance(func,Function) and func._isempty():
          continue
      return False
    return True

  def _issingle(self):
    return len(self.commands) == 1

  def _ismultiple(self):
    return len(self.commands) > 1

  def flatten_accessor(self):
    """アクセッサを解決"""
    commands:list[ICommand] = []
    for command in self.commands:
      commands.append(command.flatten_accessor())
    self.commands = commands

  def check_call_relation(self):
    """呼び出し先一覧を整理"""
    for cmd in self.commands:
      if isinstance(cmd,Command.Function):
        func = cmd.function
        if isinstance(func,Function):
          if cmd.subcommands:
            func.subcommanded = True
          func.used = True
          self.calls.add(func)
          func.within.add(self)

  def define_state(self) -> None:
    """関数を埋め込むか書き出すか決定する"""
    if self._hasname:
      self.callstate = _FuncState.EXPORT
    elif self._isempty():
      self.callstate = _FuncState.NEEDLESS
    elif self._scheduled or self.tagged:
      self.callstate = _FuncState.EXPORT
    elif not self.subcommanded:
      self.callstate = _FuncState.FLATTEN
    elif self._issingle():
      self.callstate = _FuncState.SINGLE
    else:
      self.callstate = _FuncState.EXPORT

  def recursivecheck(self,parents:set[Function]=set()):
    """埋め込み再帰が行われている場合、ファイル出力に切り替える"""
    if self.visited: return
    parents = parents|{self}

    for cmd in self.commands:
      if isinstance(cmd,Command.Function):
        func = cmd.function
        if isinstance(func,Function):
          if func in parents:
            func.callstate = _FuncState.EXPORT
          if func.callstate is _FuncState.FLATTEN or func.callstate is _FuncState.SINGLE:
            func.recursivecheck(parents)

    self.visited = True

  def export_commands(self,path:Path,commands:list[str],subcommand:list[ISubCommandSegment],is_root:bool=False):
    passed = False
    match self.callstate:
      case _FuncState.NEEDLESS:
        pass
      case _FuncState.FLATTEN:
        assert not subcommand
        for cmd in self.commands:
          if isinstance(cmd,Command.Function):
            func = cmd.function
            if isinstance(func,Function):
              func.export_commands(path,commands,cmd.subcommands)
              continue
          commands.append(cmd.export())
      case _FuncState.SINGLE:
        assert len(self.commands) == 1
        cmd = self.commands[0]
        if isinstance(cmd,Command.Function):
          func = cmd.function
          if isinstance(func,Function):
            func.export_commands(path,commands,subcommand + cmd.subcommands)
            passed = True
        if not passed:
          s = cmd.subcommands
          cmd.subcommands = subcommand + cmd.subcommands
          commands.append(cmd.export())
          cmd.subcommands = s
      case _FuncState.EXPORT:
        if is_root:
          cmds:list[str] = []
          for cmd in self.commands:
            if isinstance(cmd,Command.Function):
              func = cmd.function
              if isinstance(func,Function):
                func.export_commands(path,cmds,cmd.subcommands)
                continue
            cmds.append(cmd.export())
          self.export_function(path,cmds)

        cmd = Command.Function(self)
        cmd.subcommands = [*subcommand]
        commands.append(cmd.export())

  def export_function(self,path:Path,commands:list[str]):
    path = self.path.function(path)


    Datapack.mkdir(path,self.delete_on_regenerate)

    if Datapack.export_imp_doc:
      commands.insert(0,self._imp_doc())

    result = "\n".join(commands)

    path.write_text(result,encoding='utf8')

  def _imp_doc(self):
    description = ''
    if self.description:
      description = '\n' + '\n# \n'.join( f"# {x}" for x in self.description.split('\n'))

    withinstr = ''
    if self.access_modifier is FunctionAccessModifier.WITHIN:
      withins:list[str] = []
      for file in self.within:
        match file:
          case Function():
            withins.append(f'function {file.expression}')
          case FunctionTag():
            withins.append(f'tag/function {file.expression_without_hash}')
      withinstr = '\n' + '\n'.join(f'#   {x}' for x in withins)

    return f"""#> {self.expression}{description}
# @{self.access_modifier.value}""" + withinstr

  def export(self,path:Path) -> None:
    if self.callstate is _FuncState.EXPORT:
      self.export_commands(path,[],[],True)

class FunctionTag(IFunction):
  tick:FunctionTag
  load:FunctionTag
  functiontags:list[FunctionTag] = []
  def __init__(self,path:str|McPath,export_if_empty:bool=True) -> None:
    FunctionTag.functiontags.append(self)
    self._path = McPath(path)
    assert self._path.istag
    self.export_if_empty = export_if_empty
    self.functions:list[Function|str|McPath] = []

  @property
  def path(self) -> McPath:
    return self._path

  def call(self) -> ICommand:
    return Command.Function(self)

  @property
  def expression_without_hash(self) -> str:
    return self._path.str

  def append(self,function:Function|str|McPath):
    if isinstance(function,Function):
      function.tagged = True
    self.functions.append(function)

  def check_call_relation(self):
    """呼び出し先のファンクションにタグから呼ばれることを伝える"""
    for f in self.functions:
      if isinstance(f,Function):
        f.tagged = True
        f.within.add(self)

  def export(self,path:Path) -> None:
    path = self.path.function_tag(path)
    values:list[str] = []
    for f in self.functions:
      if isinstance(f,Function) and f.callstate is _FuncState.EXPORT:
        """中身のある呼び出し先だけ呼び出す"""
        values.append(f.expression)

    paths:list[Path] = []
    if self.export_if_empty or values:
      _path = path
      while not _path.exists():
        paths.append(_path)
        _path = _path.parent
      Datapack.created_paths.extend(reversed(paths))

      path.parent.mkdir(parents=True,exist_ok=True)
      path.write_text(json.dumps({"values":values}),encoding='utf8')

FunctionTag.tick = FunctionTag('#minecraft:tick',False)
FunctionTag.load = FunctionTag('#minecraft:load',False)





















class Execute:
  """
  コマンド/サブコマンド生成メソッドをまとめたstaticクラス

  大体のコマンドはここから呼び出せる

  コマンドを追加する場合もここに
  """

  @staticmethod
  def As(entity:ISelector):
    """ execute as @ """
    return SubCommand(SubCommandSegment.As(entity))

  @staticmethod
  def At(entity:ISelector):
    """ execute at @ """
    return SubCommand(SubCommandSegment.At(entity))

  @staticmethod
  def Positioned(pos:Position.IPosition):
    """ execute positioned ~ ~ ~ """
    return SubCommand(SubCommandSegment.Positioned(pos))

  @staticmethod
  def PositionedAs(entity:ISelector):
    """ execute positioned as @ """
    return SubCommand(SubCommandSegment.Positioned.As(entity))

  @staticmethod
  def Align(axes:Literal['x','y','z','xy','yz','xz','xyz']):
    """ execute align xyz """
    return SubCommand(SubCommandSegment.Align(axes))
    
  @staticmethod
  def Facing(pos:Position.IPosition):
    """ execute facing ~ ~ ~ """
    return SubCommand(SubCommandSegment.Facing(pos))

  @staticmethod
  def FacingEntity(entity:ISelector):
    """ execute facing entity @ """
    return SubCommand(SubCommandSegment.Facing.Entity(entity))

  @staticmethod
  def Rotated(yaw:float,pitch:float):
    """ execute rotated ~ ~ """
    return SubCommand(SubCommandSegment.Rotated(yaw,pitch))

  @staticmethod
  def RotatedAs(target:ISelector):
    """ execute rotated as @ """
    return SubCommand(SubCommandSegment.Rotated.As(target))

  @staticmethod
  def In(dimension:str):
    """ execute in {dimension} """
    return SubCommand(SubCommandSegment.In(dimension))

  @staticmethod
  def Anchored(anchor:Literal['feet','eyes']):
    """ execute anchored feet|eyes """
    return SubCommand(SubCommandSegment.Anchored(anchor))

  @staticmethod
  def IfNbt(nbt:INbt):
    """ execute if block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Nbt.If(nbt))

  @staticmethod
  def UnlessNbt(nbt:INbt):
    """ execute unless block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Nbt.Unless(nbt))

  @staticmethod
  def IfNbtMatch(nbt:NBT,value:Value[NBT]):
    """ execute if block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Nbt.Matches.If(nbt,value))

  @staticmethod
  def UnlessNbtMatch(nbt:NBT,value:Value[NBT]):
    """ execute unless block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Nbt.Matches.Unless(nbt,value))

  @staticmethod
  def IfBlock(pos:Position.IPosition,block:Block):
    """ execute if block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Block.If(pos,block))

  @staticmethod
  def UnlessBlock(pos:Position.IPosition,block:Block):
    """ execute unless block ~ ~ ~ {block} """
    return ConditionSubCommand(SubCommandSegment.Condition.Block.Unless(pos,block))

  @staticmethod
  def IfBlocks(begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute if blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return ConditionSubCommand(SubCommandSegment.Condition.Blocks.If(begin,end,destination,method))

  @staticmethod
  def UnlessBlocks(begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute unless blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return ConditionSubCommand(SubCommandSegment.Condition.Blocks.Unless(begin,end,destination,method))

  @staticmethod
  def IfEntity(entity:ISelector):
    """ execute if entity {entity} """
    return ConditionSubCommand(SubCommandSegment.Condition.Entity.If(entity))

  @staticmethod
  def UnlessEntity(entity:ISelector):
    """ execute unless entity {entity} """
    return ConditionSubCommand(SubCommandSegment.Condition.Entity.Unless(entity))

  @staticmethod
  def IfScore(target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute if score {entity} {operator} {source} """
    return ConditionSubCommand(SubCommandSegment.Condition.Score.If(target,source,operator))

  @staticmethod
  def IfScoreMatch(target:Scoreboard,start:int,stop:int|None=None):
    """ execute if score {entity} matches {start}..{stop} """
    return ConditionSubCommand(SubCommandSegment.Condition.Score.Matches.If(target,start,stop))

  @staticmethod
  def UnlessScore(target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute unless score {entity} {operator} {source} """
    return ConditionSubCommand(SubCommandSegment.Condition.Score.Unless(target,source,operator)  )

  @staticmethod
  def UnlessScoreMatch(target:Scoreboard,start:int,stop:int|None=None):
    """ execute unless score {entity} matches {start}..{stop} """
    return ConditionSubCommand(SubCommandSegment.Condition.Score.Matches.Unless(target,start,stop))

  @staticmethod
  def StoreResultNbt(nbt:INum[Any],scale:float=1):
    """ execute store result {nbt} {scale} """
    return SubCommand(SubCommandSegment.Store.Nbt.Result(nbt,scale))

  @staticmethod
  def StoreSuccessNbt(nbt:INum[Any],scale:float=1):
    """ execute store success {nbt} {scale} """
    return SubCommand(SubCommandSegment.Store.Nbt.Success(nbt,scale))

  @staticmethod
  def StoreResultScore(score:Scoreboard):
    """ execute store result score {score} """
    return SubCommand(SubCommandSegment.Store.Score.Result(score))

  @staticmethod
  def StoreSuccessScore(score:Scoreboard):
    """ execute store success score {score} """
    return SubCommand(SubCommandSegment.Store.Score.Success(score))

  @staticmethod
  def StoreResultBossbar(id:str,case:Literal['value','max']):
    """ execute store result bossbar {id} value|max {score} """
    return SubCommand(SubCommandSegment.Store.Bossbar.Result(id,case))

  @staticmethod
  def StoreSuccessBossbar(id:str,case:Literal['value','max']):
    """ execute store success bossbar {id} value|max {score} """
    return SubCommand(SubCommandSegment.Store.Bossbar.Success(id,case))

  @staticmethod
  def Run(command:ICommand):
    """ execute run {command} """
    return command






























class NbtPath:
  class INbtPath:
    def __init__(self,parent:NbtPath.INbtPath) -> None:
      self._parent = parent

    @abstractmethod
    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      """
      パスが指定された値を持つかどうかを調べるためのパス
      """

    @abstractmethod
    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      """
      パスをdictの内容で絞るためのパス
      """

    @final
    def str(self)->str:
      return f"{self.typestr} {self.holderstr} {self.pathstr}"
    
    def __str__(self):
      return self.str()

    @property
    def to_jsontext(self) -> _jsontextvalue:
      return {"nbt":self.pathstr,self.typestr:self.holderstr}
    
    @property
    def typestr(self) -> str:
      return self._parent.typestr

    @property
    def holderstr(self) -> str:
      return self._parent.holderstr

    @property
    @abstractmethod
    def pathstr(self) -> str:
      """
      nbtパスの文字列

      a / a.a / a[0] ...
      """

  class Root(INbtPath):
    """stoarge a:b {}"""
    def __init__(self,type:Literal["storage","entity","block"],holder:str) -> None:
      self._type:Literal["storage","entity","block"] = type
      self._holder = holder

    def match(self,value:Value[INbt]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self.filter(value)

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.RootMatch(self._type,self._holder,value)

    @property
    def pathstr(self)->str:
      return f'{{}}'

    @property
    def typestr(self) -> str:
      return self._type

    @property
    def holderstr(self) -> str:
      return self._holder

  class RootMatch(INbtPath):
    """stoarge a:b {bar:buz}"""
    def __init__(self,type:Literal["storage","entity","block"],holder:str,match:Value[Compound]) -> None:
      self._condition = match
      self._type:Literal["storage","entity","block"] = type
      self._holder = holder

    def match(self,value:Value[INbt]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self.filter(value)

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.RootMatch(self._type,self._holder,Compound.mergeValue(self._condition,value))
    
    @property
    def pathstr(self)->str:
      return self._condition.str()

    @property
    def typestr(self) -> str:
      return self._type

    @property
    def holderstr(self) -> str:
      return self._holder

  class Child(INbtPath):
    """
    stoarge a:b foo
    stoarge a:b foo.bar
    """
    def __init__(self, parent: NbtPath.INbtPath,child:str) -> None:
      super().__init__(parent)
      self._value = child

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      return self._parent.filter(Compound({self._value:value}))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.ChildMatch(self._parent,self._value,value)

    _escape_re = re.compile(r'[\[\]\{\}"\.]')

    @staticmethod
    def _escape(value:str):
      """
      nbtパスのエスケープ処理

      []{}." がある場合ダブルクオートで囲う必要がある
      
      ダブルクオート内では"と\\をエスケープする
      """
      if NbtPath.Child._escape_re.match(value):
        return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'
      return value

    @property
    def pathstr(self)->str:
      if isinstance(self._parent,NbtPath.Root):
        return self._value
      return self._parent.pathstr + '.' + self._value

  class ChildMatch(INbtPath):
    """stoarge a:b foo.bar{buz:qux}"""
    def __init__(self, parent: NbtPath.INbtPath,child:str,match:Value[Compound]) -> None:
      super().__init__(parent)
      self._value = child
      self._condition = match

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self._parent.filter(Compound({self._value:Compound.mergeValue(self._condition,value)}))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.ChildMatch(self._parent,self._value,value)

    @property
    def pathstr(self)->str:
      if isinstance(self._parent,NbtPath.Root):
        return f'{self._value}{self._condition.str()}'
      return self._parent.pathstr + '.' + self._value + self._condition.str()

  class Index(INbtPath):
    """stoarge a:b foo.bar[0]"""
    def __init__(self, parent: NbtPath.INbtPath,index:int) -> None:
      super().__init__(parent)
      self._index = index

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[{self._index}]'

  class All(INbtPath):
    """stoarge a:b  foo.bar[]"""
    def __init__(self, parent: NbtPath.INbtPath) -> None:
      super().__init__(parent)

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      if Value.isCompound(value):
        return NbtPath.AllMatch(self._parent,value)
      else:
        raise TypeError('nbt AllIndexPath cannot be match non-compound value')

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[]'

  class AllMatch(INbtPath):
    """stoarge a:b foo.bar[{buz:qux}]"""
    def __init__(self, parent: NbtPath.INbtPath,match:Value[Compound]) -> None:
      super().__init__(parent)
      self._condition = match

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return NbtPath.AllMatch(self._parent,Compound.mergeValue(self._condition,value))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[{self._condition.str()}]'

T = TypeVar('T')

class INbt:
  cls:type[Self]
  _path:NbtPath.INbtPath
  accessor:Callable[[ICommand],ICommand]|None

  def __init_subclass__(cls) -> None:
    super().__init_subclass__()
    cls.cls = cls

  def __new__(cls:type[NBT],value:NbtPath.INbtPath,type:type[NBT],accessor:Callable[[ICommand],ICommand]|None=None) -> NBT:
    result = super().__new__(cls)
    result.cls = type
    result._path = value
    result.accessor = accessor
    return result

  @property
  def path(self):
    return self._path

  def copy(self):
    return self.cls(self._path,self.cls,self.accessor)

  def _get(self,scale:float|None=None) -> ICommand:
    return Command.Data.Get(self,scale)

  def remove(self) -> ICommand:
    return Command.Data.Remove(self)

  def isMatch(self,value:Value[Self]) -> ConditionSubCommand:
    return Execute.IfNbtMatch(self,value)

  def notMatch(self,value:Value[Self]) -> ConditionSubCommand:
    return Execute.UnlessNbtMatch(self,value)

  def isExists(self) -> ConditionSubCommand:
    return Execute.IfNbt(self)

  def notExists(self) -> ConditionSubCommand:
    return Execute.UnlessNbt(self)

  def set(self,value:Value[Self]|Self) -> ICommand:
    return Command.Data.Modify.Set(self,value)

  def jsontext(self) -> _jsontextvalue:
    return self._path.to_jsontext

NBT = TypeVar('NBT',bound = INbt)
CO_NBT = TypeVar('CO_NBT',bound = INbt,covariant=True)

class Value(Generic[CO_NBT]):
  def __init__(self,type:type[CO_NBT],value:Any,tostr:Callable[[Any],str]) -> None:
    self._type = type
    self._tostr = tostr
    self.value = value
  
  def __str__(self):
    return self.str()

  def str(self):
    return self._tostr(self.value)

  @staticmethod
  def isCompound(value:Value[INbt]) -> TypeGuard[Value[Compound]]:
    return value._type is Compound

NUMBER = TypeVar('NUMBER',bound=Union[int,float])

class INbtGeneric(INbt,Generic[T]):
  @classmethod
  @abstractmethod
  def _str(cls:type[INBTG],value:T) -> Value[INBTG]:pass

  @overload
  def __new__(cls:type[INBTG],value:T) -> Value[INBTG]:pass
  @overload
  def __new__(cls:type[INBTG],value:NbtPath.INbtPath,type:type[INBTG],accessor:Callable[[ICommand],ICommand]|None=None) -> INBTG:pass
  def __new__(cls:type[INBTG],value:NbtPath.INbtPath|T,type:type[INBTG]|None=None,accessor:Callable[[ICommand],ICommand]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      if isinstance(value,NbtPath.Root|NbtPath.RootMatch):
        raise ValueError(f'nbt root cannot be {cls.__name__}')
      return super().__new__(cls,value,type,accessor)
    else:
      return cls._str(value)


INBTG = TypeVar('INBTG',bound=INbtGeneric[Any])

class INum(INbtGeneric[NUMBER]):
  mode:Literal['byte', 'short', 'int', 'long', 'float', 'double']
  _prefixmap = {'byte':'b','short':'s','int':'','long':'l','float':'f','double':'d'}
  _min:int|float
  _max:int|float

  def storeResult(self,scale:float) -> SubCommand: return Execute.StoreResultNbt(self,scale)
  def storeSuccess(self,scale:float) -> SubCommand: return Execute.StoreSuccessNbt(self,scale)
  def getValue(self,scale:float|None=None) -> ICommand:return super()._get(scale)

  @classmethod
  def _str(cls:type[INBTG],value:NUMBER) -> Value[INBTG]:
    assert issubclass(cls,INum)
    if value < cls._min or cls._max < value:
      raise ValueError(f'{cls.mode} must be in range {cls._min}..{cls._max}')
    return Value(cls.cls,value,cls._srtingifier)

  @classmethod
  def _srtingifier(cls,value:Any):
    if isinstance(value,float):
      return f'{float_to_str(value)}{cls._prefixmap[cls.mode]}'
    assert isinstance(value,int)
    return f'{value}{cls._prefixmap[cls.mode]}'

class Byte(INum[int]):
  mode = 'byte'
  _min = -2**7
  _max = 2**7-1

class Short(INum[int]):
  mode = 'short'
  _min = -2**15
  _max = 2**15-1

class Int(INum[int]):
  mode = 'int'
  _min = -2**31
  _max = 2**31-1

class Long(INum[int]):
  mode = 'long'
  _min = -2**63
  _max = 2**63-1

class Float(INum[float]):
  mode = 'float'
  _min = -3.402823e+38
  _max = 3.402823e+38

class Double(INum[float]):
  mode = 'double'
  _min = -1.797693e+308
  _max = 1.797693e+308

class Str(INbtGeneric[str]):
  @classmethod
  def _str(cls, value: str) -> Value[INbtGeneric[str]]:
    return Value(Str, value, cls._srtingifier)
  
  @classmethod
  def _srtingifier(cls,value:Any):
    assert isinstance(value,str)
    value = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{value}"'

  def getLength(self,scale:float|None=None) -> ICommand:return super()._get(scale)


class IArray(INbt,Generic[NBT]):
  _prefix:str
  _arg:type[NBT]

  def __getitem__(self,index:int) -> NBT:
    return self._arg(NbtPath.Index(self._path,index),self._arg,self.accessor)

  def all(self) -> NBT:
    return self._arg(NbtPath.All(self._path),self._arg,self.accessor)

  def getLength(self,scale:float|None=None) -> ICommand:return super()._get(scale)
  _cls_name:str

  @staticmethod
  @abstractmethod
  def _get_arg(c:type[IArray[NBT]]) -> type[NBT]:pass

  @overload
  def __new__(cls:type[ARRAY],value:list[Value[NBT]]) -> Value[ARRAY]:pass
  @overload
  def __new__(cls:type[ARRAY],value:NbtPath.INbtPath,type:type[ARRAY],accessor:Callable[[ICommand],ICommand]|None=None) -> ARRAY:pass
  def __new__(cls:type[ARRAY],value:NbtPath.INbtPath|list[Value[NBT]],type:type[ARRAY]|None=None,accessor:Callable[[ICommand],ICommand]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      if isinstance(value,NbtPath.Root|NbtPath.RootMatch):
        raise ValueError(f'nbt root cannot be {cls._cls_name}')
      result = super().__new__(cls,value,type,accessor)
      result._arg = cls._get_arg(type)
      return result
    else:
      return Value[cls](cls,value,cls._stringify)

  @classmethod
  def _stringify(cls, value: Any):
    vlu: list[Value[NBT]] = value
    return f"[{cls._prefix}{','.join(v.str() for v in vlu)}]"

ARRAY = TypeVar('ARRAY',bound=IArray[Any])

class List(IArray[NBT]):
  _prefix=''

  @staticmethod
  def _get_arg(c:type[IArray[NBT]]) -> type[NBT]:
    return get_args(c)[0]

  def filterAll(self:List[Compound],compound:Value[Compound]) -> Compound:
    return self._arg(NbtPath.AllMatch(self._path,compound),self._arg,self.accessor)

class ByteArray(IArray[Byte]):
  _prefix='B;'

  @staticmethod
  def _get_arg(c:type[IArray[Byte]]) -> type[Byte]:
    return Byte

class IntArray(IArray[Int]):
  _prefix='I;'

  @staticmethod
  def _get_arg(c:type[IArray[Int]]) -> type[Int]:
    return Int

class Compound(INbt):
  @overload
  def __new__(cls,value:dict[str,Value[INbt]]) -> Value[Compound]:pass
  @overload
  def __new__(cls,value:NbtPath.INbtPath,type:type[Compound],accessor:Callable[[ICommand],ICommand]|None=None) -> Compound:pass
  def __new__(cls,value:NbtPath.INbtPath|dict[str,Value[INbt]],type:type[Compound]|None=None,accessor:Callable[[ICommand],ICommand]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      return super().__new__(cls,value,type,accessor)
    else:
      return Value(cls, value,cls._stringify)

  @classmethod
  def _stringify(cls, value: Any):
    vlu: dict[str,Value[INbt]] = value
    return f"{{{','.join( f'{k}:{v.str()}' for k,v in vlu.items())}}}"

  _escape_re = re.compile(r'[0-9a-zA-Z_\.-]+')
  @staticmethod
  def _escape_key(value:str):
    if value == "":
      raise ValueError('empty string is not allowed for Compound key')
    if Compound._escape_re.fullmatch(value):
      return value
    if '"' in value:
      return "'" + value.replace('\\','\\\\').replace("'","\\'") + "'"
    return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'


  @overload
  def __getitem__(self,value:str) -> Compound:pass
  @overload
  def __getitem__(self,value:type[NBT]) -> NBT:pass
  @overload
  def __getitem__(self,value:tuple[str,type[NBT]]) -> NBT:pass
  def __getitem__(self,value:str|type[NBT]|tuple[str,type[NBT]]):
    """子要素 self.child"""
    match value:
      case str():
        result = Compound(NbtPath.Child(self._path,value),Compound,self.accessor)
      case (name,r):
        result = r(NbtPath.Child(self._path,name),r,self.accessor)
      case _:
        result = value(NbtPath.Child(self._path,gen_id(prefix=':')),value,self.accessor)
    return result


  def childMatch(self,child:str,match:Value[Compound]):
    """条件付き子要素 self.child{foo:bar}"""
    return Compound(NbtPath.ChildMatch(self._path,child,match),Compound)

  def getLength(self,scale:float|None=None) -> ICommand:return super()._get(scale)

  @staticmethod
  def mergeValue(v1:Value[Compound],v2:Value[Compound]):
    value1:dict[str,Value[INbt]] = v1.value
    value2:dict[str,Value[INbt]] = v2.value
    result = {**value1}
    for k,v in value2.items():
      if Value.isCompound(v) and k in value1:
        w = value1[k]
        if Value.isCompound(w):
          result[k] = Compound.mergeValue(w,v)
        else:
          result[k] = v
      else:
        result[k] = v
    return Compound(result)

COMPOUNDVALUE = TypeVar('COMPOUNDVALUE',bound=Value[Compound])
COMPOUND = TypeVar('COMPOUND',bound=Compound)

class StorageNbt:
  def __new__(cls,name:str) -> Compound:
    return Compound(NbtPath.Root('storage',name),Compound)

class BlockNbt:
  def __new__(cls,position:Position.IPosition) -> Compound:
    return Compound(NbtPath.Root('block',position.expression()),Compound)

class EntityNbt:
  def __new__(cls,selector:ISelector) -> Compound:
    return Compound(NbtPath.Root('entity',selector.expression()),Compound)

_pydp_storage = StorageNbt('pydp:')



class IScoreHolder:
  @abstractmethod
  def expression(self) -> str:
    pass

  def __str__(self) -> str:
    return self.expression()

class ISelector(IScoreHolder):

  def IfEntity(self):
    return Execute.IfEntity(self)

  def UnlessEntity(self):
    return Execute.UnlessEntity(self)
  
  def As(self):
    return Execute.As(self)
  
  def At(self):
    return Execute.At(self)

  def PositionedAs(self):
    return Execute.PositionedAs(self)

  def FacingEntity(self):
    return Execute.FacingEntity(self)

  def RotatedAs(self):
    return Execute.RotatedAs(self)

  @property
  def nbt(self):
    return EntityNbt(self)

  def score(self,objective:Objective):
    return Scoreboard(objective,self)

  def myDat(self):
    return OhMyDat.getData(self)

  def TagAdd(self,id:str):
    return Command.Tag.Add(self,id)

  def TagRemove(self,id:str):
    return Command.Tag.Remove(self,id)

  def TagList(self):
    return Command.Tag.List(self)

  def jsontext(self) -> _jsontextvalue:
    return {"selector":self.expression()}

  @abstractmethod
  def isSingle(self) -> bool:
    """
    limit=1 などで該当エンティティが一体のみであることが保証されているかどうか
    """
    pass

class ScoreHolder(IScoreHolder):
  """
  存在しないが、スコアを持つダミーエンティティ

  `$`や`#`等プレイヤー名に使えない文字から始めるとよい
  """
  def __init__(self,name:str) -> None:
    super().__init__()
    self.name = name
  
  def expression(self) -> str:
    return self.name

class Objective:
  """
  スコアボードのobjective

  idはスコアボード名
  """  
  @staticmethod
  def List():
    return Command.Scoreboard.Objectives.List()

  def __init__(self,id:str) -> None:
    self.id = id
    
  def Add(self,condition:str='dummy',display:str|None=None):
    """
    スコアボードを追加する

    display:
      表示名
    """
    return Command.Scoreboard.Objectives.Add(self,condition,display)
  
  def Remove(self):
    """
    スコアボードを削除する
    """
    return Command.Scoreboard.Objectives.Remove(self)

  def Setdisplay(self,slot:str):
    """
    スコアボードを表示する

    slot:
      "sidebar" 等
    """
    return Command.Scoreboard.Objectives.Setdisplay(self,slot)

  def ModifyDisplayname(self,display:str):
    """
    スコアボードの表示名を変更する

    display:
      表示名
    """
    return Command.Scoreboard.Objectives.Modify.Displayname(self,display)

  def ModifyRendertype(self,rendertype: Literal['hearts', 'integer']):
    """
    スコアボードの表示名を変更する

    display:
      表示名
    """
    return Command.Scoreboard.Objectives.Modify.Rendertype(self,rendertype)

  def score(self,entity:IScoreHolder|None):
    """
    エンティティのスコアを取得
    """
    return Scoreboard(self,entity)

class Scoreboard:
  @staticmethod
  def List(entity:IScoreHolder|None):
    """ 
    エンティティに紐づいたスコアボード一覧を取得

    entity:
      None -> すべてのエンティティを対象にする
    """
    return Command.Scoreboard.Players.List(entity)
  
  def expression(self):
    if self.entity is None:
      return f'* {self.objective.id}'
    return f'{self.entity.expression()} {self.objective.id}'

  def __init__(self,objective:Objective,entity:IScoreHolder|None) -> None:
    """ None:すべてのエンティティを対象にする """
    self.objective = objective
    self.entity = entity

  def Get(self):
    assert self.entity
    return Command.Scoreboard.Players.Get(self)

  def Set(self,value:int):
    return Command.Scoreboard.Players.Set(self,value)

  def Add(self,value:int) -> ICommand:
    if value <= -1:
      return Command.Scoreboard.Players.Remove(self,-value)
    return Command.Scoreboard.Players.Add(self,value)

  def Remove(self,value:int) -> ICommand:
    if value <= -1:
      return Command.Scoreboard.Players.Add(self,-value)
    return Command.Scoreboard.Players.Remove(self,value)
  
  def Reset(self):
    return Command.Scoreboard.Players.Reset(self)
  
  def Enable(self):
    return Command.Scoreboard.Players.Enable(self)
  
  def Oparation(self,operator:Literal['+=','-=','*=','/=','%=','=','<','>','><'],other:Scoreboard):
    return Command.Scoreboard.Players.Operation(self,operator,other)

  def StoreResult(self):
    return Execute.StoreResultScore(self)
  
  def StoreSuccess(self):
    return Execute.StoreSuccessScore(self)

  def IfMatch(self,start:int,stop:int|None=None):
    return Execute.IfScoreMatch(self,start,stop)

  def UnlessMatch(self,start:int,stop:int|None=None):
    return Execute.UnlessScoreMatch(self,start,stop)

  def If(self,target:Scoreboard,operator:Literal['<', '<=', '=', '>=', '>']):
    return Execute.IfScore(self,target,operator)

  def Unless(self,target:Scoreboard,operator:Literal['<', '<=', '=', '>=', '>']):
    return Execute.UnlessScore(self,target,operator)

  def jsontext(self) -> _jsontextvalue:
    assert self.entity is not None
    return {'score':{'name':self.entity.expression(),'objective':self.objective.id}}

class ItemTag:
  pass

class Item:
  @staticmethod
  def customModel(id:str,modeldata:int):
    return Item(id,{'CustomModelData':Int(modeldata)})

  def __init__(self,id:str|McPath,nbt:dict[str,Value[INbt]]|None=None) -> None:
    """
    アイテム

    blockstates:
      {"axis":"x"} / ...

    nbt:
      {"Items":List[Compound]\\([])} / ...
    """
    self.id = McPath(id)
    self.nbt = nbt

  def Give(self,count:int):
    return Command.Give(self,count)

  def expression(self):
    result = self.id.str
    if self.nbt is not None:
      result += Compound(self.nbt).str()
    return result

  def ToNbt(self,count:int|None=None):
    """
    {"id":"minecraft:stone","Count":1b,"tag":{}}
    """
    value:dict[str, Value[INbt]] = {'id':Str(self.id.str)}
    if count:
      value['Count'] = Byte(count)
    if self.nbt is not None:
      value['tag'] = Compound(self.nbt)
    return Compound(value)

  def withNbt(self,nbt:dict[str,Value[INbt]]):
    nbt = self.nbt|nbt if self.nbt is not None else nbt
    return Item(self.id,nbt)

class Block:
  def __init__(self,id:str|McPath,blockstates:dict[str,str]={},nbt:dict[str,Value[INbt]]|None=None) -> None:
    """
    ブロック/ブロックタグ

    id:
      "minecraft:stone" / "#logs"  / ...

    blockstates:
      {"axis":"x"} / ...

    nbt:
      {"Items":List[Compound]\\([])} / ...
    """
    self.id = McPath(id)
    self.blockstates = blockstates
    self.nbt = nbt

  def SetBlock(self,pos:Position.IPosition):
    if self.id.istag:
      raise ValueError(f'cannot set blocktag: {self.expression()}')
    return Command.SetBlock(self,pos)

  def IfBlock(self,pos:Position.IPosition):
    return Execute.IfBlock(pos,self)

  def expression(self):
    result = self.id.str
    if self.blockstates:
      result += f'[{",".join( f"{k}={v}" for k,v in self.blockstates.items())}]'
    if self.nbt is not None:
      result += Compound(self.nbt).str()
    return result

  def withNbt(self,nbt:dict[str,Value[INbt]]):
    nbt = self.nbt|nbt if self.nbt is not None else nbt
    return Block(self.id,self.blockstates,nbt)

  def withStates(self,blockstates:dict[str,str]):
    blockstates = self.blockstates|blockstates
    return Block(self.id,blockstates,self.nbt)

@runtime_checkable
class _IJsonTextable(Protocol):
  @abstractmethod
  def jsontext(self) -> _jsontextvalue:pass

def evaljsontext(jsontext:jsontext) -> _jsontextvalue:
  match jsontext:
    case str():
      return jsontext
    case _IJsonTextable():
      return jsontext.jsontext()
    case list():
      return list(map(evaljsontext,jsontext))

jsontext:TypeAlias = str|_IJsonTextable|list['jsontext']

_jsontextvalue:TypeAlias = str|list['_jsontextvalue']|dict[str,Union[dict[str,str|dict[str,str]],bool,'_jsontextvalue']]

class JsonText:
  class Decotation:
    """
    tellrawや看板で使うjsontextを装飾する
    """
    def __init__(
        self,
        value:jsontext,
        color:str|None=None,
        font:str|None=None,
        bold:bool|None=None,
        italic:bool|None=None,
        underlined:bool|None=None,
        strikethrough:bool|None=None,
        obfuscated:bool|None=None,
        insertion:str|None=None,
        click_run_command:ICommand|None=None,
        click_suggest_command:ICommand|str|None=None,
        click_copy_to_clipboard:str|None=None,
        click_open_url:str|None=None,
        click_change_page:int|None=None,
        hover_show_text:str|None=None,
        hover_show_item:Item|None=None,
        hover_show_entity:tuple[str,str,str]|None=None,
      ) -> None:
      """
      color: '#000000','reset','black','dark_blue','dark_green','dark_aqua','dark_red','dark_purple','gold','gray','dark_gray','blue','green','aqua','red','light_purple','yellow','white'

      click_run_command / click_suggest_command / click_copy_to_clipboard / click_open_url / click_change_page はどれか1つまで

      hover_show_text / hover_show_item / hover_show_entity はどれか1つまで
      """
      self.value = value
      self.color = color
      self.font = font
      self.bold = bold
      self.italic = italic
      self.underlined = underlined
      self.strikethrough = strikethrough
      self.obfuscated = obfuscated
      self.insertion = insertion
      self.click_run_command = click_run_command
      self.click_suggest_command = click_suggest_command
      self.click_copy_to_clipboard = click_copy_to_clipboard
      self.click_open_url = click_open_url
      self.click_change_page = click_change_page
      self.hover_show_text = hover_show_text
      self.hover_show_item = hover_show_item
      self.hover_show_entity = hover_show_entity

    def jsontext(self) -> _jsontextvalue:
      jtext = evaljsontext(self.value)
      match jtext:
        case str():
          value:_jsontextvalue = {"text":""}
          result = value
        case list():
          value:_jsontextvalue = {"text":""}
          jtext.insert(0,value)
          result = jtext
        case _:
          value = jtext
          result = value

      def setValue(key:str,v:bool|str|None):
        if v is not None:
          value[key] = v

      setValue('color',self.color)
      setValue('font',self.font)
      setValue('bold',self.bold)
      setValue('italic',self.italic)
      setValue('underlined',self.underlined)
      setValue('strikethrough',self.strikethrough)
      setValue('obfuscated',self.obfuscated)
      setValue('insertion',self.insertion)

      if self.click_run_command:
        value["clickEvent"] = {"action":"run_command","value":self.click_run_command.export()}
      elif self.click_suggest_command:
        cmd = self.click_suggest_command
        if isinstance(cmd,ICommand):
          cmd = cmd.export()
        value["clickEvent"] = {"action":"suggest_command","value":cmd}
      elif self.click_copy_to_clipboard:
        value["clickEvent"] = {"action":"copy_to_clipboard","value":self.click_copy_to_clipboard}
      elif self.click_open_url:
        value["clickEvent"] = {"action":"open_url","value":self.click_open_url}

      if self.hover_show_text:
        value["hoverEvent"] = {"action":"show_text","contents":self.hover_show_text}
      elif self.hover_show_item:
        raise NotImplementedError('hover_show_item is not implemented')
      elif self.hover_show_entity:
        value["hoverEvent"] = {"action":"show_entity","contents":{
          "name":self.hover_show_entity[0],
          "type":self.hover_show_entity[1],
          "id":self.hover_show_entity[2]
        }}
      return result

  class Translate:
    """
    tellrawや看板で使うjsontextのtranslate
    """
    def __init__(self,key:str,with_:list[jsontext]) -> None:
      self.key = key
      self.with_ = with_

    def jsontext(self) -> _jsontextvalue:
      return {"translate":self.key,"with": list(map(evaljsontext,self.with_))}

  class Keybind:
    """
    tellrawや看板で使うjsontextのkeybind
    """
    def __init__(self,key:str) -> None:
      self.key = key

    def jsontext(self) -> _jsontextvalue:
      return {"keybind":self.key}















# 本来は別ファイルとしてdatapack.libralyに格納すべきだが、
# 組み込んでおいたほうがエンティティセレクタから呼び出せて便利なので組み込む
class OhMyDat(IDatapackLibrary):
  using = False
  PleaseMyDat = ExternalFunctionTag('#oh_my_dat:please')
  PleaseItsDat = ExternalFunctionTag('#oh_its_dat:please')

  @classmethod
  def install(cls, datapack_path: Path, datapack_id: str) -> None:
    if not (datapack_path.parent/"OhMyDat").exists():
      print("installing OhMyDat")
      cp = subprocess.run(['git', 'clone', 'https://github.com/Ai-Akaishi/OhMyDat.git'],cwd=datapack_path.parent, encoding='utf-8', stderr=subprocess.PIPE)
      if cp.returncode != 0:
        raise ImportError(cp.stderr)

  @classmethod
  def uninstall(cls,datapack_path:Path) -> None:
    if (datapack_path.parent/"OhMyDat").exists():
      print("uninstalling OhMyDat")
      cls.rmtree(datapack_path.parent/"OhMyDat")

  @classmethod
  def Please(cls,holder:Scoreboard|ISelector|ICommand|None=None):
    """
    scoreboardのidのデータ空間にアクセス

    OhMyDat.getData で生成したデータから自動で呼ばれるため、基本的に明示的に呼ぶ必要はない

    holder : データ保持者

    +  None : 実行者本人

    +  ISelector : エンティティセレクタ (データを持っているエンティティ)

    +  Scoreboard : スコアボードの値のIDを持つエンティティ

    +  ICommand : コマンドの実行結果のIDをもつエンティティ
    """
    cls.using = True
    match holder:
      case None:
        return Command.Function(cls.PleaseMyDat)
      case ISelector():
        return holder.As() + Command.Function(cls.PleaseMyDat)
      case Scoreboard():
        f = Function()
        f += cls._scoreboard.Oparation('=',holder)
        f += Command.Function(cls.PleaseItsDat)
        return f.Call()
      case ICommand():
        f = Function()
        f += cls._scoreboard.StoreResult() + holder
        f += Command.Function(cls.PleaseItsDat)
        return f.Call()

  _storage = StorageNbt('oh_my_dat:')
  _data = _storage['_',List[List[List[List[List[List[List[List[Compound]]]]]]]]][-4][-4][-4][-4][-4][-4][-4][-4]

  @staticmethod
  def _accessor(cmd:ICommand):
    f = Function()
    f += OhMyDat.Please()
    f += cmd
    return f.Call()

  _data_self = _data.copy()
  _data_self.accessor = _accessor

  _scoreboard = Scoreboard(Objective('OhMyDatID'),ScoreHolder('_'))

  @classmethod
  def getData(cls,holder:Scoreboard|ISelector|None=None):
    """
    エンティティに紐づいたデータ空間を返す

    データへのアクセス直前に #oh_my_dat:please / #oh_its_dat:please が自動的に呼ばれる

    holder : データ保持者

    +  Scoreboard : エンティティID (OhMyDat.PleaseScore の引数と同じ)

    +  ISelector : エンティティセレクタ (データを持っているエンティティ)

    +  None : 実行者本人

    +  ICommand : コマンドの実行結果のIDをもつエンティティ
    """
    cls.using = True
    match holder:
      case None:
        return cls._data_self
      case _:
        def _accessor(cmd:ICommand):
          f = Function()
          f += OhMyDat.Please(holder)
          f += cmd
          return f.Call()
        d = cls._data.copy()
        d.accessor = _accessor
        return d

  @classmethod
  def getDataUnsafe(cls):
    """
    エンティティに紐づいたデータ空間を返す

    データへのアクセス時に #oh_my_dat:please / #oh_its_dat:please が呼ばれず、

    どのエンティティに紐づいているかが文脈依存であるため原則使用しない

    紐づいているエンティティが確実に一意である状況でのみ使用可能

    どのエンティティのデータなのかはそれまでに呼ばれた #oh_my_dat:please / #oh_its_dat:please に左右される
    """
    return cls._data

  # @classmethod
  # def Release(cls):
  #   """
  #   明示的にストレージを開放

  #   他のデータパックのデータを消してしまう恐れがあるため使わない
  #   """
  #   cls.using = True
  #   return Command.Function('#oh_my_dat:release')

class IPredicate:
  predicates:list[IPredicate] = []
  def __init__(self,path:str|McPath|None=None) -> None:
    IPredicate.predicates.append(self)
    self._path = McPath(path)

  def export(self,datapack_path:Path):
    path = self.path.predicate(datapack_path)
    Datapack.mkdir(path)
    path.write_text(
      json.dumps(self.export_dict()),
      encoding='utf8'
    )

  @property
  def path(self):
    if self._path is None:
      self._path = Datapack.default_path/gen_id(upper=False,length=24)
    else:
      self._path
    return self._path

  @abstractmethod  
  def export_dict(self) -> dict[str,Any]:
    pass

class IRecipe:
  _type:str
  recipes:list[IRecipe] = []
  def __init__(self,path:str|McPath|None=None,group:str|None=None) -> None:
    IRecipe.recipes.append(self)
    self._group = group
    self._path = McPath(path)

  def export(self,datapack_path:Path):
    path = self.path.recipe(datapack_path)
    Datapack.mkdir(path)

    obj = self.export_dict()
    obj |= { 'type':self._type }
    if self._group is not None: obj['group'] = self._group

    path.write_text(
      json.dumps(obj),
      encoding='utf8'
    )

  @property
  def path(self):
    if self._path is None:
      self._path = Datapack.default_path/gen_id(upper=False,length=24)
    else:
      self._path
    return self._path

  @abstractmethod
  def export_dict(self) -> dict[str,Any]:
    pass
