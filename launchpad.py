"""
MIDI output via Windows WinMM (winmm.dll) using ctypes.
Supports multiple Launchpad models via device name auto-detection.
"""
import ctypes
import ctypes.wintypes as wt
import time

_winmm = ctypes.windll.winmm

MMSYSERR_NOERROR = 0
CALLBACK_NULL    = 0
MHDR_DONE        = 0x00000001

GRID_SIZE = 10
CORNERS   = {(0, 0), (0, 9), (9, 0), (9, 9)}


# ---------------------------------------------------------------------------
# Device profiles  (most-specific match listed first)
#
# gen 2 (MK2, Pro):     cmd=0x0B, color 0-63, no per-LED type byte
# gen 3 (X, Mini MK3, Pro MK3): cmd=0x03, color 0-127, type byte 0x01 per LED
#
# top_base   – MIDI note for top-row col 1; remaining cols are base+1 … base+7
# has_left   – device has left-column buttons (col 0, rows 1-8)
# has_bottom – device has bottom-row buttons  (row 9, cols 1-8)
# ---------------------------------------------------------------------------
PROFILES = [
    dict(name="Launchpad Pro MK3",  match=["pro mk3"],      sysex_id=0x23, gen=3,
         has_left=True,  has_bottom=True,  top_base=91),
    dict(name="Launchpad X",        match=["launchpad x"],  sysex_id=0x0C, gen=3,
         has_left=False, has_bottom=False, top_base=91),
    dict(name="Launchpad Mini MK3", match=["mini mk3"],     sysex_id=0x0D, gen=3,
         has_left=False, has_bottom=False, top_base=91),
    dict(name="Launchpad MK2",      match=["mk2"],          sysex_id=0x18, gen=2,
         has_left=False, has_bottom=False, top_base=104),
    dict(name="Launchpad Pro",      match=["pro"],          sysex_id=0x10, gen=2,
         has_left=True,  has_bottom=True,  top_base=91),
    dict(name="Generic Launchpad",  match=[],               sysex_id=0x10, gen=2,
         has_left=True,  has_bottom=True,  top_base=91),
]


def auto_detect_profile(device_name: str) -> dict:
    """Return the best-matching profile for the given MIDI device name."""
    lower = device_name.lower()
    for profile in PROFILES:
        if any(term in lower for term in profile["match"]):
            return profile
    return PROFILES[-1]  # Generic fallback


# ---------------------------------------------------------------------------
# WinMM structures
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main device class
# ---------------------------------------------------------------------------
class LaunchpadDevice:
    def __init__(self):
        self._handle   = wt.HANDLE(0)
        self.connected = False
        self._profile  = PROFILES[-1]  # Generic default until connect()

    @property
    def detected_model(self) -> str:
        return self._profile["name"]

    def connect(self, device_id: int, device_name: str = "") -> tuple:
        try:
            self.disconnect(clear=False)
            if device_name:
                self._profile = auto_detect_profile(device_name)
                print(f"[MIDI] Detected model: {self._profile['name']}")
            handle = wt.HANDLE(0)
            r = _winmm.midiOutOpen(ctypes.byref(handle), device_id, 0, 0, CALLBACK_NULL)
            if r != MMSYSERR_NOERROR:
                return False, f"midiOutOpen failed (error {r})"
            self._handle   = handle
            self.connected = True
            self.clear()
            return True, f"Connected ({self._profile['name']})"
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
        Send a full 10x10 animation grid to the Launchpad.

        The 10x10 layout:
          (0,0),(0,9),(9,0),(9,9)  – physical corners, no pad, always skipped
          row 0, cols 1-8          – top border
          rows 1-8, col 9          – right border
          row 9, cols 1-8          – bottom border (if device has it)
          rows 1-8, col 0          – left border   (if device has it)
          rows 1-8, cols 1-8       – inner 8x8 grid
        """
        if not self.connected:
            return

        p = self._profile
        inner_pairs  = []
        border_pairs = []

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                if (row, col) in CORNERS:
                    continue
                note = self._note(row, col, p)
                if note is None:
                    continue
                r, g, b = grid[row][col]
                target = inner_pairs if (1 <= row <= 8 and 1 <= col <= 8) else border_pairs
                target.append((note, r, g, b))

        # Inner 8x8 first (proven working on all models), then border
        self._send_pairs(inner_pairs, p)
        if border_pairs:
            self._send_pairs(border_pairs, p)

    def clear(self):
        if not self.connected:
            return
        self.set_grid([[(0, 0, 0)] * GRID_SIZE for _ in range(GRID_SIZE)])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _note(row: int, col: int, profile: dict):
        """Map a 10x10 grid position to a MIDI note number, or None if no pad."""
        # Inner 8x8 — always present
        if 1 <= row <= 8 and 1 <= col <= 8:
            return (9 - row) * 10 + col
        # Top border
        if row == 0 and 1 <= col <= 8:
            return profile["top_base"] + (col - 1)
        # Right border
        if 1 <= row <= 8 and col == 9:
            return (9 - row) * 10 + 9
        # Bottom border
        if row == 9 and 1 <= col <= 8:
            return col if profile["has_bottom"] else None
        # Left border
        if 1 <= row <= 8 and col == 0:
            return (9 - row) * 10 if profile["has_left"] else None
        return None

    def _send_pairs(self, pairs: list, profile: dict):
        if not pairs:
            return
        gen  = profile["gen"]
        sid  = profile["sysex_id"]
        cmax = 63 if gen == 2 else 127

        msg = bytearray([0xF0, 0x00, 0x20, 0x29, 0x02, sid])
        if gen == 2:
            # F0 00 20 29 02 <id> 0B [note r g b ...] F7
            msg.append(0x0B)
            for note, r, g, b in pairs:
                msg += bytes([note,
                              self._scale(r, cmax),
                              self._scale(g, cmax),
                              self._scale(b, cmax)])
        else:
            # F0 00 20 29 02 <id> 03 [01 note r g b ...] F7
            msg.append(0x03)
            for note, r, g, b in pairs:
                msg += bytes([0x01, note,
                              self._scale(r, cmax),
                              self._scale(g, cmax),
                              self._scale(b, cmax)])
        msg.append(0xF7)
        self._sysex(bytes(msg))

    @staticmethod
    def _scale(v: int, cmax: int) -> int:
        return min(cmax, max(0, int(v * cmax / 255)))

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


# Backward-compatible alias
LaunchpadPro = LaunchpadDevice

