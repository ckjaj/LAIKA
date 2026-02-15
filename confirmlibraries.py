python3 - << 'EOF'
import adafruit_bme280
print("Loaded from:", adafruit_bme280.__file__)
print("Has I2C class:", hasattr(adafruit_bme280, "Adafruit_BME280_I2C"))
EOF
