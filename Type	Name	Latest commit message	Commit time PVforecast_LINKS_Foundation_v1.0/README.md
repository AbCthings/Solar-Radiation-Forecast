# Get started

1) Modify *pvforecast.config* to fit your application.

2) Launch the C-written daemon with *./c-codes/pvforecastd*. This has been compiled for *Raspbian*, and it should work in all Debian/Debian-like distributions. You can compile it within your environment with "gcc pvforecastd.c -o pvforecastd".

3) As an <b>alternative</b> you can directly launch the Python script to perform the forecast, giving the required parameters.

# Python dependecies

The following modules are required:

* paho.mqtt.client
* json
* numpy
* pytz
* requests
* csv

# Release info

This is version 1.0. 

The sequence of operations is:
1) Perform solar radiation forecast
2) Send the forecast to MQTT broker in topic "SolarForecastTopic"
3) Update sunrise/sunset in configuration file (if enabled)
4) Sleep
