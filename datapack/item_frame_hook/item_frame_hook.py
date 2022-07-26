from pathlib import Path
import shutil
import subprocess
from typing import Literal
from datapack.datapack import ExternalFunction, FunctionTag, IDatapackLibrary
from datapack.selector import Selector

class ItemFrameHook(IDatapackLibrary):
  @classmethod
  def install(cls,datapack_path:Path,datapack_id:str) -> None:
    if not (datapack_path.parent/"ItemFrameHook").exists():
      print("installing ItemFrameHook")
      cp = subprocess.run(['git', 'clone', 'https://github.com/txkodo/ItemFrameHook.git'],cwd=datapack_path.parent, encoding='utf-8', stderr=subprocess.PIPE)
      if cp.returncode != 0:
        raise ImportError(cp.stderr)

  @classmethod
  def uninstall(cls,datapack_path:Path) -> None:
    if (datapack_path.parent/"ItemFrameHook").exists():
      print("uninstalling ItemFrameHook")
      shutil.rmtree(datapack_path.parent/"ItemFrameHook")

  @classmethod
  def ChangeState(cls,i:bool,o:bool,r:bool):
    name:list[str] = []
    if i:name.append('in')
    if o:name.append('out')
    if r:name.append('rot')
    if name:
      return ExternalFunction('ifh:api/'+'_'.join(name)).Call()
    else:
      return ExternalFunction('ifh:api/none').Call()

  @classmethod
  def CounterClockWise(cls):
    return ExternalFunction('ifh:api/counterclockwise').Call()

  @classmethod
  def RotationSelectorS(cls,rotation:Literal[0,1,2,3,4,5,6,7]):
    return Selector.S(tag=f'ifh.{rotation}')

  @classmethod
  def RotationSelectorE(cls,rotation:Literal[0,1,2,3,4,5,6,7]):
    return Selector.E(tag=f'ifh.{rotation}')

  OnOut = FunctionTag('#ifh:on_out')
  OnIn  = FunctionTag('#ifh:on_in')
  OnRot  = FunctionTag('#ifh:on_rot')
