import pygame
import time
import lib_fanatec_controller_with_pid as fc

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

try:
    while True:
        print (fc.get_values(js))
        time.sleep(1/30.0)
except KeyboardInterrupt:
    print("\n[!] interrupted.")
finally:
    di.stop("pid_drive")
    di.destroy("pid_drive")

print("\n── Shutdown ──")
js.quit()
pygame.joystick.quit()
di.close()
if hid_dev:
    hid_dev.close()
print("[✓] Done.")