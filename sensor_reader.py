import RPi.GPIO as GPIO
import time

PIR_PIN = 11
TRIG_PIN = 16
ECHO_PIN = 18

GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIR_PIN, GPIO.IN)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# pir 센서 입력 받기
def read_pir():
    return GPIO.input(PIR_PIN)

# 초음파 센서 거리 받기
def read_distance():
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150  # cm 단위
    return round(distance, 2)
