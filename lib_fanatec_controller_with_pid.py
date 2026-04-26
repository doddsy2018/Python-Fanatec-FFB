#!/usr/bin/env python3
"""
Fanatec Steering Wheel - Force Feedback Configuration (Windows)
Fixed: Handles SDL2 haptic detection failures common with Fanatec wheels.

Fallback chain:
  1. SDL_HapticOpenFromJoystick  (standard path)
  2. SDL_HapticOpen by index     (direct haptic enumeration)
  3. Raw HID only                (vendor commands without DirectInput FFB)

Requirements:
    pip install pygame hidapi
"""

import ctypes
import ctypes.util
import os
import sys
import time
import threading
import hid
from dataclasses import dataclass
from typing import Optional
import pygame
import keyboard

# ──────────────────────────────────────────────
# 1. LOAD SDL2
# ──────────────────────────────────────────────

def load_sdl2() -> ctypes.CDLL:
    try:
        import pygame
        pkg_dir = os.path.dirname(pygame.__file__)
        for path in [
            os.path.join(pkg_dir, "SDL2.dll"),
            os.path.join(pkg_dir, "lib", "SDL2.dll"),
        ]:
            if os.path.exists(path):
                print(f"[✓] SDL2: {path}")
                return ctypes.CDLL(path)
    except ImportError:
        pass
    name = ctypes.util.find_library("SDL2")
    if name:
        return ctypes.CDLL(name)
    raise RuntimeError("SDL2.dll not found. Run: pip install pygame")

SDL = load_sdl2()

# ──────────────────────────────────────────────
# 2. SDL2 CONSTANTS
# ──────────────────────────────────────────────

SDL_INIT_JOYSTICK   = 0x00000200
SDL_INIT_HAPTIC     = 0x00001000
SDL_HAPTIC_CONSTANT = (1 << 0)
SDL_HAPTIC_SINE     = (1 << 1)
SDL_HAPTIC_TRIANGLE = (1 << 3)
SDL_HAPTIC_SPRING   = (1 << 7)
SDL_HAPTIC_DAMPER   = (1 << 8)
SDL_HAPTIC_INERTIA  = (1 << 9)
SDL_HAPTIC_FRICTION = (1 << 10)
SDL_HAPTIC_GAIN     = (1 << 12)
SDL_HAPTIC_AUTOCENTER = (1 << 13)
SDL_HAPTIC_INFINITY = 0xFFFFFFFF
SDL_HAPTIC_CARTESIAN = 1
SDL_HAPTIC_POLAR    = 0

# ──────────────────────────────────────────────
# 3. SDL2 STRUCTURES
# ──────────────────────────────────────────────

class SDL_HapticDirection(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint8), ("dir", ctypes.c_int32 * 3)]

class SDL_HapticConstant(ctypes.Structure):
    _fields_ = [
        ("type",          ctypes.c_uint16),
        ("direction",     SDL_HapticDirection),
        ("length",        ctypes.c_uint32),
        ("delay",         ctypes.c_uint16),
        ("button",        ctypes.c_uint16),
        ("interval",      ctypes.c_uint16),
        ("level",         ctypes.c_int16),
        ("attack_length", ctypes.c_uint16),
        ("attack_level",  ctypes.c_uint16),
        ("fade_length",   ctypes.c_uint16),
        ("fade_level",    ctypes.c_uint16),
    ]

class SDL_HapticPeriodic(ctypes.Structure):
    _fields_ = [
        ("type",          ctypes.c_uint16),
        ("direction",     SDL_HapticDirection),
        ("length",        ctypes.c_uint32),
        ("delay",         ctypes.c_uint16),
        ("button",        ctypes.c_uint16),
        ("interval",      ctypes.c_uint16),
        ("period",        ctypes.c_uint16),
        ("magnitude",     ctypes.c_int16),
        ("offset",        ctypes.c_int16),
        ("phase",         ctypes.c_uint16),
        ("attack_length", ctypes.c_uint16),
        ("attack_level",  ctypes.c_uint16),
        ("fade_length",   ctypes.c_uint16),
        ("fade_level",    ctypes.c_uint16),
    ]

class SDL_HapticCondition(ctypes.Structure):
    _fields_ = [
        ("type",        ctypes.c_uint16),
        ("direction",   SDL_HapticDirection),
        ("length",      ctypes.c_uint32),
        ("delay",       ctypes.c_uint16),
        ("button",      ctypes.c_uint16),
        ("interval",    ctypes.c_uint16),
        ("right_sat",   ctypes.c_uint16 * 3),
        ("left_sat",    ctypes.c_uint16 * 3),
        ("right_coeff", ctypes.c_int16  * 3),
        ("left_coeff",  ctypes.c_int16  * 3),
        ("deadband",    ctypes.c_uint16 * 3),
        ("center",      ctypes.c_int16  * 3),
    ]

