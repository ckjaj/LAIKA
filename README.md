# LAIKA
**L**ehigh **A**vionics **I**nstrumentation & **K**inetics **A**nalysis

Rocket payload for LU Rocketry Association's IREC June 2026 launch. Runs on a Raspberry Pi and logs barometric, thermal, and acceleration data during flight to a CSV file for post-flight analysis.

---

## Hardware

| Component | Sensor | Interface | Address |
|---|---|---|---|
| Barometer / Thermometer | BME280 | I2C | `0x77` |
| Accelerometer | LIS3DH | I2C | `0x19` |
| Computer | Raspberry Pi | — | — |

---

## Project Structure

```
LAIKA/
├── DATA/               # CSV logs written here at runtime
├── main_tests.py           # Main flight data logger (Python)
├── graphing.R          # Post-flight data visualization (R)
└── README.md
```

---

## Setup

### Python Logger

Requires Python 3 and the following libraries. Run on the Raspberry Pi:

```bash
pip install adafruit-circuitpython-bme280 adafruit-circuitpython-lis3dh
```

Make sure I2C is enabled on the Pi:

```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

Verify sensors are wired and detected:

```bash
i2cdetect -y 1
# Should show 0x19 (LIS3DH) and 0x77 (BME280)
```

### R Graphing

Requires R and the following packages. Run once in an R session:

```r
install.packages(c("ggplot2", "dplyr", "readr"))
```

---

## How to Run

### Logging (on the Raspberry Pi)

```bash
python logger.py
```

- Creates a new CSV in `DATA/` named `DD-MM-YYYY_(log N).csv` — the log number increments automatically so previous runs are never overwritten
- Press `Ctrl+C` to stop; the file is saved automatically

**Configuration** — edit these constants at the top of `logger.py`:

| Constant | Default | Description |
|---|---|---|
| `BUFFER` | `0.1` | Seconds between readings (10 Hz) |
| `SEA_LEVEL_PRESSURE` | `1013.25` | Calibrate to local conditions before launch |
| `LOG_DIR` | `./DATA/` | Output directory |

### Graphing (on your laptop)

```bash
Rscript graphing.R "DD-MM-YYYY_(log N).csv"
```

> **Note:** Quote the filename — parentheses in the name will confuse the shell otherwise.

The script looks for the file inside `DATA/` automatically, so you don't need to include the path prefix.

---

## Exit Codes (logger.py)

| Code | Meaning |
|---|---|
| `0` | Clean stop (Ctrl+C) |
| `1` | I2C bus failed to initialize |
| `2` | Sensor failed to initialize |

---

## CSV Format

Each row is one sensor reading. Columns:

| Column | Unit | Description |
|---|---|---|
| `time` | HH:MM:SS | Wall clock time |
| `rel_time` | seconds | Time since logger started |
| `pressure` | hPa | Absolute atmospheric pressure |
| `temperature` | °C | Temperature at sensor |
| `rel_altitude` | m | Altitude above launch site |
| `abs_altitude` | m | Altitude above sea level |
| `acc_x` | m/s² | Acceleration — X axis |
| `acc_y` | m/s² | Acceleration — Y axis |
| `acc_z` | m/s² | Acceleration — Z axis |