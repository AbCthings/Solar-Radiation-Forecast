''

*** Solar radiation prediction and MQTT publishing ***

Authors: 
    Hamidreza Mirtaheri, 
    Alessandro Bortoletto 
    
Latest version: 
    29/04/2019
    
Version: 
    1.1
    
Abstract:
    This Python script performs the prediction of the solar radiation (W/m^2), from the 00:00 of the day during which the script is executed.
    The solar radiation forecast is then sent to an MQTT broker, with an associated timestamp, ONLY for the samples with a future timestamp with respect to the current instant.

    The following parameters can be passed via command line (pass '0' to use the default value):
        1) LATITUDE
        2) LONGITUDE
        3) STEP
        4) FORECAST_HORIZON
        5) THINGSBOARD_HOST
        6) BROKER_PORT
        7) ACCESS_TOKEN
        
'''

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
import csv

# **********************************************************************

# *********************** CONFIGURATION SECTION ************************

'''
DEFAULT CONFIGURATION VARIABLES DECLARED HERE
'''
# LOCATION
LATITUDE = 45.065262
LONGITUDE = 7.659192
# FORECAST HORIZON AND TIMESTEP
STEP = 60 # [seconds]
FORECAST_HORIZON = 2 # [days] This value must be between 1 and 6 days
# THINGSBOARD UPLOAD CREDENTIALS
THINGSBOARD_HOST = 'xxx'
BROKER_PORT = 1883
ACCESS_TOKEN = 'xxx'

'''
UPDATE CONFIGURATION VARIABLES WITH COMMAND LINE ARGUMENTS

The arguments shall be passed with the following sequence:
1) LATITUDE
2) LONGITUDE
3) STEP
4) FORECAST_HORIZON
5) THINGSBOARD_HOST
6) BROKER_PORT
7) ACCESS_TOKEN

If you want to use the default value for a parameter, pass '0' in the related command line argument

'''
# Declare input arguments variables
arg_latitude = LATITUDE
arg_longitude = LONGITUDE
arg_step = STEP
arg_horizon = FORECAST_HORIZON
arg_host = THINGSBOARD_HOST
arg_port = BROKER_PORT
arg_token = ACCESS_TOKEN

if(len(sys.argv)<8):
    print("\nNot enough input arguments. Using default configuration.")
else:
    if(len(sys.argv)>8):
        print("\nToo many input arguments. Using default configuration.")
    else:
        # Import all the command line arguments and check argument quality
        uncorrectFlag = False
        if(sys.argv[1]!='0'): # If users wants to specify a custom LATITUDE value
            arg_latitude = float(sys.argv[1])
            if(arg_latitude<-90 or arg_latitude>90):
                uncorrectFlag = True
        if(sys.argv[2]!='0'): # If users wants to specify a custom LONGITUDE value
            arg_longitude = float(sys.argv[2])
            if(arg_longitude<-180 or arg_longitude>180):
                uncorrectFlag = True
        if(sys.argv[3]!='0'): # If users wants to specify a custom STEP value
            arg_step = int(sys.argv[3])
            if(arg_step<1):
                uncorrectFlag = True
        if(sys.argv[4]!='0'): # If users wants to specify a custom FORECAST_HORIZON value
            arg_horizon = int(sys.argv[4])
            if(arg_horizon<1 or arg_horizon>6):
                uncorrectFlag = True
        if(sys.argv[5]!='0'): # If users wants to specify a custom THINGSBOARD_HOST value
            arg_host = sys.argv[5]
            if len(arg_host)<3:
                uncorrectFlag = True
        if(sys.argv[6]!='0'): # If users wants to specify a custom BROKER_PORT value
            arg_port = int(sys.argv[6])
            if(arg_port<10):
                uncorrectFlag = True
        if(sys.argv[7]!='0'): # If users wants to specify a custom ACCESS_TOKEN value
            arg_token = sys.argv[7]
            if(len(arg_token)<20):
                uncorrectFlag = True   

        if uncorrectFlag:
            print("\nThere is a format error in the input arguments. Rolling back to default configuration.")
        else:
            # If there are no errors, update the configuration variables
            LATITUDE = arg_latitude
            LONGITUDE = arg_longitude
            STEP = arg_step
            FORECAST_HORIZON = arg_horizon
            THINGSBOARD_HOST = arg_host
            BROKER_PORT = arg_port
            ACCESS_TOKEN = arg_token
            print("\nUsing the user defined configuration (via command line arguments).")
        
# **********************************************************************

# *********************** SOLAR FORECAST SECTION ***********************
'''
Compute the solar radiation prediction

NB: We modified the method "get_radiation_direct()" of the class "radiation" of the package "pysolar", as in the following:

def get_radiation_direct(when, altitude_deg):
    # from Masters, p. 412
    day = when.utctimetuple().tm_yday
    flux = get_apparent_extraterrestrial_flux(day)
    optical_depth = get_optical_depth(day)
    air_mass_ratio = get_air_mass_ratio(altitude_deg)
    AlesandrosVar = optical_depth * air_mass_ratio
    if AlesandrosVar< -10:
        AlesandrosVar= -10
    return flux * math.exp(-1 * AlesandrosVar)
    
