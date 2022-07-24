from pathlib import Path
import shutil
import subprocess
from datapack import Command, FunctionTag, IDatapackLibrary

class ItemFrameHook(IDatapackLibrary):
  @classmethod
  def install(cls,datapack_path:Path) -> None:
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
      return Command.CallFunc('ifh:api/'+'_'.join(name))
    else:
      return Command.CallFunc('ifh:api/none')

  OnOut = FunctionTag('ifh','on_out')
  OnIn  = FunctionTag('ifh','on_in')
  OnRot  = FunctionTag('ifh','on_rot')