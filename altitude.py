#!/usr/bin/env python3
import csv
import datetime as dt
import math
import os
import sys
import time

# ========= USER SETTINGS =========
REFRESH_S = 0.25

# Set this if you know local sea-level pressure (QNH) in hPa (more accurate MSL altitude).
# Example: 1018.6
QNH_HPA = None

# If QNH_HPA is None, we use standard sea-level pressure for MSL estimate:
STD_SEA_LEVEL_HPA = 1013.25

# Smoothing (0..1). Higher = smoother but slower response.
ALT_ALPHA = 0.90

# How long to average pressure at startup for baseline
BASELINE_SECONDS = 3.0

# Output CSV path (auto timestamp name). Set to a filename if you want fixed name.
CSV_NAME = None
# ================================


def pressure_to_altitude_m(pressure_hpa: float, sea_level_hpa: float) -> float:
    """Barometric formula (ISA approximation)."""
    return 44330.0 * (1.0 - (pressure_hpa / sea_level_hpa) ** (1.0 / 5.255))


def fmt(v, nd=2, unit=""):
    if v is None:
        return "—"
    return f"{v:.{nd}f}{unit}"


def init_i2c():
    import board
    import busio
    return busio.I2C(board.SCL, board.SDA)


def init_lis3dh(i2c):
    try:
        import adafruit_lis3dh
    except ImportError:
        return None, "adafruit-circuitpython-lis3dh not installed"

    # Typical LIS3DH I2C addresses
    for addr in (0x18, 0x19):
        try:
            s = adafruit_lis3dh.LIS3DH_I2C(i2c, address=addr)
            s.range = adafruit_lis3dh.RANGE_2_G
            return s, f"OK (addr 0x{addr:02X})"
        except Exception:
            pass

    return None, "Not found at 0x18/0x19"


def init_bme280(i2c):
    try:
        import adafruit_bme280
    except ImportError:
        return None, "adafruit-circuitpython-bme280 not installed"

    # Typical BME280 I2C addresses
    for addr in (0x76, 0x77):
        try:
            s = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=addr)
            return s, f"OK (addr 0x{addr:02X})"
        except Exception:
            pass

    return None, "Not found at 0x76/0x77"


def make_csv_path():
    if CSV_NAME:
        return CSV_NAME
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"sensor_log_{ts}.csv"