class SDL_HapticEffect(ctypes.Union):
    _fields_ = [
        ("type",      ctypes.c_uint16),
        ("constant",  SDL_HapticConstant),
        ("periodic",  SDL_HapticPeriodic),
        ("condition", SDL_HapticCondition),
    ]

# ──────────────────────────────────────────────
# 4. SDL2 FUNCTION SIGNATURES
# ──────────────────────────────────────────────

def _bind(name, argtypes, restype):
    fn = getattr(SDL, name, None)
    if fn:
        fn.argtypes = argtypes
        fn.restype  = restype
    return fn

SDL_Init                   = _bind("SDL_Init",                   [ctypes.c_uint32],                                    ctypes.c_int)
SDL_Quit                   = _bind("SDL_Quit",                   [],                                                   None)
SDL_GetError               = _bind("SDL_GetError",               [],                                                   ctypes.c_char_p)
SDL_ClearError             = _bind("SDL_ClearError",             [],                                                   None)
SDL_NumJoysticks           = _bind("SDL_NumJoysticks",           [],                                                   ctypes.c_int)
SDL_JoystickOpen           = _bind("SDL_JoystickOpen",           [ctypes.c_int],                                       ctypes.c_void_p)
SDL_JoystickName           = _bind("SDL_JoystickName",           [ctypes.c_void_p],                                    ctypes.c_char_p)
SDL_JoystickNameForIndex   = _bind("SDL_JoystickNameForIndex",   [ctypes.c_int],                                       ctypes.c_char_p)
SDL_JoystickClose          = _bind("SDL_JoystickClose",          [ctypes.c_void_p],                                    None)
SDL_JoystickIsHaptic       = _bind("SDL_JoystickIsHaptic",       [ctypes.c_void_p],                                    ctypes.c_int)
SDL_NumHaptics             = _bind("SDL_NumHaptics",             [],                                                   ctypes.c_int)
SDL_HapticName             = _bind("SDL_HapticName",             [ctypes.c_int],                                       ctypes.c_char_p)
SDL_HapticOpen             = _bind("SDL_HapticOpen",             [ctypes.c_int],                                       ctypes.c_void_p)
SDL_HapticOpenFromJoystick = _bind("SDL_HapticOpenFromJoystick", [ctypes.c_void_p],                                    ctypes.c_void_p)
SDL_HapticClose            = _bind("SDL_HapticClose",            [ctypes.c_void_p],                                    None)
SDL_HapticQuery            = _bind("SDL_HapticQuery",            [ctypes.c_void_p],                                    ctypes.c_uint)
SDL_HapticSetGain          = _bind("SDL_HapticSetGain",          [ctypes.c_void_p, ctypes.c_int],                      ctypes.c_int)
SDL_HapticSetAutocenter    = _bind("SDL_HapticSetAutocenter",    [ctypes.c_void_p, ctypes.c_int],                      ctypes.c_int)
SDL_HapticNewEffect        = _bind("SDL_HapticNewEffect",        [ctypes.c_void_p, ctypes.POINTER(SDL_HapticEffect)],  ctypes.c_int)
SDL_HapticRunEffect        = _bind("SDL_HapticRunEffect",        [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32],     ctypes.c_int)
SDL_HapticStopEffect       = _bind("SDL_HapticStopEffect",       [ctypes.c_void_p, ctypes.c_int],                      ctypes.c_int)
SDL_HapticDestroyEffect    = _bind("SDL_HapticDestroyEffect",    [ctypes.c_void_p, ctypes.c_int],                      None)
SDL_HapticStopAll          = _bind("SDL_HapticStopAll",          [ctypes.c_void_p],                                    ctypes.c_int)
SDL_HapticUpdateEffect     = _bind("SDL_HapticUpdateEffect",     [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(SDL_HapticEffect)], ctypes.c_int)

