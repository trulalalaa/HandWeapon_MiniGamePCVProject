import ctypes
import os
import threading

winmm = ctypes.windll.winmm

def _mci(command: str) -> str:
    buf = ctypes.create_unicode_buffer(256)
    err = winmm.mciSendStringW(command, buf, 255, 0)
    if err:
        return ""
    return buf.value

def _play_async(alias: str, filepath: str, loop: bool):
    _mci(f'stop {alias}')
    _mci(f'close {alias}')
    _mci(f'open "{filepath}" type mpegvideo alias {alias}')
    cmd = f'play {alias} repeat' if loop else f'play {alias}'
    _mci(cmd)

def play(alias: str, filepath: str, loop: bool = False):
    filepath = os.path.abspath(filepath)
    t = threading.Thread(target=_play_async, args=(alias, filepath, loop), daemon=True)
    t.start()

def stop(alias: str):
    _mci(f'stop {alias}')
    _mci(f'close {alias}')

def is_playing(alias: str) -> bool:
    status = _mci(f'status {alias} mode')
    return status == 'playing'
