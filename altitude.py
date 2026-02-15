#!/usr/bin/env python3
import time, math, sys, datetime

from smbus2 import SMBus
import bme280
import board, busio
import adafruit_lis3dh

REFRESH_S = 0.25
ALT_ALPHA = 0.90
BASELINE_SECONDS = 3.0

BME_ADDRS = [0x76, 0x77]


def pressure_to_altitude_m(p, p0):
    return 44330.0 * (1.0 - (p / p0) ** (1.0 / 5.255))


def fmt(v, unit="", nd=2):
    if v is None:
        return "—"
    return f"{v:.{nd}f}{unit}"


def init_bme280():
    bus = SMBus(1)
    for addr in BME_ADDRS:
        try:
            calib = bme280.load_calibration_params(bus, addr)
            return bus, addr, calib
        except Exception:
            pass
    raise RuntimeError("BME280 not found at 0x76 or 0x77")


def init_lis3dh():
    i2c = busio.I2C(board.SCL, board.SDA)
    for addr in (0x18, 0x19):
        try:
            s = adafruit_lis3dh.LIS3DH_I2C(i2c, address=addr)
            s.range = adafruit_lis3dh.RANGE_2_G
            return s
        except Exception:
            pass
    return None


def main():
    # --- Init sensors ---
    bus, bme_addr, calib = init_bme280()
    lis = init_lis3dh()

    # --- Baseline pressure ---
    samples = []
    t0 = time.time()
    while time.time() - t0 < BASELINE_SECONDS:
        data = bme280.sample(bus, bme_addr, calib)
        samples.append(data.pressure)
        time.sleep(0.05)

    p0 = sum(samples) / len(samples)
    alt0 = pressure_to_altitude_m(p0, p0)
    alt_filt = None

    print("=== ALTITUDE LIVE (BME280 + LIS3DH) ===")
    print(f"BME280 addr: 0x{bme_addr:02X}")
    print(f"Baseline pressure: {p0:.2f} hPa")
    print("Mode: RELATIVE altitude (zeroed at start)")
    print("\nCtrl+C to stop\n")
    time.sleep(0.5)

    try:
        while True:
            data = bme280.sample(bus, bme_addr, calib)

            temp = data.temperature
            pres = data.pressure
            hum = data.humidity

            alt = pressure_to_altitude_m(pres, p0)
            rel_alt = alt - alt0

            if alt_filt is None:
                alt_filt = alt
            else:
                alt_filt = ALT_ALPHA * alt_filt + (1 - ALT_ALPHA) * alt

            rel_alt_f = alt_filt - alt0

            amag = None
            if lis:
                ax, ay, az = lis.acceleration
                amag = math.sqrt(ax*ax + ay*ay + az*az) / 9.80665

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{now}\n")
            sys.stdout.write("=" * 42 + "\n")

            sys.stdout.write("BME280\n")
            sys.stdout.write(f"  temp: {fmt(temp, ' °C', 2)}\n")
            sys.stdout.write(f"  pres: {fmt(pres, ' hPa', 2)}\n")
            sys.stdout.write(f"  hum : {fmt(hum, ' %', 1)}\n")

            sys.stdout.write("\nALTITUDE\n")
            sys.stdout.write(f"  alt:      {fmt(alt, ' m', 2)}\n")
            sys.stdout.write(f"  alt_filt: {fmt(alt_filt, ' m', 2)}\n")
            sys.stdout.write(f"  Δalt:     {fmt(rel_alt, ' m', 2)}\n")
            sys.stdout.write(f"  Δalt_f:   {fmt(rel_alt_f, ' m', 2)}\n")

            if amag is not None:
                sys.stdout.write("\nLIS3DH\n")
                sys.stdout.write(f"  |a|: {fmt(amag, ' g', 3)}\n")

            sys.stdout.write("\nCtrl+C to stop\n")
            sys.stdout.flush()
            time.sleep(REFRESH_S)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
