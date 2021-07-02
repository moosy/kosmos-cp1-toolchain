# kosmos-cp1-toolchain
Toolchain for the 1980s Kosmos-CP1 learning computer

This is a toolchain for owners of the brilliant Kosmos CP1 learning computer.
See https://de.wikipedia.org/wiki/Kosmos_CP1 for details.
A comprehensive collection of documentation can be found at 
http://www.8bit-homecomputermuseum.at/computer/kosmos_computer_praxis_cp1.html .

This toolchain consists of the following tools:

kosmos_recv.py filename.json
----------------------------

A python script that can transfer the contents of the CP1 memory to a .json file.
It is designed to run on a raspberry pi, where one GPIO Pin (I use GPIO 26) has to 
be connected to Pin 8 at Port 1 of the CP1.

Beware: The CP1 is a 5V device, therefore the voltage to the raspi has to be limited.
It turns out a simple zener diode with a resistor does the job:
                     
GPIO: --------o-----[1 kOhm]------ Port 1/8
              |
            -----,
              ^     Zener diode 3,3 V
             / \
            -----
              |
GND:  --------o-------------------- GND 

After the script has been started, press CAS on your CP1.
Note the CP1 will wait 16 seconds before starting the transfer.

The transfer will take about 3,5 mins or 7 mins with memory expansion installed.
This cannot be sped up, because the CP1 determines the speed of communication.


kosmos_send.py filename.json
----------------------------

The counter part of kosmos_recv.py. Sends a compatible .json file data to the CP1.
After starting the script, press CAL on your CP1.

The data is received and written to the file.
If you don't have a memory extension installed, you might have to press CAS and STP
after the CP1 is ready, because the script still waits for the rest of the data.

