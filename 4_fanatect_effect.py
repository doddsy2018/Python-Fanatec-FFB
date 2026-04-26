import pygame
import time
import numpy as np
import lib_fanatec_controller_with_mpc as fc
import numpy as np
import keyboard

pygame.init()
pygame.joystick.init()
joystick_index=1
count = pygame.joystick.get_count()
if joystick_index >= count:
    raise RuntimeError(f"Joystick {joystick_index} not found ({count} available)")
    exit()

js = pygame.joystick.Joystick(joystick_index)

di = fc.FanatecDirectInput(joystick_index=0)

hid_dev = fc.FanatecHID()
if not hid_dev.connect():
    print("[~] HID vendor layer unavailable — DirectInput only.")
    hid_dev = None

fc.apply_preset(di, hid_dev, fc.PRESETS["snap"])
time.sleep(5)


print("\n── Cornering load (2 s) ──")
di.play_constant_force("corner", level=14000, duration_ms=2000)
time.sleep(2.2)
di.destroy("corner")
time.sleep(10)

print("\n── Kerb hit ──")
di.play_sine("kerb", magnitude=20000, period_ms=60, duration_ms=500)
time.sleep(0.7)
di.destroy("kerb")

'''
# LED Control Not working yet
if hid_dev:
    print("\n── LED sweep ──")
    for pct in range(0, 101, 10):
        hid_dev.set_leds(pct)
        time.sleep(0.1)
    hid_dev.leds_off()
'''

print("\n── Shutdown ──")
js.quit()
pygame.joystick.quit()
di.close()
if hid_dev:
    hid_dev.close()
print("[✓] Done.")