SDL_PumpEvents         = _bind("SDL_PumpEvents",         [],                                      None)
SDL_WasInit            = _bind("SDL_WasInit",            [ctypes.c_uint32],                       ctypes.c_uint32)
SDL_QuitSubSystem      = _bind("SDL_QuitSubSystem",      [ctypes.c_uint32],                       None)
SDL_JoystickNumAxes    = _bind("SDL_JoystickNumAxes",    [ctypes.c_void_p],                       ctypes.c_int)
SDL_JoystickNumButtons = _bind("SDL_JoystickNumButtons", [ctypes.c_void_p],                       ctypes.c_int)
SDL_JoystickNumHats    = _bind("SDL_JoystickNumHats",    [ctypes.c_void_p],                       ctypes.c_int)
SDL_JoystickGetAxis    = _bind("SDL_JoystickGetAxis",    [ctypes.c_void_p, ctypes.c_int],         ctypes.c_int16)
SDL_JoystickGetButton  = _bind("SDL_JoystickGetButton",  [ctypes.c_void_p, ctypes.c_int],         ctypes.c_uint8)
SDL_JoystickGetHat     = _bind("SDL_JoystickGetHat",     [ctypes.c_void_p, ctypes.c_int],         ctypes.c_uint8)

def sdl_error() -> str:
    err = SDL_GetError()
    SDL_ClearError()
    return err.decode() if err else "unknown"

def sdl_check(ret: int, ctx: str = "") -> int:
    if ret < 0:
        raise RuntimeError(f"SDL2 error{' (' + ctx + ')' if ctx else ''}: {sdl_error()}")
    return ret

# ──────────────────────────────────────────────
# 5. HAPTIC DEVICE DISCOVERY
#    Fanatec wheels sometimes only appear via
#    SDL_HapticOpen(index), not from the joystick
#    handle. We try all strategies.
# ──────────────────────────────────────────────

def enumerate_all_devices():
    """Print every joystick and haptic device SDL2 can see."""
    n_joy = SDL_NumJoysticks()
    n_hap = SDL_NumHaptics()
    print(f"\n  SDL2 sees {n_joy} joystick(s), {n_hap} haptic device(s):")

    print("  Joysticks:")
    for i in range(n_joy):
        js   = SDL_JoystickOpen(i)
        name = SDL_JoystickName(js).decode() if js else SDL_JoystickNameForIndex(i).decode()
        hap  = SDL_JoystickIsHaptic(js) if js else -1
        print(f"    JS[{i}] '{name}'  haptic={hap}")
        if js:
            SDL_JoystickClose(js)

    print("  Haptic devices:")
    for i in range(n_hap):
        raw  = SDL_HapticName(i)
        name = raw.decode() if raw else "<unknown>"
        print(f"    HAP[{i}] '{name}'")


def open_haptic_for_joystick(js_index: int):
    """
    Try every strategy to get a haptic handle for the given joystick.
    Returns (haptic_ptr, method_description) or raises RuntimeError.
    """
    js = SDL_JoystickOpen(js_index)
    if not js:
        raise RuntimeError(f"Cannot open joystick {js_index}: {sdl_error()}")

    name = SDL_JoystickName(js).decode()

    # ── Strategy 1: standard path ────────────
    SDL_ClearError()
    haptic = SDL_HapticOpenFromJoystick(js)
    if haptic:
        SDL_JoystickClose(js)
        return haptic, "SDL_HapticOpenFromJoystick"

    print(f"  [~] HapticOpenFromJoystick failed: {sdl_error()}")

    # ── Strategy 2: match by name in haptic list ──
    n_hap = SDL_NumHaptics()
    for i in range(n_hap):
        raw      = SDL_HapticName(i)
        hap_name = raw.decode() if raw else ""
        # fuzzy match — SDL haptic name often differs slightly from joystick name
        if (hap_name.lower() in name.lower() or
            name.lower() in hap_name.lower() or
            _name_similarity(name, hap_name) > 0.5):
            SDL_ClearError()
            haptic = SDL_HapticOpen(i)
            if haptic:
                SDL_JoystickClose(js)
                return haptic, f"SDL_HapticOpen({i}) matched '{hap_name}'"
            print(f"  [~] SDL_HapticOpen({i}) failed: {sdl_error()}")

    # ── Strategy 3: brute-force every haptic index ──
    print("  [~] Trying all haptic indices...")
    for i in range(n_hap):
        SDL_ClearError()
        haptic = SDL_HapticOpen(i)
        if haptic:
            caps = SDL_HapticQuery(haptic)
            if caps != 0:
                raw      = SDL_HapticName(i)
                hap_name = raw.decode() if raw else f"haptic[{i}]"
                print(f"  [~] Using haptic[{i}] '{hap_name}' (caps={caps:#010x})")
                SDL_JoystickClose(js)
                return haptic, f"SDL_HapticOpen({i}) brute-force"
            SDL_HapticClose(haptic)

    SDL_JoystickClose(js)
    raise RuntimeError(
        f"No haptic device found for '{name}'.\n\n"
        "── Troubleshooting ──────────────────────────────────────────\n"
        "1. WHEEL MODE: Fanatec wheel must be in PC mode (not PS/Xbox).\n"
        "   Hold the MODE button until the LED shows 'PC' / turns off.\n\n"
        "2. FANATEC DRIVER: Install the latest Fanatec driver from\n"
        "   https://fanatec.com/eu-en/wheelbases  (not just the firmware)\n\n"
        "3. SINGLE USB: Plug directly into a motherboard USB port,\n"
        "   not a hub. Some hubs block HID feature reports.\n\n"
        "4. VJOY / VJOYD CONFLICT: Disable vJoy / reWASD if installed;\n"
        "   they can shadow the real haptic device.\n\n"
        "5. RUN AS ADMIN: Right-click the script → 'Run as administrator'\n\n"
        "6. DINPUT TEST: Open 'Set up USB game controllers' in Control\n"
        "   Panel → Properties → Test tab — does the wheel respond?\n"
        "   If not, FFB isn't exposed to Windows at all yet.\n"
        "────────────────────────────────────────────────────────────"
    )


