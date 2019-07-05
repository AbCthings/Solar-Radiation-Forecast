# Info & example
Perform a georeferenced forecast of the solar radiation.

An example for (lat,lon) = (45.065262,7.659192) can be found here: https://linksboard.polito.it/dashboard/355f6f90-85e6-11e9-acf5-fb7ea3e0493d?publicId=8bc0b440-85f3-11e9-acf5-fb7ea3e0493d

# How it works
These Python scripts perform the forecast of the solar radiation (W/m^2) for a given time period, considering the meteorological conditions, the season and the sun position.

The solar radiation forecast is then sent to an MQTT broker, with an associated timestamp.

Relevant variables are also logged in a local .csv file.
