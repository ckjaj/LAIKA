#!/usr/bin/env python3
import time, math, sys, datetime

REFRESH_S = 0.25

# If you know local sea-level pressure (QNH) in hPa, set it here.
# If None, we auto-calibrate using the first few seconds of readings (good for RELATIVE altitude).
SEA_LEVEL_HPA = None  # e.g. 1018.6

# Smoothing (0..1). Higher = smoother but slower response.
ALT_ALPHA = 0.90

# How long to average pressure at startup for baseline calibration
BASELINE_SECONDS = 3.0


def init_i2c():
    import board, busio
    return busio.I2C(board.SCL, board.SDA)


def i2c_ping(i2c, addr: int) -> bool:
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
        return None

    for addr in (0x18, 0x19):
        if not i2c_ping(i2c, addr):
            continue
        try:
            s = adafruit_lis3dh.LIS3DH_I2C(i2c, address=addr)
            s.range = adafruit_lis3dh.RANGE_2_G
            return s
        except Exception:
            pass
    return None


def init_bme280(i2c):
    # Adafruit CircuitPython BME280
    import adafruit_bme280
    for addr in (0x76, 0x77):
        if not i2c_ping(i2c, addr):
            continue
        s = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=addr)
        # sea_level_pressure is used ONLY for s.altitude; we compute ourselves too.
        if SEA_LEVEL_HPA is not None:
            s.sea_level_pressure = float(SEA_LEVEL_HPA)
        return s
    raise RuntimeError("BME280 not found at 0x76/0x77")


def pressure_to_altitude_m(pressure_hpa: float, sea_level_hpa: float) -> float:
    """
    International Standard Atmosphere approximation:
    h = 44330 * (1 - (P / P0)^(1/5.255))
    """
    return 44330.0 * (1.0 - (pressure_hpa / sea_level_hpa) ** (1.0 / 5.255))


def fmt(v, unit="", nd=2):
    if v is None:
        return "—"
    return f"{v:.{nd}f}{unit}"


def calibrate_sea_level_from_baseline(pressure_samples_hpa, assumed_start_alt_m: float = 0.0) -> float:
    """
    If you assume your start altitude is 0m (or any known altitude),
    you can estimate sea-level pressure P0 from measured pressure P.
    P0 = P / (1 - h/44330)^(5.255)
    """
    p = sum(pressure_samples_hpa) / len(pressure_samples_hpa)
    h = assumed_start_alt_m
    return p / ((1.0 - (h / 44330.0)) ** 5.255)


def main():
    i2c = init_i2c()
    bme = init_bme280(i2c)
    lis = init_lis3dh(i2c)

    # Baseline pressure averaging
    samples = []
    t0 = time.time()
    while time.time() - t0 < BASELINE_SECONDS:
        try:
            samples.append(float(bme.pressure))  # hPa
        except Exception:
            pass
        time.sleep(0.05)

    if len(samples) < 5:
        print("❌ Could not get baseline pressure samples from BME280.")
        sys.exit(1)

    baseline_pressure = sum(samples) / len(samples)

    # Determine sea-level pressure to use
    if SEA_LEVEL_HPA is not None:
        sea_level_hpa = float(SEA_LEVEL_HPA)
        mode = "SEA-LEVEL CALIBRATED (absolute-ish)"
    else:
        # This sets altitude=0 at start (relative mode).
        # Equivalent to using baseline pressure as "sea level" for your local reference.
        sea_level_hpa = baseline_pressure
        mode = "RELATIVE (zeroed at start)"

    # Altitude filters
    alt_filt = None
    alt0 = pressure_to_altitude_m(baseline_pressure, sea_level_hpa)

    print("=== Altitude live ===")
    print(f"Mode: {mode}")
    print(f"Baseline pressure: {baseline_pressure:.2f} hPa")
    print(f"Sea-level used:    {sea_level_hpa:.2f} hPa")
    print("Press Ctrl+C to stop.\n")
    time.sleep(0.5)

    try:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read sensors
            temp_c = float(bme.temperature)
            pres_hpa = float(bme.pressure)
            hum = float(bme.humidity)

            # Altitude from pressure
            alt_m = pressure_to_altitude_m(pres_hpa, sea_level_hpa)
            rel_alt_m = alt_m - alt0

            # Smooth altitude
            if alt_filt is None:
                alt_filt = alt_m
            else:
                alt_filt = ALT_ALPHA * alt_filt + (1.0 - ALT_ALPHA) * alt_m

            rel_alt_filt = alt_filt - alt0

            # Optional accel magnitude (for “are we moving?” sanity)
            amag_g = None
            if lis:
                try:
                    ax, ay, az = lis.acceleration
                    amag_g = math.sqrt(ax*ax + ay*ay + az*az) / 9.80665
                except Exception:
                    pass

            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{now}\n")
            sys.stdout.write("=" * 42 + "\n")

            sys.stdout.write("BME280\n")
            sys.stdout.write(f"  temp: {fmt(temp_c, ' °C', 2)}\n")
            sys.stdout.write(f"  pres: {fmt(pres_hpa, ' hPa', 2)}\n")
            sys.stdout.write(f"  hum : {fmt(hum, ' %', 1)}\n")

            sys.stdout.write("\nALTITUDE (from pressure)\n")
            sys.stdout.write(f"  alt:      {fmt(alt_m, ' m', 2)}   (raw)\n")
            sys.stdout.write(f"  alt_filt: {fmt(alt_filt, ' m', 2)}   (smoothed)\n")
            sys.stdout.write(f"  Δalt:     {fmt(rel_alt_m, ' m', 2)}   vs start\n")
            sys.stdout.write(f"  Δalt_f:   {fmt(rel_alt_filt, ' m', 2)}   vs start (smoothed)\n")

            if amag_g is not None:
                sys.stdout.write("\nLIS3DH\n")
                sys.stdout.write(f"  |a|: {fmt(amag_g, ' g', 3)} (≈1g when still)\n")

            sys.stdout.write("\nCtrl+C to stop.\n")
            sys.stdout.flush()
            time.sleep(REFRESH_S)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