def _name_similarity(a: str, b: str) -> float:
    """Rough word-overlap similarity (no external deps)."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ──────────────────────────────────────────────
# 6. DIRECTINPUT FFB CLASS
# ──────────────────────────────────────────────

def _cart(x: int = 1, y: int = 0) -> SDL_HapticDirection:
    d = SDL_HapticDirection()
    d.type   = SDL_HAPTIC_CARTESIAN
    d.dir[0] = x
    d.dir[1] = y
    return d


class FanatecDirectInput:

    def __init__(self, joystick_index: int = 0):
        sdl_check(SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_HAPTIC), "SDL_Init")
        enumerate_all_devices()

        self._js_index = joystick_index
        js = SDL_JoystickOpen(joystick_index)
        self.name = SDL_JoystickName(js).decode() if js else f"joystick[{joystick_index}]"
        if js:
            SDL_JoystickClose(js)

        print(f"\n[→] Opening haptic for '{self.name}'...")
        self._haptic, method = open_haptic_for_joystick(joystick_index)
        print(f"[✓] Haptic opened via {method}")

        self._caps    = SDL_HapticQuery(self._haptic)
        self._effects: dict[str, int] = {}
        self._print_capabilities()

    def _print_capabilities(self):
        FLAGS = {
            SDL_HAPTIC_CONSTANT:   "Constant Force",
            SDL_HAPTIC_SINE:       "Sine (Periodic)",
            SDL_HAPTIC_SPRING:     "Spring",
            SDL_HAPTIC_DAMPER:     "Damper",
            SDL_HAPTIC_INERTIA:    "Inertia",
            SDL_HAPTIC_FRICTION:   "Friction",
            SDL_HAPTIC_GAIN:       "Master Gain",
            SDL_HAPTIC_AUTOCENTER: "Auto-Center",
        }
        print(f"\n  FFB capabilities on '{self.name}':")
        for flag, label in FLAGS.items():
            if self._caps & flag:
                print(f"    [✓] {label}")

    def supports(self, flag: int) -> bool:
        return bool(self._caps & flag)

    # ── Master controls ──────────────────────

    def set_gain(self, pct: float):
        if self.supports(SDL_HAPTIC_GAIN):
            SDL_HapticSetGain(self._haptic, int(max(0, min(100, pct))))
            print(f"[✓] Gain: {pct:.0f}%")
        else:
            print("[~] Gain not supported on this device")

    def set_autocenter(self, pct: float):
        if self.supports(SDL_HAPTIC_AUTOCENTER):
            SDL_HapticSetAutocenter(self._haptic, int(max(0, min(100, pct))))
            print(f"[✓] Autocenter: {pct:.0f}%")

    # ── Internal helpers ─────────────────────

    def _run(self, name: str, effect: SDL_HapticEffect, repeat: int = 1) -> int:
        if name in self._effects:
            self.destroy(name)
        eid = sdl_check(SDL_HapticNewEffect(self._haptic, ctypes.byref(effect)), "NewEffect")
        sdl_check(SDL_HapticRunEffect(self._haptic, eid, repeat), "RunEffect")
        self._effects[name] = eid
        return eid

    def _condition(self, etype: int, name: str,
                   right_sat: int, left_sat: int,
                   right_coeff: int, left_coeff: int,
                   deadband: int = 0, center: int = 0,
                   duration_ms: int = 0) -> int:
        e = SDL_HapticEffect()
        e.type                  = etype
        e.condition.type        = etype
        e.condition.direction   = _cart(1, 0)
        e.condition.length      = SDL_HAPTIC_INFINITY if duration_ms == 0 else duration_ms
        e.condition.delay       = 0
        e.condition.button      = 0
        e.condition.interval    = 0
        for i in range(3):
            e.condition.right_sat[i]   = right_sat
            e.condition.left_sat[i]    = left_sat
            e.condition.right_coeff[i] = right_coeff
            e.condition.left_coeff[i]  = left_coeff
            e.condition.deadband[i]    = deadband
            e.condition.center[i]      = center
        return self._run(name, e)

    # ── Effects ──────────────────────────────

    def play_constant_force(self, name="constant", level=12000,
                            duration_ms=3000, attack_ms=100, fade_ms=200,
                            repeat=1) -> int:
        e = SDL_HapticEffect()
        e.type                   = SDL_HAPTIC_CONSTANT
        e.constant.type          = SDL_HAPTIC_CONSTANT
        e.constant.direction     = _cart(1 if level >= 0 else -1, 0)
        e.constant.length        = duration_ms
        e.constant.delay         = 0
        e.constant.button        = 0
        e.constant.interval      = 0
        e.constant.level         = max(-32767, min(32767, level))
        e.constant.attack_length = attack_ms
        e.constant.attack_level  = 0
        e.constant.fade_length   = fade_ms
        e.constant.fade_level    = 0
        eid = self._run(name, e, repeat)
        print(f"[✓] Constant '{name}' playing (level={level})")
        return eid

    def play_spring(self, name="spring", right_coeff=20000, left_coeff=20000,
                    right_sat=32767, left_sat=32767, deadband=500,
                    center=0, duration_ms=0) -> int:
        eid = self._condition(SDL_HAPTIC_SPRING, name, right_sat, left_sat,
                              right_coeff, left_coeff, deadband, center, duration_ms)
        print(f"[✓] Spring '{name}' playing (coeff={right_coeff})")
        return eid

    def play_damper(self, name="damper", right_coeff=12000, left_coeff=12000,
                    right_sat=32767, left_sat=32767, duration_ms=0) -> int:
        eid = self._condition(SDL_HAPTIC_DAMPER, name, right_sat, left_sat,
                              right_coeff, left_coeff, 0, 0, duration_ms)
        print(f"[✓] Damper '{name}' playing (coeff={right_coeff})")
        return eid

    def play_friction(self, name="friction", right_coeff=10000, left_coeff=10000,
                      right_sat=32767, left_sat=32767, duration_ms=0) -> int:
        eid = self._condition(SDL_HAPTIC_FRICTION, name, right_sat, left_sat,
                              right_coeff, left_coeff, 0, 0, duration_ms)
        print(f"[✓] Friction '{name}' playing (coeff={right_coeff})")
        return eid

    def play_inertia(self, name="inertia", right_coeff=8000, left_coeff=8000,
                     right_sat=32767, left_sat=32767, duration_ms=0) -> int:
        eid = self._condition(SDL_HAPTIC_INERTIA, name, right_sat, left_sat,
                              right_coeff, left_coeff, 0, 0, duration_ms)
        print(f"[✓] Inertia '{name}' playing (coeff={right_coeff})")
        return eid

    def play_sine(self, name="sine", magnitude=15000, period_ms=150,
                  duration_ms=1000, attack_ms=0, fade_ms=300, repeat=1) -> int:
        e = SDL_HapticEffect()
        e.type                   = SDL_HAPTIC_SINE
        e.periodic.type          = SDL_HAPTIC_SINE
        e.periodic.direction     = _cart(1, 0)
        e.periodic.length        = duration_ms
        e.periodic.delay         = 0
        e.periodic.button        = 0
        e.periodic.interval      = 0
        e.periodic.period        = period_ms
        e.periodic.magnitude     = max(0, min(32767, magnitude))
        e.periodic.offset        = 0
        e.periodic.phase         = 0
        e.periodic.attack_length = attack_ms
        e.periodic.attack_level  = 0
        e.periodic.fade_length   = fade_ms
        e.periodic.fade_level    = 0
        eid = self._run(name, e, repeat)
        print(f"[✓] Sine '{name}' playing (mag={magnitude}, period={period_ms}ms)")
        return eid

    def update_constant_force(self, name: str = "pid_constant", level: int = 0) -> int:
        """Create or update a persistent constant-force effect without destroy/recreate overhead."""
        level = max(-32767, min(32767, level))
        e = SDL_HapticEffect()
        e.type                   = SDL_HAPTIC_CONSTANT
        e.constant.type          = SDL_HAPTIC_CONSTANT
        e.constant.direction     = _cart(1, 0)  # signed level controls direction, not this vector
        e.constant.length        = SDL_HAPTIC_INFINITY
        e.constant.delay         = 0
        e.constant.button        = 0
        e.constant.interval      = 0
        e.constant.level         = level
        e.constant.attack_length = 0
        e.constant.attack_level  = 0
        e.constant.fade_length   = 0
        e.constant.fade_level    = 0
        if name not in self._effects:
            return self._run(name, e, 1)
        eid = self._effects[name]
        if SDL_HapticUpdateEffect(self._haptic, eid, ctypes.byref(e)) < 0:
            self.destroy(name)
            return self._run(name, e, 1)
        return eid

    # ── Lifecycle ────────────────────────────

    def stop(self, name: str):
        if name in self._effects:
            SDL_HapticStopEffect(self._haptic, self._effects[name])

    def stop_all(self):
        SDL_HapticStopAll(self._haptic)

    def destroy(self, name: str):
        if name in self._effects:
            SDL_HapticDestroyEffect(self._haptic, self._effects.pop(name))

    def destroy_all(self):
        for name in list(self._effects):
            self.destroy(name)

    def close(self):
        self.destroy_all()
        SDL_HapticClose(self._haptic)
        SDL_Quit()
        print("[✓] Released.")


# ──────────────────────────────────────────────
# 7. FANATEC VENDOR HID
# ──────────────────────────────────────────────

FANATEC_VID = 0x0EB7
FANATEC_PIDS = {
    0x0001: "CSL Elite Wheel Base",
    0x0003: "ClubSport Wheel Base V2.5",
    0x0005: "ClubSport Wheel Base",
    0x0006: "ClubSport Wheel Base V2",
    0x0010: "Podium Wheel Base DD1",
    0x0011: "Podium Wheel Base DD2",
    0x0020: "CSL DD",
    0x0021: "CSL DD (8Nm Kit)",
}

class FanatecHID:
    def __init__(self):
        self.device: Optional[hid.device] = None

    def connect(self) -> bool:
        devs = hid.enumerate(FANATEC_VID, 0)
        if not devs:
            print("[!] No Fanatec HID device found.")
            return False
        d    = devs[0]
        pid  = d["product_id"]
        name = FANATEC_PIDS.get(pid, f"Fanatec {pid:#06x}")
        print(f"[✓] HID: {name}")
        self.device = hid.device()
        self.device.open(FANATEC_VID, pid)
        self.device.set_nonblocking(True)
        return True

    def _send(self, data: list):
        padded = (data + [0] * 64)[:64]
        self.device.write(padded)

    def set_steering_range(self, deg: int):
        deg = max(180, min(1080, deg))
        self._send([0x02, (deg >> 8) & 0xFF, deg & 0xFF])
        print(f"[✓] Steering range: {deg}°")

    def set_ffb_strength(self, pct: int):
        self._send([0x01, 0x01, max(0, min(100, pct))])
        print(f"[✓] HW FFB: {pct}%")

    def set_damper(self, pct: int):
        self._send([0x01, 0x02, max(0, min(100, pct))])

    def set_friction(self, pct: int):
        self._send([0x01, 0x03, max(0, min(100, pct))])

    def set_leds(self, rpm_pct: float):
        self._send([0x08, int(max(0, min(100, rpm_pct)) / 100 * 0xFF)])

    def leds_off(self):
        self._send([0x08, 0])

    def close(self):
        if self.device:
            self.device.close()


# ──────────────────────────────────────────────
# 8. PRESETS
# ──────────────────────────────────────────────

@dataclass
class FFBPreset:
    name: str
    gain_pct: float
    autocenter_pct: float
    spring_coeff: int
    damper_coeff: int
    friction_coeff: int
    inertia_coeff: int
    hw_ffb_pct: int
    steering_range: int

PRESETS = {
    "road":    FFBPreset("Road Car",      75.0, 0, 16000,  8000, 5000, 6000,  75, 900),
    "gt":      FFBPreset("GT / Race Car", 85.0, 0, 22000, 12000, 7000, 8000,  85, 720),
    "formula": FFBPreset("Formula",       90.0, 0, 28000, 16000, 9000,10000,  90, 360),
    "drift":   FFBPreset("Drift",         70.0, 0,  8000,  4000, 3000, 3000,  70, 720),
    "menu":    FFBPreset("Menu",          50.0,30, 20000,  5000, 2000, 2000,  50, 540),
    # High spring snaps the wheel back hard; low damper/inertia minimise resistance to that return motion.
    "snap":    FFBPreset("Snap Center",   85.0, 0, 32000,  2000, 2000, 1500,  85, 360),
}

def apply_preset(di: FanatecDirectInput, hid_dev: Optional[FanatecHID], p: FFBPreset):
    print(f"\n══ Preset: {p.name} ══")
    di.set_gain(p.gain_pct)
    di.set_autocenter(p.autocenter_pct)
    di.stop_all()
    di.destroy_all()
    di.play_spring(   right_coeff=p.spring_coeff,   left_coeff=p.spring_coeff)
    di.play_damper(   right_coeff=p.damper_coeff,   left_coeff=p.damper_coeff)
    di.play_friction( right_coeff=p.friction_coeff, left_coeff=p.friction_coeff)
    di.play_inertia(  right_coeff=p.inertia_coeff,  left_coeff=p.inertia_coeff)
    if hid_dev and hid_dev.device:
        hid_dev.set_steering_range(p.steering_range)
        hid_dev.set_ffb_strength(p.hw_ffb_pct)
        hid_dev.set_damper(int(p.damper_coeff / 327))
        hid_dev.set_friction(int(p.friction_coeff / 327))


# ──────────────────────────────────────────────
# 9. LIVE INPUT MONITOR
# ──────────────────────────────────────────────


_HAT_DIR = {
    ( 0,  0): "C",  ( 0,  1): "N",  ( 1,  1): "NE",
    ( 1,  0): "E",  ( 1, -1): "SE", ( 0, -1): "S",
    (-1, -1): "SW", (-1,  0): "W",  (-1,  1): "NW",
}

def print_inputs_loop(js, poll_hz: float = 30.0):
    """Print joystick axis, button, and hat values in a live updating loop. Ctrl+C to stop."""


    name      = js.get_name()
    n_axes    = js.get_numaxes()
    n_buttons = js.get_numbuttons()
    n_hats    = js.get_numhats()
    interval  = 1.0 / max(1.0, poll_hz)

    print(f"[✓] '{name}'  axes={n_axes}  buttons={n_buttons}  hats={n_hats}")
    print("Press Ctrl+C to stop.\n")

    n_lines = 0
    try:
        while True:
            pygame.event.pump()

            axes    = [js.get_axis(i)   for i in range(n_axes)]
            buttons = [js.get_button(i) for i in range(n_buttons)]
            hats    = [js.get_hat(i)    for i in range(n_hats)]

            lines = []
            if axes:
                row = []
                for i, v in enumerate(axes):
                    pct    = (v + 1.0) / 2.0
                    filled = int(pct * 10)
                    bar    = "█" * filled + "░" * (10 - filled)
                    row.append(f"A{i}:[{bar}]{v:+.3f}")
                lines.append("  ".join(row))
            if buttons:
                lines.append(" ".join(f"B{i}:{'■' if b else '□'}" for i, b in enumerate(buttons)))
            if hats:
                lines.append(" ".join(f"H{i}:{_HAT_DIR.get(h, str(h))}" for i, h in enumerate(hats)))

            if n_lines:
                sys.stdout.write(f"\033[{n_lines}A")
            for line in lines:
                sys.stdout.write(f"\033[K{line}\n")
            sys.stdout.flush()
            n_lines = len(lines)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[✓] User input Printing stopped.")
    finally:
        pass



def get_values(js, a=None, b=None, h=None):
    if a is None:
        a = [0, 1, 4, 5]
    if b is None:
        b = [4, 5]
    if h is None:
        h = []

    name      = js.get_name()
    n_axes    = js.get_numaxes()
    n_buttons = js.get_numbuttons()
    n_hats    = js.get_numhats()

    pygame.event.pump()

    axes    = [js.get_axis(i)   for i in range(n_axes)]
    buttons = [js.get_button(i) for i in range(n_buttons)]
    hats    = [js.get_hat(i)    for i in range(n_hats)]

    input_values={}
    if axes:
        for i, v in enumerate(axes):
            if i in a:
                input_values[f"A{i}"] = round(v, 3)
    if buttons:
        for i, v in enumerate(buttons):
            if i in b:
                input_values[f"B{i}"] = round(v, 3)
    if hats:
        for i, v in enumerate(hats):
            if i in h:
                input_values[f"H{i}"] = round(v,3)

    return input_values


# ──────────────────────────────────────────────
# 10. PID STEERING CONTROLLER
# ──────────────────────────────────────────────

class PIDController:
    """Discrete PID with anti-windup integral clamping."""

    def __init__(self, kp: float, ki: float, kd: float,
                 output_min: float = -32767.0, output_max: float = 32767.0,
                 integral_limit: float = 8000.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        self._integral   = 0.0
        self._prev_error = 0.0

    def reset(self):
        self._integral   = 0.0
        self._prev_error = 0.0

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0.0:
            return 0.0
        self._integral = max(-self.integral_limit,
                             min(self.integral_limit, self._integral + error * dt))
        derivative       = (error - self._prev_error) / dt
        self._prev_error = error
        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(self.output_min, min(self.output_max, output))


class AngleHoldController:
    """
    PID wheel-position controller that drives to a target angle and holds it
    indefinitely until a new target is supplied or deactivate() is called.

    Usage::
        ctrl = AngleHoldController(di, js, steering_range=360.0)
        ctrl.activate(90.0)       # drive to 90° and hold
        time.sleep(2)
        ctrl.set_target(-45.0)    # transition to -45° and hold
        time.sleep(2)
        ctrl.deactivate()         # stop all force
    """

    _EFFECT = "pid_drive"

    def __init__(self, di: FanatecDirectInput, js,
                 steering_range: float = 900.0,
                 kp: float = 100.0, ki: float = 5.0, kd: float = 10.0,
                 poll_hz: float = 60.0, steering_axis: int = 0):
        self._di       = di
        self._js       = js
        self._half     = steering_range / 2.0
        self._kp       = kp
        self._ki       = ki
        self._kd       = kd
        self._interval = 1.0 / max(1.0, poll_hz)
        self._axis     = steering_axis

        self._target     = 0.0
        self._lock       = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Public API ───────────────────────────

    def activate(self, target_deg: float):
        """Drive to target_deg and hold. Safe to call while already active — updates target."""
        with self._lock:
            self._target = target_deg
            if self._thread and self._thread.is_alive():
                #print(f"[→] AngleHoldController: target → {target_deg:.1f}°")
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="angle-hold")
            self._thread.start()
        print(f"[→] AngleHoldController: activated, target={target_deg:.1f}°")

    def set_target(self, target_deg: float):
        """Update the target angle while the controller is running."""
        with self._lock:
            self._target = target_deg
        print(f"[→] AngleHoldController: target → {target_deg:.1f}°")

    def deactivate(self):
        """Stop the control loop and release all force effects."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        print("[✓] AngleHoldController: deactivated")

    @property
    def is_active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Background control loop ──────────────

    def _loop(self):
        pid         = PIDController(self._kp, self._ki, self._kd)
        t_prev      = time.time()
        last_target = None

        try:
            while not self._stop_event.is_set():
                pygame.event.pump()
                current_deg = self._js.get_axis(self._axis) * self._half

                with self._lock:
                    target = self._target

                if target != last_target:
                    pid.reset()
                    last_target = target

                error  = target - current_deg
                t_now  = time.time()
                dt     = max(t_now - t_prev, 1e-6)
                t_prev = t_now

                force = int(pid.compute(error, dt))
                self._di.update_constant_force(self._EFFECT, level=force)

                self._stop_event.wait(self._interval)

        except Exception as e:
            print(f"[!] AngleHoldController loop error: {e}")
        finally:
            self._di.stop(self._EFFECT)
            self._di.destroy(self._EFFECT)


