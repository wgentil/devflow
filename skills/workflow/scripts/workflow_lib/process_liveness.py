"""Conservative launcher liveness probes for orphan reconciliation."""
import os


def process_alive(pid):
    """Return False only when the recorded process is definitively gone."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False if ctypes.get_last_error() == 87 else None  # ERROR_INVALID_PARAMETER
        try:
            result = kernel.WaitForSingleObject(handle, 0)
            if result == 0:  # WAIT_OBJECT_0
                return False
            if result == 0x102:  # WAIT_TIMEOUT
                return True
            return None
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    return True
