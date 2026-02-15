#!/usr/bin/env python3
import sys
import time
import math
import datetime

REFRESH_S = 0.2


def init_i2c():
    import board
    import busio
    return busio.I2C(board.SCL, board.SDA)


def i2c_ping(i2c, addr: int) -> bool:
    """True if a device ACKs at addr."""
    try:
        from adafruit_bus_device.i2c_device import I2CDevice
        dev = I2CDevice(i2c, addr)
        with dev:
            pass
        return True
    except Exception:
        return False


def init_lis3dh(i2c):
    try:
        import adafruit_lis3dh
    except ImportError:
        return None, "adafruit-circuitpython-lis3dh not installed"

    for addr in (0x18, 0x19):
        if not i2c_ping(i2c, addr):
            continue
        try:
            s = adafruit_lis3dh.LIS3DH_I2C(i2c, address=addr)
            s.range = adafruit_lis3dh.RANGE_2_G
            return s, f"OK (addr 0x{addr:02X})"
        except Exception as e:
            return None, f"Found at 0x{addr:02X} but init failed: {e}"
    return None, "Not found at 0x18/0x19"


def init_bme280(i2c):
    """
    Tries Adafruit CircuitPython BME280 first (recommended),
    then falls back to smbus2+bme280 if present.
    """
    # 1) Try Adafruit
    try:
        import adafruit_bme280
        for addr in (0x76, 0x77):
            if not i2c_ping(i2c, addr):
                continue
            try:
                s = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=addr)
                s.sea_level_pressure = 1013.25
                return ("adafruit", s), f"OK (Adafruit, addr 0x{addr:02X})"
            except Exception as e:
                return None, f"Found at 0x{addr:02X} but Adafruit init failed: {e}"
    except ImportError:
        pass

    # 2) Try smbus2 + bme280
    try:
        from smbus2 import SMBus
        import bme280 as bme280_lib

        bus = SMBus(1)
        for addr in (0x76, 0x77):
            # no ping here; bme280 lib will error if missing
            try:
                calib = bme280_lib.load_calibration_params(bus, addr)
                return ("smbus2", (bus, addr, calib, bme280_lib)), f"OK (smbus2+bme280, addr 0x{addr:02X})"
            except Exception:
                continue
        return None, "Not found at 0x76/0x77 (smbus2+bme280)"
    except ImportError:
        return None, "No supported BME280 library found (install adafruit-circuitpython-bme280 or bme280+smbus2)"


def read_bme280(bme):
    kind, obj = bme
    if kind == "adafruit":
        s = obj
        return float(s.temperature), float(s.pressure), float(s.humidity), getattr(s, "altitude", None), None
    else:
        bus, addr, calib, bme280_lib = obj
        try:
            data = bme280_lib.sample(bus, addr, calib)
            return float(data.temperature), float(data.pressure), float(data.humidity), None, None
        except Exception as e:
            return None, None, None, None, str(e)


def fmt(v, unit="", nd=3):
    if v is None:
        return "—"
    return f"{v:.{nd}f}{unit}"


def main():
    try:
        i2c = init_i2c()
        while not i2c.try_lock():
            time.sleep(0.01)
        i2c.unlock()
    except Exception as e:
        print(f"❌ I2C init failed: {e}")
        print("Make sure I2C is enabled: sudo raspi-config -> Interface Options -> I2C")
        sys.exit(1)

    lis, lis_status = init_lis3dh(i2c)
    bme, bme_status = init_bme280(i2c)

    print("=== Sensor live view (fixed BME280 init) ===")
    print(f"LIS3DH: {lis_status}")
    print(f"BME280 : {bme_status}")
    print("\nPress Ctrl+C to stop.\n")
    time.sleep(0.75)

    try:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            ax = ay = az = None
            aerr = None
            if lis:
                try:
                    ax, ay, az = lis.acceleration
                except Exception as e:
                    aerr = str(e)

            amag_g = None
            if ax is not None and ay is not None and az is not None:
                amag_g = math.sqrt(ax*ax + ay*ay + az*az) / 9.80665

            temp_c = pres_hpa = hum = alt_m = None
            berr = None
            if bme:
                temp_c, pres_hpa, hum, alt_m, berr = read_bme280(bme)

            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{now}\n")
            sys.stdout.write("=" * 38 + "\n\n")
            
            # account for gravity
            az = az - 9.8
            
            sys.stdout.write("LIS3DH\n")
            if lis:
                sys.stdout.write(f"  ax: {fmt(ax, ' m/s^2', 3)}\n")
                sys.stdout.write(f"  ay: {fmt(ay, ' m/s^2', 3)}\n")
                sys.stdout.write(f"  az: {fmt(az, ' m/s^2', 3)}\n")
                sys.stdout.write(f"   |a|: {fmt(amag_g, ' g', 3)}\n")
                if aerr:
                    sys.stdout.write(f"  ⚠️ read error: {aerr}\n")
            else:
                sys.stdout.write("  — not available\n")

            sys.stdout.write("\nBME280\n")
            if bme:
                sys.stdout.write(f"  temp: {fmt(temp_c, ' °C', 2)}\n")
                sys.stdout.write(f"  pres: {fmt(pres_hpa, ' hPa', 2)}\n")
                sys.stdout.write(f"  hum : {fmt(hum, ' %', 1)}\n")
                if alt_m is not None:
                    sys.stdout.write(f"  alt : {fmt(float(alt_m), ' m', 2)}\n")
                if berr:
                    sys.stdout.write(f"  ⚠️ read error: {berr}\n")
            else:
                sys.stdout.write("  — not available\n")

            sys.stdout.write("\nCtrl+C to stop.\n")
            sys.stdout.flush()
            time.sleep(REFRESH_S)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