# ──────────────────────────────────────────────
# 11. DEMO
# ──────────────────────────────────────────────

def demo():
    pygame.init()
    pygame.joystick.init()
    joystick_index=1
    count = pygame.joystick.get_count()
    if joystick_index >= count:
        raise RuntimeError(f"Joystick {joystick_index} not found ({count} available)")
        exit()

    js = pygame.joystick.Joystick(joystick_index)

    di = FanatecDirectInput(joystick_index=0)

    hid_dev = FanatecHID()
    if not hid_dev.connect():
        print("[~] HID vendor layer unavailable — DirectInput only.")
        hid_dev = None

    apply_preset(di, hid_dev, PRESETS["snap"])
    time.sleep(5)

    ctrl = AngleHoldController(di, js, steering_range=360.0, poll_hz=120.0)

    steer_angle = 0.0
    ctrl.activate(steer_angle)
    print("Use +/- to adjust steering angle, Q to quit.")
    while True:
        if keyboard.is_pressed('q'):
            break
        if keyboard.is_pressed('+'):
            steer_angle += 5.0
            ctrl.set_target(steer_angle)
            time.sleep(0.2)
        elif keyboard.is_pressed('-'):
            steer_angle -= 5.0
            ctrl.set_target(steer_angle)
            time.sleep(0.2)
        #print(get_values(js))
        time.sleep(0.05)

    ctrl.deactivate()


    print("\n── Shutdown ──")
    js.quit()
    pygame.joystick.quit()
    di.close()
    if hid_dev:
        hid_dev.close()
    print("[✓] Done.")


if __name__ == "__main__":
    demo()