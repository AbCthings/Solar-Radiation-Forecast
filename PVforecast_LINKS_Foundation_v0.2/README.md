# Get started

Modify pvforecast.config to fit your application.

Launche the daemon "./c-codes/pvforecastd". This has been compiled for Raspbian.

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
