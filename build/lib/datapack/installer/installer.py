from pathlib import Path
from random import randint
from datapack.datapack import Command, Function, FunctionTag, IDatapackLibrary, StorageNbt, Str
from datapack.mcpath import McPath
from datapack.selector import Selector

_id_upper = tuple(map(chr, range(ord('A'), ord('Z')+1)))
_id_lower = tuple(map(chr, range(ord('a'), ord('z')+1)))
_id_number = tuple(map(chr, range(ord('0'), ord('9')+1)))

def _gen_id(length: int = 8, prefix: str = '', suffix: str = '', upper: bool = True, lower: bool = True, number: bool = True):
  """{length=8}桁のIDを生成する [0-9a-zA-Z]"""
  chars: list[str] = []
  if upper:
    chars.extend(_id_upper)
  if lower:
    chars.extend(_id_lower)
  if number:
    chars.extend(_id_number)
  maxidx = len(chars) - 1
  return prefix + ''.join(chars[randint(0, maxidx)] for _ in range(length)) + suffix

build_id = _gen_id(16,upper=False)
def setBuildId(id:str):
  global build_id
  build_id = id


class Installer(IDatapackLibrary):
  _uninstall_all_func = Function()
  OnInstall = Function(commands=[_uninstall_all_func.Call()])
  OnUninstall = Function()

  @classmethod
  def install(cls, datapack_path: Path, datapack_id: str) -> None:
    build_nbt = StorageNbt(f'{datapack_id}:install')['build_id', Str]

    install_mcpath = McPath(f'{datapack_id}:install')
    uninstall_mcpath = McPath(f'{datapack_id}:uninstall')
    uninstall_funcs_mcpath = McPath(f'{datapack_id}:core/uninstall')

    # installの解決
    cls.OnInstall.set_path(install_mcpath)
    load = Function()
    load += build_nbt.notMatch(Str(build_id)) + cls.OnInstall.Call()
    cls.OnInstall += build_nbt.set(Str(build_id))
    cls.OnInstall += Command.Tellraw(Selector.A(),f"[{datapack_id}] installed build_id={build_id}")
    FunctionTag.load.append(load)

    cls.OnUninstall += Command.Tellraw(Selector.A(),f"[{datapack_id}] uninstalled build_id={build_id}")
    cls.OnUninstall.set_path(uninstall_funcs_mcpath/build_id)
    cls.OnUninstall.delete_on_regenerate = False

    # uninstall_all
    uninstalls_path = uninstall_funcs_mcpath.function_dir(datapack_path)
    if uninstalls_path.exists():
      for func in uninstalls_path.iterdir():
        if func.suffix == '.mcfunction':
          if func.stem == build_id:
            raise ValueError(f'build_id {build_id} is not unique id')
          cls._uninstall_all_func += build_nbt.isMatch(Str(func.stem)) + Command.Function(uninstall_funcs_mcpath/func.stem)

    # uninstallの解決
    cls.OnUninstall = Function(uninstall_mcpath)

    cls.OnUninstall += build_nbt.isMatch(Str(build_id)) + cls.OnUninstall.Call()

    cls.OnUninstall += build_nbt.remove()
