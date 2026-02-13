import smbus2
import bme280
import sys
import time

port = 1
address = 0x77

bus = smbus2.SMBus(port)

calibration_params = bme280.load_calibration_params(bus, address)

running = True

while(running):
    try:
        time.sleep(.1)
        data = bme280.sample(bus, address, calibration_params)
        
        strData = f"temp: {data.temperature:.2f} dC " + f"pres: {data.pressure:.2f} hPa " + f"humi: {data.humidity:.2f} hPa"
        
        print(strData, end='\r')
    except KeyboardInterrupt:
        print('\n')
        sys.exit(0)
