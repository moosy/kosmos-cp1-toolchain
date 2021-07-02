#!/usr/bin/python
from __future__ import division
from gpiozero import LED, Button
from time import sleep
import json
import sys

if len(sys.argv) < 2:
  print("Usage: "+sys.argv[0]+" filename.json");
  sys.exit(1)

fn = sys.argv[1]

if fn[-5:] != ".json":
  print("ERROR: File does not end in .json");
  sys.exit(1)

fo = fn.replace("json","koa");

cmd = { 
  0 : "  #",
  1 : "HLT",
  2 : "ANZ",
  3 : "VZG",
  4 : "AKO",
  5 : "LDA",
  6 : "ABS",
  7 : "ADD",
  8 : "SUB",
  9 : "SPU",
  10 : "VGL",
  11 : "SPB",
  12 : "VGR",
  13 : "VKL",
  14 : "NEG",
  15 : "UND",
  16 : "P1E",
  17 : "P1A",
  18 : "P2A",
  19 : "LIA",
  20 : "AIS",
  21 : "SIU",
  22 : "P3E",
  23 : "P4A",
  24 : "P5A"
}

with open(fn) as f:
    indata = json.load(f)
    f.close()

for k,v  in sorted(indata.items()):
    print (k + ':  '+
         cmd.get(v[0],'-?-')+' '+str(v[1]).zfill(3)+
         '   '+str(v[0]).zfill(2)+'.'+str(v[1]).zfill(3)  )
