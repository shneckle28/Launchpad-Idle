"""
Run this directly: python test_midi.py
Tests every Launchpad port with both NoteOn and SysEx to find what works.
Watch your Launchpad — any pad that lights up tells us which port and method works.
"""
import ctypes
import ctypes.wintypes as wt
import time

winmm = ctypes.windll.winmm

class MIDIOUTCAPS(ctypes.Structure):
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

class MIDIHDR(ctypes.Structure):
    pass

MIDIHDR._fields_ = [
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

print(f"MIDIHDR size: {ctypes.sizeof(MIDIHDR)} (must be 88)")
assert ctypes.sizeof(MIDIHDR) == 88

def send_noteon(handle, note, velocity=63, channel=0):
    msg = 0x90 | (channel & 0xF) | (note << 8) | (velocity << 16)
    r = winmm.midiOutShortMsg(handle, msg)
    return r

def send_sysex(handle, data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    hdr = MIDIHDR()
    hdr.lpData          = ctypes.cast(buf, ctypes.c_char_p)
    hdr.dwBufferLength  = len(data)
    hdr.dwBytesRecorded = len(data)
    hdr.dwFlags         = 0

    r = winmm.midiOutPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
    if r != 0:
        print(f"  PrepareHeader failed: {r}")
        return r

    r = winmm.midiOutLongMsg(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
    if r != 0:
        print(f"  LongMsg failed: {r}")
        winmm.midiOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
        return r

    # Wait for done
    deadline = time.perf_counter() + 2.0
    while not (hdr.dwFlags & 0x1) and time.perf_counter() < deadline:
        time.sleep(0.001)

    if not (hdr.dwFlags & 0x1):
        print("  WARNING: MHDR_DONE never set (timeout)")

    winmm.midiOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
    return 0

# List all devices
count = winmm.midiOutGetNumDevs()
print(f"\n{count} MIDI output devices:")
for i in range(count):
    caps = MIDIOUTCAPS()
    winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
    print(f"  [{i}] {caps.szPname}")

# Test each Launchpad port
for device_id in range(count):
    caps = MIDIOUTCAPS()
    winmm.midiOutGetDevCapsW(device_id, ctypes.byref(caps), ctypes.sizeof(caps))
    if "Launchpad" not in caps.szPname:
        continue

    print(f"\n{'='*50}")
    print(f"Testing [{device_id}] {caps.szPname}")
    print(f"{'='*50}")

    handle = wt.HANDLE(0)
    r = winmm.midiOutOpen(ctypes.byref(handle), device_id, 0, 0, 0)
    if r != 0:
        print(f"  midiOutOpen failed: {r}")
        continue
    print(f"  Opened OK")

    # Test 1: NoteOn — lights pad 44 (center) bright red (vel=5 = red on LP Pro)
    print("  Test 1: NoteOn note=44 vel=5 (should light center pad red)...")
    r = send_noteon(handle, 44, velocity=5)
    print(f"  NoteOn result: {r} ({'OK' if r==0 else 'FAIL'})")
    time.sleep(1.5)

    # Test 2: NoteOn to turn it off
    send_noteon(handle, 44, velocity=0)
    time.sleep(0.3)

    # Test 3: SysEx — single pad bright white
    print("  Test 2: SysEx single pad (note 44, RGB 63,63,63 = white)...")
    sysex = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x10, 0x0B,
                   44, 63, 63, 63,
                   0xF7])
    r = send_sysex(handle, sysex)
    print(f"  SysEx result: {r} ({'OK' if r==0 else 'FAIL'})")
    time.sleep(1.5)

    # Clear
    send_sysex(handle, bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x10, 0x0B,
                               44, 0, 0, 0, 0xF7]))
    time.sleep(0.3)

    winmm.midiOutClose(handle)
    print(f"  Closed")

print("\nDone. Did anything light up? Note which device ID and which test worked.")
