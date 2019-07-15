from pymoku.version import *

def build_is_compatible(moku):
    # Check firmware versions
    moku_fw = moku.get_firmware_build()
    pymoku_fw = compat_fw[0]

    if moku_fw == 65535:
        return None # Development build, unable to determine

    return moku_fw == pymoku_fw

def patch_is_compatible(moku):
    return set(moku._list_running_packs()) == set(compat_packs)

def firmware_is_compatible(moku):
    return build_is_compatible(moku) and patch_is_compatible(moku)

def list_compatible_firmware():
    return compat_fw
