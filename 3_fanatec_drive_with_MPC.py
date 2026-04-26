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

ctrl = fc.AngleHoldController(di, js, steering_range=900.0, poll_hz=120.0)

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