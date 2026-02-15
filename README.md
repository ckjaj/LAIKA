Procedure for testing phase:

streaming data isn't important at the testing stage of the project ->
  save it all to a csv file to examine after the test

0, code procedure 
1, use board and busio libraries to initialize I2C
2, use adafruit -> bme_280, lis3dh libraries to initialize sensors
    sensors at I2C addresses 0x77, 0x18 on rasberry pi, respectively
3, initialize I2C, sensors
4, callibrate barometric readings to find baseline pressure to find relative altitude
5, initialize csv file and it's writer
6, in while loop -
      get data from sensors,
      find altitudes (relative and absolute)
      log data with csv writer
7, close the csv file to save changes

0, tests to ensure the reliability of data 
1, make sure barometric readings are stable and correct

  2, make sure pressure spike at beginning of stage 3 won't fry avionics

  3, ...

  