'''

# This method performs a convolution of the array passed as parameter
def convolution(array):
    box_pts = 21
    box = np.ones(box_pts) / box_pts
    return np.convolve(array, box, mode='same')

'''
# THIS FUNCTION USES PANDAS! I REMOVED IT TO MAKE LIGHTER THE SCRIPT FOR THE RASPBERRY PI 
# This method adds the noise (due to clouds) to the solar irradiation timeseries
def addNoise(irrad, sim_step, lat, lon):
    w_id, w_key = '39df55d0', 'afce27bf61cdfc4cdd3ae5b5281e39dc'
    url = 'http://api.weatherunlocked.com/api/forecast/'\
    +str(lat)+','+str(lon)+'?app_id='+w_id+'&app_key='+w_key
    response = requests.get(url)
    cloud_presence = []
    temperature = []
    for d in range(len(response.json()['Days'])):
        for h in range(len(response.json()['Days'][d]['Timeframes'])):
            cloud_presence.append(response.json()['Days'][d]['Timeframes'][h]['cloudtotal_pct'])
            temperature.append(response.json()['Days'][d]['Timeframes'][h]['temp_c'])
            df_weather = pd.DataFrame(dict(cloud_presence=np.array(cloud_presence).repeat(3 * (3600 / sim_step)),
            temperature=np.array(temperature).repeat(3 * (3600 / sim_step))))
    if len(df_weather) >= len(irradiations):
        cloud_array = df_weather['cloud_presence'][:len(irradiations)]
    elif len(df_weather) < len(irradiations):
        cloud_array = df_weather['cloud_presence']
    pdf_func = lambda j: np.mean(np.random.choice(2, 10, 2, p=[j, 1 - j]))
    pdf_func_vect = np.vectorize(pdf_func)
    pdfs = pdf_func_vect(cloud_array / 100)
    resulting_radiation = irradiations * pdfs
    return resulting_radiation, df_weather
