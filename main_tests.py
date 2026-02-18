import sys
import datetime as dt
import csv
import time
import os

import math

#system exit (0, keyboard interruption
#		  	  1, i2c failure
#			  2, sensor failure
#


#---------#
BME_ADDRESS = 0x77
LIS_ADDRESS = 0x19

SEA_LEVEL_PRESSURE = 1013.25

LOG_DIR = "./DATA/" #note: needs to be ./(name)/ for formatting
CSV_NAME = dt.datetime.now().strftime("%d-%m-%Y")

BUFFER = .25

#---------#

def get_csv_path():
	import pathlib as path

	#creates ./DATA if it doesn't exist
	data_Path = path.Path(LOG_DIR)
	data_Path.mkdir(exists_ok=True)
	
	

	#return a unique filename in form ./DATA/[date]_(log *).csv 
		#note: cannot be bigger than a 64 bit int
	x=1
	while(x < sys.maxsize):
		filestr = f"{LOG_DIR}{CSV_NAME}_(log {x}).csv"
		file_path = path.Path(filestr)
		if not file_path.exists(): 
			return filestr
		x += 1
	
def init_i2c():
	import board
	return board.I2C()

def init_bme(i2c):
	from adafruit_bme280 import basic as adafruit_bme280
	bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, BME_ADDRESS)	
	bme.sea_level_pressure = SEA_LEVEL_PRESSURE #calibrate
	return bme

def init_lis(i2c):
	import adafruit_lis3dh
	return adafruit_lis3dh.LIS3DH_I2C(i2c, LIS_ADDRESS)



def main():
	# init I2C
	try:
		i2c = init_i2c()
	except Exception as e:
		print(f"i2c failed to initialize: {e}")
		sys.exit(1)	

	#init sensors
	try:
		bme280 = init_bme(i2c)

	except Exception as e:
		print(f"bme280 failed to initialize: {e}")
		sys.exit(2)

	try:
		lis3dh = init_lis(i2c)
	except Exception as e:
		print(f"lis3dh failed to initialize: {e}")
		sys.exit(2)

	#get initial altitude and pressure readings (for relative pressure and altitude measurements)


	baseAlt = bme280.altitude
	basePre = bme280.pressure
		#note: could make this more accurate by getting a mean of various values, integrate later???

	baseTime = dt.datetime.now()


	#initialize csv file
	csv_path = get_csv_path()

	data = open(csv_path, 'w', newline="")
	fields = [
		"time",
		"rel_time",
		"pressure",
		"temperature",
		"rel_altitude",
		"abs_altitude",
		"acc_x",
		"acc_y",
		"acc_z"
		]
	writer = csv.DictWriter(data, fieldnames=fields)
	writer.writeheader()



	#while loop to log data into csv
	while(True):
		try:
			#get data
			pressure = bme280.pressure
			temperature = bme280.temperature
			abs_altitude = bme280.altitude
			rel_altitude = abs_altitude - baseAlt
			acc_x, acc_y, acc_z = lis3dh.acceleration

			time_now = dt.datetime.now()

			rel_time = time_now - baseTime

			writer.writerow({
				"time": time_now.strftime("%H-%M-%S"),
				"rel_time": rel_time.total_seconds(),
				"pressure": pressure,
				"temperature": temperature,
				"rel_altitude": rel_altitude,
				"abs_altitude": abs_altitude,
				"acc_x": acc_x,
				"acc_y": acc_y,
				"acc_z": acc_z
				})

			time.sleep(BUFFER)
			#in g's
		
		except KeyboardInterrupt:
			print(f"\nStopped. CSV saved at:{csv_path}")
		finally:
			try:
				data.close()
			except Exception:
				pass

if __name__ == "__main__":
	main()










