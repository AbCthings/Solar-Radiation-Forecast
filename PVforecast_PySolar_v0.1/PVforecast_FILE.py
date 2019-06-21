# ***************************************************************
# This Python script performs the forecast of the solar radiation (W/m^2) for the next day with respect to the moment of execution.
# (for instance, if I call it the 1st of the month, it will report the forecast from the 2nd to the 8th included)
# The solar radiation forecast is then sent to an MQTT broker, with an associated timestamp. The time step of the previsions is 60 seconds.
# ***************************************************************

# *************************** IMPORT SECTION ***************************
import paho.mqtt.client as mqtt
import os
import sys
import json
import random
import time as tempo

import pysolar
import numpy as np
from datetime import *
import pytz as tz
import requests
import pandas as pd
# **********************************************************************


# *************************** FORECAST SECTION ***************************
dt_start = datetime.combine(datetime.now().date(), time(0,0,0))
dt_end = datetime.combine(datetime.now().date() + timedelta(days=1), time(0,0,0))
'''
lat, lon, elevation = 45, 11, 100
step = 60
alt_func = lambda t: pysolar.solar.get_altitude(lat, lon, t)
alt_func_vect = np.vectorize(alt_func)
sim_time_array = np.arange(dt_start, dt_end, timedelta(seconds=step)).astype(datetime)
altitudes = alt_func_vect(sim_time_array)
rad_func = lambda dateArray, altitude_deg: pysolar.radiation.get_radiation_direct(dateArray, altitude_deg)
rad_func_vect = np.vectorize(rad_func)
radiations = rad_func_vect(sim_time_array, altitudes)
radiations[altitudes <= 0] = 0
irradiations = radiations * np.sin(np.deg2rad(altitudes))
def moving_average(a, n=3):
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n
def convolution(array):
    box_pts = 21
    box = np.ones(box_pts) / box_pts
    return np.convolve(array, box, mode='same')
def addNoise(irrad, sim_step):
    w_id, w_key = '39df55d0', 'afce27bf61cdfc4cdd3ae5b5281e39dc'
    url = 'http://api.weatherunlocked.com/api/forecast/'\
    +str(46)+','+str(12)+'?app_id='+w_id+'&app_key='+w_key
    response = requests.get(url)
    #print(response.json())
    cloud_presence = []
    temperature = []
    for d in range(len(response.json()['Days'])):
        for h in range(len(response.json()['Days'][d]['Timeframes'])):
            cloud_presence.append(response.json()['Days'][d]['Timeframes'][h]['cloudtotal_pct'])
            temperature.append(response.json()['Days'][d]['Timeframes'][h]['temp_c'])
            df_weather = pd.DataFrame(dict(cloud_presence=np.array(cloud_presence).repeat(3 * (3600 / step)),
            temperature=np.array(temperature).repeat(3 * (3600 / step))))
    if len(df_weather) >= len(irradiations):
        cloud_array = df_weather['cloud_presence'][:len(irradiations)]
    elif len(df_weather) < len(irradiations):
        cloud_array = df_weather['cloud_presence']
    pdf_func = lambda j: np.mean(np.random.choice(2, 10, 2, p=[j, 1 - j]))
    pdf_func_vect = np.vectorize(pdf_func)
    pdfs = pdf_func_vect(cloud_array / 100)
    resulting_radiation = irradiations * pdfs
    return resulting_radiation, df_weather
A, j = addNoise(irradiations, step)
final_results = convolution(A)
# **********************************************************************
'''

# temporary fix until Hamid sistema il prediction module (math range error)
final_results = range(1440)

'''
# *************************** MQTT SECTION ***************************
# Set TB variables  
THINGSBOARD_HOST = 'demo.thingsboard.io'
ACCESS_TOKEN = 'nbRuILwwxyl15okusFUc'
# Create MQTT client
client = mqtt.Client()
# Set access token
client.username_pw_set(ACCESS_TOKEN)
# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
client.connect(THINGSBOARD_HOST, 1883, 60)
client.loop_start()
# Declare data format
sensor_data = {"ts":0, "values":{"pv_forecast":0}}
# THE TIMESTAMP ARE 1 HOUR EARLIER BECAUSE IN UTC FORMAT
dt_start_TIMESTAMP = tempo.mktime(dt_start.timetuple())
dt_end_TIMESTAMP = tempo.mktime(dt_end.timetuple())
# SINCE WE ARE USING A SENSOR LOCATED IN TURIN (UTC+1), WE ADD 1 HOUR TO THE TIME REFERENCE
#dt_start_TIMESTAMP += 3600
#dt_end_TIMESTAMP += 3600
# THE CURRENT TIMESTAMP VARIABLE, in UNIX milliseconds format
current_TIMESTAMP = int(dt_start_TIMESTAMP * 1000)
# UPLOAD THE FORECAST WITH CORRECT TIMESTAMP
try:
    for i in range(len(final_results)):
        
        #client.connect(THINGSBOARD_HOST, 1883, 60)
        
        pv_value = final_results[i]
        pv_timestamp = int(current_TIMESTAMP)
        
        # Insert the data in a suitable format
        sensor_data['ts'] = pv_timestamp
        sensor_data['values']['pv_forecast'] = pv_value
        
        # Send data to ThingsBoard via MQTT
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
        print(i, ") Upload timestamp: ", pv_timestamp, "(", datetime.fromtimestamp(pv_timestamp/1000), ") | Value: ", pv_value)
        
        # update the timestamp, going to next minute (60000 milliseconds)
        current_TIMESTAMP += 60000
        
        # THE DELAY IS NECESSARY TO AVOID THE "WEB_SOCKET: TOO MANY REQUESTS" ERROR
        tempo.sleep(0.1)
        
        #client.disconnect()
        
except KeyboardInterrupt:
    pass    
# Close the MQTT connections
client.loop_stop()
client.disconnect()
# **********************************************************************
'''

# save on a file (per Maurizio)

dt_start_TIMESTAMP = tempo.mktime(dt_start.timetuple())
dt_end_TIMESTAMP = tempo.mktime(dt_end.timetuple())
current_TIMESTAMP = int(dt_start_TIMESTAMP * 1000)
sensor_data = {"ts":0, "values":{"pv_forecast":0}}

f = open("pv_forecast.txt","w+")

for i in range(len(final_results)):
    
    pv_value = final_results[i]
    pv_timestamp = int(current_TIMESTAMP)
    
    sensor_data['ts'] = pv_timestamp
    sensor_data['values']['pv_forecast'] = pv_value
    
    f.write(json.dumps(sensor_data))
    f.write("\r\n")
    
    current_TIMESTAMP += 60000
    
f.close() 
© 2019 GitHub, Inc.
