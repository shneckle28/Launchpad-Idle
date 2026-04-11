"""
MIDI output via Windows WinMM (winmm.dll) using ctypes.
Sends only the inner 8x8 pad grid — exactly the layout that was proven working.
"""
import ctypes
import ctypes.wintypes as wt
import time

_winmm = ctypes.windll.winmm

MMSYSERR_NOERROR = 0
CALLBACK_NULL    = 0
MHDR_DONE        = 0x00000001

GRID_SIZE    = 10
CORNERS      = {(0, 0), (0, 9), (9, 0), (9, 9)}   # only the 4 physical corners have no pad
INVALID_PADS = CORNERS                              # left col (notes x0) DOES exist on LP Pro


class _MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid",           wt.WORD),
        ("wPid",           wt.WORD),
        ("vDriverVersion", wt.UINT),
        ("szPname",        ctypes.c_wchar * 32),
        ("wTechnology",    wt.WORD),
        ("wVoices",        wt.WORD),
        ("wNotes",         wt.WORD),
        ("wChannelMask",   wt.WORD),
        ("dwSupport",      wt.DWORD),
    ]


class _MIDIHDR(ctypes.Structure):
    pass

_MIDIHDR._fields_ = [
    ("lpData",          ctypes.c_char_p),
    ("dwBufferLength",  wt.DWORD),
    ("dwBytesRecorded", wt.DWORD),
    ("dwUser",          ctypes.c_size_t),
    ("dwFlags",         wt.DWORD),
    ("lpNext",          ctypes.c_void_p),
    ("reserved",        ctypes.c_size_t),
    ("dwOffset",        wt.DWORD),
    ("dwReserved",      ctypes.c_size_t * 4),
]

assert ctypes.sizeof(_MIDIHDR) == 88


def list_output_devices():
    devices = []
    for i in range(_winmm.midiOutGetNumDevs()):
        caps = _MIDIOUTCAPSW()
        if _winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
            devices.append((i, caps.szPname))
    return devices


class LaunchpadPro:
    def __init__(self):
        self._handle   = wt.HANDLE(0)
        self.connected = False

    def connect(self, device_id):
        try:
            self.disconnect(clear=False)
            handle = wt.HANDLE(0)
            r = _winmm.midiOutOpen(ctypes.byref(handle), device_id, 0, 0, CALLBACK_NULL)
            if r != MMSYSERR_NOERROR:
                return False, f"midiOutOpen failed (error {r})"
            self._handle   = handle
            self.connected = True
            self.clear()
            return True, "Connected"
        except Exception as exc:
            self.connected = False
            return False, str(exc)

    def disconnect(self, clear=True):
        if clear:
            self.clear()
        if self.connected:
            _winmm.midiOutClose(self._handle)
            self._handle   = wt.HANDLE(0)
            self.connected = False

    def set_grid(self, grid):
        """
        Send the full Launchpad Pro pad layout from a 10x10 animation grid.

        10x10 grid layout:
          Row 0,  cols 1-8  -> top border    (notes 91-98)
          Rows 1-8, col 9   -> right border  (notes 89,79,...,19)
          Row 9,  cols 1-8  -> bottom border (notes 1-8)
          Rows 1-8, cols 1-8 -> inner 8x8   (notes 11-88, proven working)
          Col 0 and corners  -> no pad, skipped
        """
        if not self.connected:
            return

        # --- Inner 8x8 (proven working) — sent first, separate message ---
        inner = bytearray([0xF0, 0x00, 0x20, 0x29, 0x02, 0x10, 0x0B])
        for anim_row in range(8):
            for anim_col in range(8):
                r, g, b = grid[anim_row + 1][anim_col + 1]
                note = (8 - anim_row) * 10 + (anim_col + 1)
                inner += bytes([note, self._to63(r), self._to63(g), self._to63(b)])
        inner.append(0xF7)
        self._sysex(bytes(inner))

        # --- Border buttons — separate message so any bad note can't kill inner ---
        border = bytearray([0xF0, 0x00, 0x20, 0x29, 0x02, 0x10, 0x0B])
        # Top row (row 0, cols 1-8) -> notes 91-98
        for col in range(1, 9):
            r, g, b = grid[0][col]
            border += bytes([90 + col, self._to63(r), self._to63(g), self._to63(b)])
        # Right col (rows 1-8, col 9) -> notes 89, 79, ... 19
        for anim_row in range(8):
            r, g, b = grid[anim_row + 1][9]
            note = (8 - anim_row) * 10 + 9
            border += bytes([note, self._to63(r), self._to63(g), self._to63(b)])
        # Bottom row (row 9, cols 1-8) -> notes 1-8
        for col in range(1, 9):
            r, g, b = grid[9][col]
            border += bytes([col, self._to63(r), self._to63(g), self._to63(b)])
        # Left col (rows 1-8, col 0) -> notes 80, 70, ... 10
        for anim_row in range(8):
            r, g, b = grid[anim_row + 1][0]
            note = (8 - anim_row) * 10
            border += bytes([note, self._to63(r), self._to63(g), self._to63(b)])
        border.append(0xF7)
        self._sysex(bytes(border))

    def clear(self):
        if not self.connected:
            return
        self.set_grid([[(0, 0, 0)] * GRID_SIZE for _ in range(GRID_SIZE)])

    def _sysex(self, data: bytes):
        buf = ctypes.create_string_buffer(data, len(data))
        hdr = _MIDIHDR()
        hdr.lpData          = ctypes.cast(buf, ctypes.c_char_p)
        hdr.dwBufferLength  = len(data)
        hdr.dwBytesRecorded = len(data)
        hdr.dwFlags         = 0

        r = _winmm.midiOutPrepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
        if r != 0:
            print(f"[MIDI] PrepareHeader error {r}")
            self.connected = False
            return

        r = _winmm.midiOutLongMsg(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
        if r != 0:
            print(f"[MIDI] LongMsg error {r}")
            _winmm.midiOutUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            self.connected = False
            return

        deadline = time.perf_counter() + 1.0
        while not (hdr.dwFlags & MHDR_DONE) and time.perf_counter() < deadline:
            time.sleep(0.001)

        _winmm.midiOutUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))

    @staticmethod
    def _to63(v):
        return min(63, max(0, int(v * 63 / 255)))