'''

# THIS FUNCTION DOESN'T USE PANDAS
def addNoise(irrad, sim_step, lat, lon):
    w_id, w_key = '39df55d0', 'afce27bf61cdfc4cdd3ae5b5281e39dc'
    url = 'http://api.weatherunlocked.com/api/forecast/'\
    +str(lat)+','+str(lon)+'?app_id='+w_id+'&app_key='+w_key
    response = requests.get(url)
    cloud_total_perceptions, cloud_low_level, cloud_mid_level, cloud_high_level, temperature = [], [], [], [], []
    for d in range(len(response.json()['Days'])):
        for h in range(len(response.json()['Days'][d]['Timeframes'])):
            cloud_total_perceptions.append(response.json()['Days'][d]['Timeframes'][h]['cloudtotal_pct'])
            cloud_low_level.append(response.json()['Days'][d]['Timeframes'][h]['cloud_low_pct'])
            cloud_mid_level.append(response.json()['Days'][d]['Timeframes'][h]['cloud_mid_pct'])
            cloud_high_level.append(response.json()['Days'][d]['Timeframes'][h]['cloud_high_pct'])
            temperature.append(response.json()['Days'][d]['Timeframes'][h]['temp_c'])
            weather_dict = dict(cloud_total_perceptions=np.array(cloud_total_perceptions).repeat(3 * (3600 / sim_step)),
                                cloud_low_level=np.array(cloud_low_level).repeat(3 * (3600 / sim_step)),
                                cloud_mid_level=np.array(cloud_mid_level).repeat(3 * (3600 / sim_step)),
                                cloud_high_level=np.array(cloud_mid_level).repeat(3 * (3600 / sim_step)),
                                temperature=np.array(temperature).repeat(3 * (3600 / sim_step)))
    if len(weather_dict[list(weather_dict.keys())[0]]) >= len(irradiations):
        cloud_array = weather_dict['cloud_total_perceptions'][:len(irradiations)]
    elif len(weather_dict[list(weather_dict.keys())[0]]) < len(irradiations):
        cloud_array = df_weather['cloud_total_perceptions']
    pdf_func = lambda j: np.mean(np.random.choice(2, 10, 2, p=[j, 1 - j]))
    pdf_func_vect = np.vectorize(pdf_func)
    pdfs = pdf_func_vect(cloud_array / 100)
    resulting_radiation = irradiations * pdfs
    return resulting_radiation, weather_dict

# Setup the start and end time of the prediction
dt_start = datetime.combine(datetime.now().date(), time(0,0,0,tzinfo=tz.timezone("Europe/Rome")))
dt_end = datetime.combine(datetime.now().date() + timedelta(days=FORECAST_HORIZON), time(0,0,0,tzinfo=tz.timezone("Europe/Rome")))

# Get solar altitudes for the specified location, and compute the solar radiation
alt_func = lambda t: pysolar.solar.get_altitude(LATITUDE, LONGITUDE, t)
alt_func_vect = np.vectorize(alt_func)
sim_time_array = np.arange(dt_start, dt_end, timedelta(seconds=STEP)).astype(datetime)

# The following line of code is to assign a correct timezone awareness to each entry of the array
new_array = []
for i in range(len(sim_time_array)):
	new_array.append(sim_time_array[i].replace(tzinfo=tz.timezone("Europe/Rome")))
sim_time_array = new_array

altitudes = alt_func_vect(sim_time_array)
rad_func = lambda dateArray, altitude_deg: pysolar.radiation.get_radiation_direct(dateArray, altitude_deg)
rad_func_vect = np.vectorize(rad_func)
radiations = rad_func_vect(sim_time_array, altitudes)
radiations[altitudes <= 0] = 0
irradiations = radiations * np.sin(np.deg2rad(altitudes))

# Add the noise to the "pure" solar radiation vector
appliedNoiseIrradiation, WD = addNoise(irradiations, STEP, LATITUDE, LONGITUDE)

# Compute the final result by performing a convolution
final_results = convolution(appliedNoiseIrradiation)

print("\nSolar radiation prediction successfully computed.\n")

# **********************************************************************

# *********************** MQTT UPLOAD SECTION ************************

'''
Upload the results to ThingsBoard with correct timestamp associated. Furthermore, save the forecast and all the used data in a log file.
'''

# Create MQTT client
client = mqtt.Client()
# Set access token
client.username_pw_set(ACCESS_TOKEN)
# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
client.connect(THINGSBOARD_HOST, BROKER_PORT, 60)
client.loop_start()
# Declare data format
sensor_data = {"ts":0, "values":{"pv_forecast":0}}
# THE TIMESTAMP ARE 1 HOUR EARLIER BECAUSE IN UTC FORMAT
dt_start_TIMESTAMP = tempo.mktime(dt_start.timetuple())
dt_end_TIMESTAMP = tempo.mktime(dt_end.timetuple())
# THE CURRENT TIMESTAMP VARIABLE, in UNIX milliseconds format
current_TIMESTAMP = int(dt_start_TIMESTAMP * 1000)

# UPLOAD THE FORECAST WITH CORRECT TIMESTAMP
# --> Only the prediction referring to the future is uploaded
# oraTsRoma refers is the timestamp at which the computation (prediction) is done
ora = datetime.combine(datetime.now().date(), datetime.now().time())
oraTsRoma = int(tempo.mktime(ora.timetuple()) * 1000)
print("\nI am sending the following data to LinksBoard:\n")
try:

	# Open the log file (.csv) and write the title
	try:
		logTitle = ['Timestamp', ' Theory_Irradiation', 'Forecast_Irradiation', 'Cloud_Low', 'Cloud_Mid', 'Cloud_High', 'Cloud_Tot', 'Temperature']
		fileName = "log-" + datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + ".csv"
		filePath = "/home/PVforecast/prediction-logs/"
		with open(filePath+fileName, 'w', newline='') as csv_file:  
			csv_writer = csv.writer(csv_file, delimiter=';')
			csv_writer.writerow(logTitle)
		csv_file.close()
	except IOError:
		print("\nAn error occoured while opening log file.")
		pass

	# Send the values via MQTT and concurrently save them into the log file
	for i in range(len(final_results)):
		pv_value = final_results[i]
		pv_timestamp = int(current_TIMESTAMP)
        	#*******************************************
        	# This condition checks the current time to decide wether to upload the result or not
		if(oraTsRoma<pv_timestamp):  # Upload the result, it is a prediction for the future  
			# Insert the data in a suitable format
			sensor_data['ts'] = pv_timestamp
			sensor_data['values']['pv_forecast'] = pv_value
            		# Send data to ThingsBoard via MQTT
			client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
			print("Upload timestamp: ", pv_timestamp, "(", datetime.fromtimestamp(pv_timestamp/1000), ") | Value: ", pv_value)
	        # THE DELAY IS NECESSARY TO AVOID THE "WEB_SOCKET: TOO MANY REQUESTS" ERROR
		#tempo.sleep(0.05)
		# Save the results in the log file
		# The line has the following format: ['Timestamp', ' Theory_Irradiation', 'Forecast_Irradiation', 'Cloud_Low', 'Cloud_Mid', 'Cloud_High', 'Cloud_Tot', 'Temperature']
		try:
			logDataLine = [pv_timestamp,str(irradiations[i]),str(pv_value),WD['cloud_low_level'][i],WD['cloud_mid_level'][i],WD['cloud_high_level'][i],WD['cloud_total_perceptions'][i],WD['temperature'][i]]
			with open(filePath+fileName, 'a', newline='') as csv_file:
				csv_writer = csv.writer(csv_file, delimiter=';')
				csv_writer.writerow(logDataLine)
			csv_file.close()
		except IOError:
			print("\nAn error occoured while opening log file.")
			pass

		# update the timestamp, going to next timestep (in milliseconds)
		current_TIMESTAMP += STEP * 1000

except KeyboardInterrupt:
    print("\nThe user manually interrputed the MQTT upload using the keyboard.")
    pass

# Close the MQTT connections
client.loop_stop()
client.disconnect()
print("\nSolar radiation prediction successfully published via MQTT.")
