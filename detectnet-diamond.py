#!/usr/bin/python3
#
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit person to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
##############################################################################
# from here detectnet-diamont.py
# based on https://github.com/dusty-nv/jetson-inference/blob/master/python/examples/detectnet.py
# modified by coniferconifer as a diamond-shaped mark detector
#
# ./detectnet-diamond.py  --headless=true --camera=/dev/video0 --width=640 --height=480 --model=models/diamond/ssd-mobilenet.onnx --labels=models/diamond/labels.txt --input-blob=input_0 --output-cvg=scores --output-bbox=boxes

# time(sec) from start, date , lat , lon, speed(km/h) , number of diamond  ,confidence level
#
# 881.677 ,2023-03-17 23:48:08 , 33.318686 , 134.6852810833 , 0.0 , 1 , 0.567
# Left,Right,CenterX  148.984375 , 326.25 , 237.6171875

import jetson.inference
import jetson.utils

import argparse
import RPi.GPIO as GPIO
import sys

import time
import datetime

# GPS speed reader
from gps3 import gps3
import threading
import pytz

TIMEZONE=9 # JST

# class to keep GPS speed
class message:
	speed= 5.0 # initial GPS speed  5m/s until GPS fixes
	lat = 0.0
	lon = 0.0
	time = " "

#
# tuning parameters
#
#speedThresh=30.0 # km/h minimum speed to detect and warn the diamond mark 
speedThresh=20.0 # km/h minimum speed to detect and warn the diamond mark 
#speedThresh=0.0 # km/h minimum speed to detect and warn the diamond mark 
minX=150.0 #X range to find diamond mark  in 640x480 camera
maxX=640.0-minX
#confidenceThresh=0.5
confidenceThresh=0.50
rate=0.9 # confidenceE is low pass filtered confidence of every frame (max confidence is used in the same frame) 
#
centerPosition=640.0/2.0


ut = time.time()
utnew = time.time()
# thread to get GPS data
def get_gpsdata(mes):
	for new_data in gps_socket:
		if new_data:
			data_stream.unpack(new_data)
			mes.speed = data_stream.TPV['speed']
			mes.lon = data_stream.TPV['lon']
			mes.lat = data_stream.TPV['lat']
			utc_time = data_stream.TPV['time']
# ISO time to JST localtime
			if utc_time != 'n/a':
				utc_dt = datetime.datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%S.%fZ")
				mes.time = utc_dt + datetime.timedelta(hours=TIMEZONE)


m = message() # instance to hold GPS speed
gps_socket = gps3.GPSDSocket()
data_stream = gps3.DataStream()
gps_socket.connect()
gps_socket.watch()
print('GPS reader thread1 ')
thread1 = threading.Thread(target=get_gpsdata, args=(m,))
print('thread1 start')
thread1.start()

pin_diamond=13 # gpio38 = GPIO_PE6 pin 33
pin_person=6 # gpio200 = GPIO_PZ0 pin 31

def testGPIO():
#set up GPIO
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(pin_diamond,   GPIO.OUT, initial=GPIO.HIGH)
	GPIO.setup(pin_person, GPIO.OUT, initial=GPIO.HIGH)
	time.sleep(1)
	GPIO.output(pin_diamond, GPIO.LOW)
	GPIO.output(pin_person, GPIO.LOW)

# parse the command line
parser = argparse.ArgumentParser(description="Locate objects in a live camera stream using an object detection DNN.", 
                                 formatter_class=argparse.RawTextHelpFormatter, epilog=jetson.inference.detectNet.Usage() +
                                 jetson.utils.videoSource.Usage() + jetson.utils.videoOutput.Usage() + jetson.utils.logUsage())

parser.add_argument("input_URI", type=str, default="", nargs='?', help="URI of the input stream")
parser.add_argument("output_URI", type=str, default="", nargs='?', help="URI of the output stream")
parser.add_argument("--network", type=str, default="ssd-mobilenet-v2", help="pre-trained model to load (see below for options)")
parser.add_argument("--overlay", type=str, default="box,labels,conf", help="detection overlay flags (e.g. --overlay=box,labels,conf)\nvalid combinations are:  'box', 'labels', 'conf', 'none'")
parser.add_argument("--threshold", type=float, default=0.5, help="minimum detection threshold to use") 

