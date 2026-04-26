import pygame
import time
import numpy as np
import lib_fanatec_controller_with_pid as fc
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

#    name: str
#    gain_pct: float
#    autocenter_pct: float
#    spring_coeff: int
#    damper_coeff: int
#    friction_coeff: int
#    inertia_coeff: int
#    hw_ffb_pct: int
#    steering_range: int

wheel_setup=fc.FFBPreset("custom",    85.0, 30, 32000,  12000, 12000, 15000,  85, 360)

fc.apply_preset(di, hid_dev, wheel_setup)
time.sleep(5)

ctrl = fc.AngleHoldController(di, js, steering_range=360.0, poll_hz=120.0)

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

print("\n── Shutdown ──")
js.quit()
pygame.joystick.quit()
di.close()
if hid_dev:
    hid_dev.close()
print("[✓] Done.")