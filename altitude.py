#!/usr/bin/env python3
import csv
import datetime as dt
import math
import os
import sys
import time

# ===== settings =====
REFRESH_S = 0.25
BASELINE_SECONDS = 3.0
ALT_ALPHA = 0.90

BME280_ADDR = 0x77  # you saw 77 on i2cdetect, so we force it
QNH_HPA = None      # set for better MSL altitude (e.g. 1018.6). None => use STD
STD_SEA_LEVEL_HPA = 1013.25

CSV_NAME = None     # None => auto timestamped
# ====================


def pressure_to_altitude_m(p_hpa: float, p0_hpa: float) -> float:
    return 44330.0 * (1.0 - (p_hpa / p0_hpa) ** (1.0 / 5.255))


def fmt(v, nd=2, unit=""):
    if v is None:
        return "—"
    return f"{v:.{nd}f}{unit}"


def make_csv_path():
    if CSV_NAME:
        return CSV_NAME
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"sensor_log_{ts}.csv"


def init_i2c():
    import board
    import busio
    return busio.I2C(board.SCL, board.SDA)


def init_bme280(i2c, address=0x77):
    # Newer Adafruit layout (recommended in docs)
    try:
        from adafruit_bme280 import basic
        return basic.Adafruit_BME280_I2C(i2c, address=address)
    except Exception:
        pass

    # Older layout fallback (some installs)
    import adafruit_bme280
    return adafruit_bme280.Adafruit_BME280_I2C(i2c, address=address)


def init_lis3dh(i2c):
    import adafruit_lis3dh
    for addr in (0x18, 0x19):
        try:
            s = adafruit_lis3dh.LIS3DH_I2C(i2c, address=addr)
            s.range = adafruit_lis3dh.RANGE_2_G
            return s, f"OK (addr 0x{addr:02X})"
        except Exception:
            pass
    return None, "Not found at 0x18/0x19"


def main():
    try:
        i2c = init_i2c()
    except Exception as e:
        print("❌ I2C init failed:", e)
        sys.exit(1)

    # init sensors
    try:
        bme = init_bme280(i2c)
        bme_status = f"OK (addr 0x{BME280_ADDR:02X})"
    except Exception as e:
        print(f"❌ BME280 init failed at 0x{BME280_ADDR:02X}: {e}")
        print("You confirmed 0x77 shows in i2cdetect, so this usually means wiring/power or I2C not enabled.")
        sys.exit(2)

    lis, lis_status = init_lis3dh(i2c)

    # baseline pressure for REL altitude
    samples = []
    t0 = time.time()
    while time.time() - t0 < BASELINE_SECONDS:
        try:
            samples.append(float(bme.pressure))
        except Exception:
            pass
        time.sleep(0.05)

    if len(samples) < 5:
        print("❌ Could not collect baseline pressure samples.")
        sys.exit(3)

    baseline_p = sum(samples) / len(samples)

    sea_level_hpa = float(QNH_HPA) if QNH_HPA is not None else float(STD_SEA_LEVEL_HPA)

    alt_rel_filt = None
    alt_msl_filt = None

    # CSV setup
    csv_path = make_csv_path()
    fieldnames = [
        "timestamp_iso",
        "temp_c",
        "pressure_hpa",
        "humidity_pct",
        "alt_rel_m",
        "alt_rel_filt_m",
        "alt_msl_m",
        "alt_msl_filt_m",
        "sea_level_hpa_used",
        "baseline_pressure_hpa",
        "ax_mps2",
        "ay_mps2",
        "az_mps2",
        "accel_mag_g",
    ]

    f = open(csv_path, "w", newline="")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    f.flush()

    print("=== Altitude + CSV Logger ===")
    print(f"BME280: {bme_status}")
    print(f"LIS3DH: {lis_status}")
    print("CSV:", os.path.abspath(csv_path))
    if QNH_HPA is None:
        print(f"MSL altitude uses STD sea-level pressure: {STD_SEA_LEVEL_HPA:.2f} hPa (approx)")
        print("Set QNH_HPA for better MSL accuracy.\n")
    else:
        print(f"MSL altitude uses QNH_HPA: {sea_level_hpa:.2f} hPa\n")

    print("Ctrl+C to stop.\n")
    time.sleep(0.5)

    try:
        while True:
            ts = dt.datetime.now().isoformat(timespec="seconds")

            temp_c = float(bme.temperature)
            pres_hpa = float(bme.pressure)
            hum = float(bme.humidity)

            alt_rel = pressure_to_altitude_m(pres_hpa, baseline_p)  # 0 at start baseline
            alt_msl = pressure_to_altitude_m(pres_hpa, sea_level_hpa)

            if alt_rel_filt is None:
                alt_rel_filt = alt_rel
                alt_msl_filt = alt_msl
            else:
                alt_rel_filt = ALT_ALPHA * alt_rel_filt + (1 - ALT_ALPHA) * alt_rel
                alt_msl_filt = ALT_ALPHA * alt_msl_filt + (1 - ALT_ALPHA) * alt_msl

            ax = ay = az = amag_g = None
            if lis is not None:
                try:
                    ax, ay, az = lis.acceleration
                    amag_g = math.sqrt(ax * ax + ay * ay + az * az) / 9.80665
                except Exception:
                    pass

            # terminal
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{ts}\n")
            sys.stdout.write("=" * 52 + "\n")
            sys.stdout.write("BME280\n")
            sys.stdout.write(f"  temp: {fmt(temp_c, 2, ' °C')}\n")
            sys.stdout.write(f"  pres: {fmt(pres_hpa, 2, ' hPa')}\n")
            sys.stdout.write(f"  hum : {fmt(hum, 1, ' %')}\n")
            sys.stdout.write("\nALTITUDE\n")
            sys.stdout.write(f"  rel:      {fmt(alt_rel, 2, ' m')} (since start)\n")
            sys.stdout.write(f"  rel_filt: {fmt(alt_rel_filt, 2, ' m')}\n")
            sys.stdout.write(f"  msl:      {fmt(alt_msl, 2, ' m')} (approx above sea level)\n")
            sys.stdout.write(f"  msl_filt: {fmt(alt_msl_filt, 2, ' m')}\n")
            sys.stdout.write(f"  P0 used:  {sea_level_hpa:.2f} hPa\n")

            if lis is not None:
                sys.stdout.write("\nLIS3DH\n")
                sys.stdout.write(f"  ax: {fmt(ax, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  ay: {fmt(ay, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  az: {fmt(az, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  |a|: {fmt(amag_g, 3, ' g')} (≈1g still)\n")

            sys.stdout.write("\nLogging… Ctrl+C to stop.\n")
            sys.stdout.flush()

            writer.writerow({
                "timestamp_iso": ts,
                "temp_c": temp_c,
                "pressure_hpa": pres_hpa,
                "humidity_pct": hum,
                "alt_rel_m": alt_rel,
                "alt_rel_filt_m": alt_rel_filt,
                "alt_msl_m": alt_msl,
                "alt_msl_filt_m": alt_msl_filt,
                "sea_level_hpa_used": sea_level_hpa,
                "baseline_pressure_hpa": baseline_p,
                "ax_mps2": ax,
                "ay_mps2": ay,
                "az_mps2": az,
                "accel_mag_g": amag_g,
            })
            f.flush()

            time.sleep(REFRESH_S)

    except KeyboardInterrupt:
        print("\nStopped. CSV saved at:", os.path.abspath(csv_path))
    finally:
        try:
            f.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