is_headless = ["--headless"] if sys.argv[0].find('console.py') != -1 else [""]

try:
	opt = parser.parse_known_args()[0]
except:
	print("")
	parser.print_help()
	sys.exit(0)

testGPIO() # turn on GPIO and off GPIO , send rising edge to ISD1820 board

# load the object detection network
net = jetson.inference.detectNet(opt.network, sys.argv, opt.threshold)

# create video sources & outputs
input = jetson.utils.videoSource(opt.input_URI, argv=sys.argv)
output = jetson.utils.videoOutput(opt.output_URI, argv=sys.argv+is_headless)
n_diamond=0
confidenceE=0.0
# process frames until the user exits
while True:

#reset GPIO before every frame
	GPIO.output(pin_person,GPIO.LOW)
	GPIO.output(pin_diamond,GPIO.LOW)
# capture the next image
	img = input.Capture()
	utnew=time.time()
	confidenceRaw=0.0
	# detect objects in the image (with overlay)
	n_diamond=0
	detections = net.Detect(img, overlay=opt.overlay)
	for detection in detections:
		classid=net.GetClassDesc(detection.ClassID)
		area=detection.Area
		width=detection.Width
		centerPosition = (detection.Left + detection.Right)/2.0
		confidence=detection.Confidence
		if confidenceRaw < confidence :
			confidenceRaw = confidence # get max confidence in the loop

#		if "diamond"==classid :
		if "diamond"==classid :
			n_diamond=n_diamond+1
			if m.speed != "n/a":
				print(f"{time.perf_counter():.3f}",',',end="")
				print( m.time, ',' , m.lat ,',', m.lon, ',', format(float(m.speed)*3.6, ".1f"), ',', n_diamond,',',confidence,',',confidenceE)
				if float(m.speed)*3.6 >= speedThresh: #compare speed by km/h 
					if centerPosition < maxX and centerPosition > minX:
						if  confidenceE > confidenceThresh:
							GPIO.output(pin_diamond, GPIO.HIGH) #if speed is available
							print('diamond: Left,Right,CenterX,lat,lon ',detection.Left, ',',detection.Right,',',centerPosition,',',m.lat,',',m.lon,', detected')
						print(detection)
					else:
						print('diamond: Left,Right,CenterX,lat,lon ',detection.Left, ',',detection.Right,',',centerPosition,',',m.lat,',',m.lon,', outOfRange')
						print(detection)
				else:
						print('diamond: Left,Right,CenterX,lat,lon ',detection.Left, ',',detection.Right,',',centerPosition,',',m.lat,',',m.lon,', underSpeed')
						print(detection)

					
				
			else: # GPS speed is not available
					print(f"{time.perf_counter():.3f}",',',end="")
					print( 0 , ',' , 0 ,',', 0 , ',', 0 , ',', n_diamond)
					if confidence > confidenceThresh :
						print('diamond: Left,Right,CenterX ',detection.Left, ',',detection.Right,',',centerPosition)
						GPIO.output(pin_diamond, GPIO.HIGH) # n/a case
						print(detection)
					
		else:
			if "person"==classid: # ./models/diamond/ssd-mobilenet.onnx is not yet trained for person
				print("found person")
				GPIO.output(pin_person, GPIO.HIGH)

		GPIO.output(pin_diamond, GPIO.LOW) # reset GPIO to low
		GPIO.output(pin_person, GPIO.LOW) # reset GPIO to low
#
# periodical  GPS record here
	if  utnew - ut > 1.0:
		print(f"{time.perf_counter():.3f}",',',end="")
		print( m.time, ',' , m.lat ,',', m.lon, ',', format(float(m.speed)*3.6, ".1f"), ',', n_diamond,',',confidenceE)
		ut=utnew

	if len(detections)>1:
		print("detected {:d} objects in image".format(len(detections)))

	# render the image
	output.Render(img)
	# update confidenceE per frame
	confidenceE=confidenceE*rate+confidenceRaw*(1.0-rate)

	# update the title bar
#	output.SetStatus("{:s} | Network {:.0f} FPS".format(opt.network, net.GetNetworkFPS()))

	# print out performance info
#	net.PrintProfilerTimes()

	# exit on input/output EOS
	if not input.IsStreaming() or not output.IsStreaming():
		break


