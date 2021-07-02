#!/usr/bin/python -u
from __future__ import division
from gpiozero import LED, Button
from time import sleep
import json
import sys

time_base = 15  # ms, bit is 3x as long

if len(sys.argv) < 2:
  print("Usage: "+sys.argv[0]+" filename.json");
  sys.exit(1)

fn = sys.argv[1]

if fn[-5:] != ".json":
  print("ERROR: File does not end with .json");
  sys.exit(1)



with open(fn) as f:
    indata = json.load(f)
    f.close()


# Rearrange data:
# 1. Command of cell 0 (1 byte).
# 2. Argument, data of cell 127 - 0, descending. Command of cell 0 is omitted
# 3. Command of cell 128 (1 byte)
# 4. Argument, data of cell 255 - 128, descending.

data = [];
data.append(indata["000"][0]); # Command of cell[0];

for i in range(0,128):     # Cell 127 - 0
  data.append(indata[str(127-i).zfill(3)][1])
  if (i < 127):
    data.append(indata[str(127-i).zfill(3)][0])

data.append(indata["128"][0]); # Command of cell[128];
  
for i in range(128,256):     # cell 255 - 128
  data.append(indata[str(383-i).zfill(3)][1])
#  if (i < 255):
  data.append(indata[str(383-i).zfill(3)][0])


led = LED(26, True, True);

t = [ [ time_base * 2, time_base] , [ time_base , time_base * 2 ] ]

print("Starting the transfer to the Kosmos CP1. Make sure that the interface is switched on.")
print(str(len(data))+ " bytes to send.")
print("\nPress CAL on CP1 within 5 seconds.")

led.on()
sleep(5)
cnt = 0;

print("Starting transfer...");
print("...")

for x in data:
  cnt = cnt + 1
  print ('\033[FSending byte '+str(cnt) + ' / ' + str(len(data)) + ' [' + str(x)+ ']    ');
  bits = format(x, "08b")
  bits = bits[::-1]
  
  for bit in bits:
#    print('  Bit ' + bit);
    p = t[int(bit)]
    frst = p[0]
    scnd = p[1]
#    print('    Sending ' + str(frst) + ' high and ' + str(scnd) + ' low')
    led.off()
    sleep(frst / 1000)
    led.on()
    sleep(scnd / 1000)
#    print("ok")        
    
print("Transfer complete.");