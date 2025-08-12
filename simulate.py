from pykml import parser
import sys
import time
import datetime
import random
import ssl
import select
import math
import socket, json, requests

# CoT route simulator
# Published under the MIT licence
# Copyright 2023 Farrant Consulting Ltd
#
# Courtesy of CloudRF.com - "The API for RF"


# Array for our points
route = []

# BOT VARIABLES
speed = 5 # seconds
bots = 4 # bots to insert. These will share the same cert but TAK server allows this madness
interpolation=1 # Smooth our KML route to fine(r) points

# TAK SERVER VARIABLES
TAK_SERVER_PORT = 8089        		# The SSL / CoT port used by the server for XML
SSL_VERIFY = False                      # Set to False for a self signed cert on a private server 		
UDP_BUFFER_SIZE = 4096

if len(sys.argv) < 2:
	print("No KML file specified eg. simulate.py {KML file}")
	quit()

takserver = ""
if len(sys.argv) < 3:
	print("No TAK server specified. Sending UDP broadcast instead. eg. simulate.py {KML file} {Server IP}")
else:
	takserver = sys.argv[2]

kml = sys.argv[1]


if len(sys.argv) > 3:
	speed = int(sys.argv[3])


print("Using KML %s with interval %d and %d bots" % (kml,speed,bots))
print("TAK server: %s" % takserver)

xml = parser.parse(kml).getroot().Document


# SSL options
TAK_SERVER_ADDRESS = takserver 	#"116.202.56.2"  	# The TAK server's hostname or IP address

# SSL 
ssl_path="ssl/"
ca_cert = ssl_path+'ca.pem'                      
client_cert = ssl_path+'simulator.pem'               
client_key = ssl_path+'simulator.key'     

context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert)
context.options |= ssl.OP_NO_SSLv2 
context.options |= ssl.OP_NO_SSLv3
context.load_cert_chain(certfile=client_cert, keyfile=client_key,password='atakatak')
	

# Extract coordinates into array
for pm in xml.Placemark:
	path = str(pm.LineString.coordinates)
	for pt in path.strip("\t\n").split("\n"):
		point = pt.split(",")
		if len(point) > 2:
			#print(point)
			route.append([float(point[1]),float(point[0])])

# Interpolate the points 
bigroute = []
p=0
while p < len(route)-1:
	xf = (route[p][0] - route[p+1][0])/interpolation
	yf = (route[p][1] - route[p+1][1])/interpolation
	f=1
	while f <= interpolation:
		xstep = f * xf
		ystep = f * yf
		bigroute.append([route[p][0]+xstep,route[p][1]+ystep])
		f+=1
	p+=1

# Comment this out to just use the KML points as defined.
route=bigroute

def register(bot):
	ts=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
	tots=(datetime.datetime.now()+datetime.timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
	msg='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\
	<event version="2.0" uid="'+bot["uid"]+'" type="a-f-G-U-C" time="'+ts+'" start="'+ts+'" stale="'+tots+'" how="h-e">\
	<point lat="'+str(bot["lat"])+'" lon="'+str(bot["lon"])+'" hae="1" ce="9999999" le="9999999"/>\
	<detail><takv os="0" version="1.0" device="" platform="BOT"/>\
	<contact callsign="'+bot["cs"]+'" endpoint="*:-1:stcp"/><uid Droid="'+bot["uid"]+'"/>\
	<precisionlocation altsrc="" geopointsrc="USER"/><__group role="Team Member" name="Cyan"/>\
	<status battery="100"/><track course="0.0" speed="0.0"/></detail></event>'
	return msg.encode("utf-8")

start=0
multiplier=10#len(route)/bots

if takserver:
	# Connect to a TAK server with SSL + mutual auth
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ssl = context.wrap_socket(sock, server_side=False, server_hostname=TAK_SERVER_ADDRESS)
else:
	# UDP BCAST :)
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

if takserver:
	with ssl as s:
		s.connect((TAK_SERVER_ADDRESS, TAK_SERVER_PORT))
else:
	while True:

		# Both SSL and UDP start here
		while True:
			v = 1
			print(start)
			while v <= bots:
				name = "CS%02d" % v
				p = round(start + (v*multiplier))
				if p > len(route)-1:
					p = p - len(route)

				lat=route[p][0] 
				lon=route[p][1] 

				if p >= len(route):
					p -= len(route)

				reported=datetime.datetime.now().isoformat()
				v+=1
				bot = {"uid": name,"cs": name, "lat": lat, "lon": lon}
				print("%s @ position %d" % (bot,p))
				if takserver:
					s.sendall(register(bot)) 
				else:
					sock.sendto(register(bot), ('<broadcast>', 4242))

			start+=1
			if start == len(route): # back to the start!
				print("Start = 0")
				start=0
			time.sleep(speed)