# Get started

Modify *pvforecast.config* to fit your application.

Launch the C-written daemon with *./c-codes/pvforecastd*. This has been compiled for *Raspbian*, and i should work in all Debian/Debian-like distributions.

You can compile it within your environment with "gcc pvforecastd.c -o pvforecastd".

# Python dependecies

The following modules are required:

* paho.mqtt.client
* json
* numpy
* pytz
* requests
* csv

# Release info

This is version 0.2. 

The sunrise and sunset are automatically updated by the script, allowing to run it only during daytime.
