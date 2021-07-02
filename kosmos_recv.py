#!/usr/bin/python -u
from __future__ import division
from gpiozero import LED, Button
from time import sleep
import time
import json
import sys


up = '\033[F'

if len(sys.argv) < 2:
  print("Usage: "+sys.argv[0]+" filename.json");
  sys.exit(1)

fn = sys.argv[1]

if fn[-5:] != ".json":
  print("ERROR: File does not end in .json");
  sys.exit(1)

btn = Button(26, True);

def milli_time():
    return int(round(time.time() * 100000))

bit = 0
byte = 0

cnt = 128
cnt_max = 128
cnt_exp_max = 256
iscmd = True
d_cmd = 0;
d_arg = 0;
frst_cmd = 0;

data = {}

print("Receive memory content from Kosmos CP1")
print("Press CAS on CP1!")

btn.wait_for_release()
btn.wait_for_press()
t0 = milli_time()

print("\nReceiving data...\n");


while (cnt < 900):
  btn.wait_for_release()
  t1 = milli_time()
  dt1 = t1 - t0
  if (dt1 > 100000):
    break
  if (dt1 < 2200): print ('  WARNING: release too short ' + str(dt1) + "\n")
  if (dt1 > 7800): print ('  WARNING: release too long ' + str(dt1)+ "\n")

  btn.wait_for_press()
  t0 = milli_time()
  dt2 = t0 - t1
  if (dt2 > 100000):
    break

  if (dt2 < 2200): print ('  WARNING: press too short ' + str(dt2)+ "\n")
  if (dt2 > 7800): print ('  WARNING: press too long '+ str(dt2) +"\n")


#  print ('pressed: '+str(dt2))

  incr = (1<<(bit))  
#  print("Bit "+str(bit)+" Incr "+str(incr))
  
  if (dt1 < dt2):
    byte += incr
#    print("1")
#  else:
#    print("0")
  
  bit += 1
  if (bit >= 8):
    bit = 0
    if (iscmd):
      iscmd = False
      if (cnt == cnt_max):
        frst_cmd = byte
#        print("Firstcmd: "+str(byte))
      elif (cnt == cnt_exp_max):
        frst_cmd = byte
#        print("scndFirstcmd: "+str(byte))
      else:  
        d_cmd = byte
        print(up + "Got cell "+str(cnt).zfill(3) + ": "+str(d_cmd).zfill(2)+"."+str(d_arg).zfill(3))
        data[str(cnt).zfill(3)] = [d_cmd, d_arg]
      cnt = cnt - 1
    else:
      iscmd = True
      d_arg = byte
      if (cnt == 0):
        print(up + "Got cell "+str(cnt).zfill(3) + ": "+str(frst_cmd).zfill(2)+"."+str(d_arg).zfill(3))
        data[str(cnt).zfill(3)] = [frst_cmd, d_arg]
        cnt = cnt_exp_max
      if (cnt == 128):
        print(up + "Got cell "+str(cnt).zfill(3) + ": "+str(frst_cmd).zfill(2)+"."+str(d_arg).zfill(3))
        data[str(cnt).zfill(3)] = [frst_cmd, d_arg]
        cnt = 999
      
    byte = 0 

print("\nWriting file "+fn+"...")
    
with open(fn, 'w') as f:
    json.dump(data, f)
    f.close()
        
print("Transfer finished.")