def main():
    # Init I2C + sensors
    try:
        i2c = init_i2c()
    except Exception as e:
        print(f"❌ I2C init failed: {e}")
        print("Enable I2C: sudo raspi-config -> Interface Options -> I2C")
        sys.exit(1)

    bme, bme_status = init_bme280(i2c)
    lis, lis_status = init_lis3dh(i2c)

    print("=== Altitude + CSV Logger ===")
    print(f"BME280: {bme_status}")
    print(f"LIS3DH: {lis_status}")
    if bme is None:
        print("\n❌ BME280 is required for altitude. Install:")
        print("  pip install adafruit-circuitpython-bme280")
        sys.exit(2)
    if lis is None:
        print("\n⚠️ LIS3DH not found (still logging BME280).")

    # Baseline pressure average for RELATIVE altitude
    samples = []
    t0 = time.time()
    while time.time() - t0 < BASELINE_SECONDS:
        try:
            samples.append(float(bme.pressure))  # hPa
        except Exception:
            pass
        time.sleep(0.05)

    if len(samples) < 5:
        print("❌ Could not collect baseline pressure samples.")
        sys.exit(3)

    baseline_pressure_hpa = sum(samples) / len(samples)

    # For MSL altitude:
    sea_level_hpa = float(QNH_HPA) if QNH_HPA is not None else float(STD_SEA_LEVEL_HPA)

    # Reference values
    alt_rel0 = pressure_to_altitude_m(baseline_pressure_hpa, baseline_pressure_hpa)  # will be ~0
    alt_filt_rel = None
    alt_filt_msl = None

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

    # Open CSV
    f = open(csv_path, "w", newline="")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    f.flush()

    print("\nLogging to CSV:", os.path.abspath(csv_path))
    if QNH_HPA is None:
        print(f"MSL altitude uses STANDARD sea-level pressure: {STD_SEA_LEVEL_HPA:.2f} hPa (approx)")
        print("For better accuracy, set QNH_HPA in the script to your local sea-level pressure.")
    else:
        print(f"MSL altitude uses QNH_HPA: {sea_level_hpa:.2f} hPa")

    print("\nCtrl+C to stop.\n")
    time.sleep(0.5)

    try:
        while True:
            now = dt.datetime.now()
            ts_iso = now.isoformat(timespec="seconds")

            # Read BME280
            temp_c = float(bme.temperature)
            pressure_hpa = float(bme.pressure)
            humidity = float(bme.humidity)

            # Altitudes
            alt_rel_m = pressure_to_altitude_m(pressure_hpa, baseline_pressure_hpa) - alt_rel0
            alt_msl_m = pressure_to_altitude_m(pressure_hpa, sea_level_hpa)

            # Smooth
            if alt_filt_rel is None:
                alt_filt_rel = alt_rel_m
                alt_filt_msl = alt_msl_m
            else:
                alt_filt_rel = ALT_ALPHA * alt_filt_rel + (1 - ALT_ALPHA) * alt_rel_m
                alt_filt_msl = ALT_ALPHA * alt_filt_msl + (1 - ALT_ALPHA) * alt_msl_m

            # Read LIS3DH (optional)
            ax = ay = az = amag_g = None
            if lis is not None:
                try:
                    ax, ay, az = lis.acceleration  # m/s^2
                    amag_g = math.sqrt(ax * ax + ay * ay + az * az) / 9.80665
                except Exception:
                    pass

            # Terminal output
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{ts_iso}\n")
            sys.stdout.write("=" * 48 + "\n")
            sys.stdout.write("BME280\n")
            sys.stdout.write(f"  temp: {fmt(temp_c, 2, ' °C')}\n")
            sys.stdout.write(f"  pres: {fmt(pressure_hpa, 2, ' hPa')}\n")
            sys.stdout.write(f"  hum : {fmt(humidity, 1, ' %')}\n")

            sys.stdout.write("\nALTITUDE\n")
            sys.stdout.write(f"  rel:      {fmt(alt_rel_m, 2, ' m')}   (since start)\n")
            sys.stdout.write(f"  rel_filt: {fmt(alt_filt_rel, 2, ' m')}   (smoothed)\n")
            sys.stdout.write(f"  msl:      {fmt(alt_msl_m, 2, ' m')}   (approx above sea level)\n")
            sys.stdout.write(f"  msl_filt: {fmt(alt_filt_msl, 2, ' m')}   (smoothed)\n")
            sys.stdout.write(f"  P0 used:  {sea_level_hpa:.2f} hPa\n")

            if lis is not None:
                sys.stdout.write("\nLIS3DH\n")
                sys.stdout.write(f"  ax: {fmt(ax, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  ay: {fmt(ay, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  az: {fmt(az, 3, ' m/s^2')}\n")
                sys.stdout.write(f"  |a|: {fmt(amag_g, 3, ' g')} (≈1g when still)\n")

            sys.stdout.write("\nLogging… Ctrl+C to stop.\n")
            sys.stdout.flush()

            # Write CSV row
            writer.writerow({
                "timestamp_iso": ts_iso,
                "temp_c": temp_c,
                "pressure_hpa": pressure_hpa,
                "humidity_pct": humidity,
                "alt_rel_m": alt_rel_m,
                "alt_rel_filt_m": alt_filt_rel,
                "alt_msl_m": alt_msl_m,
                "alt_msl_filt_m": alt_filt_msl,
                "sea_level_hpa_used": sea_level_hpa,
                "baseline_pressure_hpa": baseline_pressure_hpa,
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
