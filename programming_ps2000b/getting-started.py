from time import strftime as now, sleep
import serial
import struct

FORMAT = '%Y-%m-%d %H:%M:%S'
ser = serial.Serial('COM3', baudrate=115200, parity='O', stopbits=1, timeout=1)


ask_queue_untrimmed = [
    '75 00 47 00 BC', # (Single model or output 1 of a triple model)
    '75 01 47 00 BD'  #(Single model or output 2 of a triple model)
    ]
ask_queue_hex = [hex_string.replace(' ', '') for hex_string in ask_queue_untrimmed]
ask_queue_data = [bytes.fromhex(hex_string) for hex_string in ask_queue_hex]

index = 0
# SD    # Byte 0: SD (start delimiter)
# DN    # Byte 1: DN (device node)
# OBJ   # Byte 2: OBJ communication objects for a device are addressed by this byte
# DATA  # Byte 3 - 18: Data field
# ST    # Status
# AV    # Voltage
# AC    # Current
# CS    # Word x: CS (check sum)

import numpy  # Import numpy
import matplotlib.pyplot as plt #import matplotlib library
from drawnow import *

plt.ion() #Tell matplotlib you want interactive mode to plot live data
cnt=0

plts = [{'volt': [], 'current': []}, {'volt': [], 'current': []}]

def makeFig(): #Create a function that makes our desired plot
    maxs = max((plts[0]['volt'] + plts[1]['volt'])) + 2
    plt.ylim(0, maxs)                                 #Set y min and max values
    # plt.title('My Live Streaming Sensor Data')      #Plot the title
    plt.grid(True)                                  #Turn the grid on
    plt.ylabel('Voltage')                            #Set ylabels
    plt.plot(plts[0]['volt'], 'ro-', label='Ch1 Voltage')       #plot the temperature
    plt.plot(plts[1]['volt'], 'yo-', label='Ch2 Voltage')  # plot the temperature
    plt.legend(loc='upper left')                    #plot the legend

    plt2=plt.twinx()                                #Create a second y axis
    maxs = max((plts[0]['current'] + plts[1]['current'])) + 1
    plt.ylim(0, maxs)                           #Set limits of second y axis- adjust to readings you are getting

    plt2.plot(plts[0]['current'], 'b^-', label='Ch1 Current') #plot pressure data
    plt2.plot(plts[1]['current'], 'g^-', label='Ch2 Current')  # plot pressure data
    plt2.set_ylabel('Current')                    #label second y axis
    plt2.ticklabel_format(useOffset=False)           #Force matplotlib to NOT autoscale y axis
    plt2.legend(loc='upper right')                  #plot the legend


while True:
    try:
        ser.write(ask_queue_data[index])
        data = ser.read(11)
        t = iter(data.hex())
        # print(len(data), ' '.join(a+b for a, b in zip(t, t)))
        SD, DN, OBJ, QDS, ST, AV, AC, CS = struct.unpack('>5B3H', data)

        volt = AV * 42 / 25600
        current = AC * 6 / 25600
        print(DN, volt, current)
        plts[DN]['volt'].append(volt)
        plts[DN]['current'].append(current)

        index += 1
        if index >= len(ask_queue_data):
            drawnow(makeFig)  # Call drawnow to update our live graph
            plt.pause(.000001)  # Pause Briefly. Important to keep drawnow from crashing
            cnt = cnt + 1
            if (cnt > 150):  # If you have 50 or more points, delete the first one from the array
                for lst in plts:
                    for key, val in lst.items():
                        val.pop(0) # This allows us to just see the last 50 data points
            index = 0
        sleep(0.1)
    except (KeyboardInterrupt, SystemExit, EOFError):
        break