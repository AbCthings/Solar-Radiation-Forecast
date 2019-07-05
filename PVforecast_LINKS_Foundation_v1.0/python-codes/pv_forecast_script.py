import paho.mqtt.client as mqtt
import os
import sys
import json
import random
import time as tempo
import numpy as np
import datetime
import pytz as tz
import requests
import csv
from tempfile import mkstemp
from shutil import move
from os import fdopen, remove
#import timezonefinder

# **********************************************************************

# *********************** CONFIGURATION SECTION ************************

'''
DEFAULT CONFIGURATION VARIABLES DECLARED HERE
'''
# LOCATION
LATITUDE = 45.065262
LONGITUDE = 7.659192
DECLINATION = 0
TILT = 0
# FORECAST HORIZON AND TIMESTEP
STEP = 60 # [seconds]
FORECAST_HORIZON = 2 # [days] This value must be between 1 and 6 days
# THINGSBOARD UPLOAD CREDENTIALS
THINGSBOARD_HOST = 'localhost'
BROKER_PORT = 1883

'''
UPDATE CONFIGURATION VARIABLES WITH COMMAND LINE ARGUMENTS

The arguments shall be passed with the following sequence:
1) LATITUDE
2) LONGITUDE
3) STEP
4) FORECAST_HORIZON
5) THINGSBOARD_HOST
6) BROKER_PORT

If you want to use the default value for a parameter, pass '0' in the related command line argument

'''
# Declare input arguments variables
arg_latitude = LATITUDE
arg_longitude = LONGITUDE
arg_panel_declination = DECLINATION
arg_panel_tilt = TILT
arg_step = STEP
arg_horizon = FORECAST_HORIZON
arg_host = THINGSBOARD_HOST
arg_port = BROKER_PORT

if(len(sys.argv)<7):
    print("\nNot enough input arguments. Using default configuration.")
else:
    if(len(sys.argv)>7):
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
            print("\nUsing the user defined configuration (via command line arguments).")
 
# **********************************************************************

# *********************** SOLAR FORECAST SECTION ***********************

'''
We have used ASHRAE model for solar irradiance forecast.
This lookup table contains coefficients for average clear day solar radiation calculation for the 21th day of each month.
These values are referred to the ASHRAE Clear Day Solar Flux Model. The table originally comes from ASHRAE Handbook of fundamentals.

https://www.tandfonline.com/doi/pdf/10.1080/15567030701522534
http://www.me.umn.edu/courses/me4131/LabManual/AppDSolarRadiation.pdf

the first column is indicaing the coefficient value for irradiance throughout the year which is subject to dust and vapor presence in the atmosphere, and its unit is W/m^2.
second and this columns are other recommended coefficients used for calculation which are dimensionless values.

'''


# this lookup table contains coefficients for average clear day solar radiation calculation for the 21 day of each month
lookup_table = np.array([
       [0.000e+00, 0.000e+00, 0.000e+00],
       [1.230e+03, 1.420e-01, 5.800e-02],
       [1.215e+03, 1.440e-01, 6.000e-02],
       [1.186e+03, 1.560e-01, 7.100e-02],
       [1.136e+03, 1.800e-01, 9.700e-02],
       [1.104e+03, 1.960e-01, 1.210e-01],
       [1.088e+03, 2.050e-01, 1.340e-01],
       [1.085e+03, 2.070e-01, 1.360e-01],
       [1.107e+03, 2.010e-01, 1.220e-01],
       [1.151e+03, 1.770e-01, 9.200e-02],
       [1.192e+03, 1.600e-01, 7.300e-02],
       [1.221e+03, 1.490e-01, 6.300e-02],
       [1.233e+03, 1.420e-01, 5.700e-02]])

# The reflect cofficients can be partially retreived from the following dictionary.
reflect_coeffs = {'browned_grass':0.2,
                  'bare_soil':0.1,
                  'fresh_snow':0.87,
                  'dirty_snow':0.5}


def convolution(array):
    box_pts = 21
    box = np.ones(box_pts) / box_pts
    return np.convolve(array, box, mode='same')


def addNoise(irradiations, sim_step, lat, lon):
    '''
    addNoise function first calls a weather prediction service (WEATHER UNLOCKED) and then applies the effect of 
    cloud presence to the solar irradiation with a simple probability function.
    '''
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


'''
 ________________________ SETTING THE FORECAST HORIZON AS REQUESTED THROUGH INPUT ARGUMENTS____________________________
########################################################################################################################

 forecast_time_horizon_array: contains forecast horizon's time steps in hour (particular format in which the 15:45 p.m. is "15.75").
 dt_start is the starting point for the forecast horizon and dt_end is th eending point of the forecast window, both as datetime objects.
 sim_time_array instead contains all the steps of forecast as datetime object.
 
'''

forecast_time_horizon_array = np.concatenate([np.arange(0, 24, STEP/3600) for day in range(FORECAST_HORIZON)])
dt_start = datetime.datetime.combine(datetime.datetime.now().date(), 
                                     datetime.time(0,0,0))
dt_end = datetime.datetime.combine(datetime.datetime.now().date() + 
                                   datetime.timedelta(days=FORECAST_HORIZON), 
                                   datetime.time(0,0,0))
sim_time_array = np.arange(dt_start, dt_end, datetime.timedelta(seconds=STEP)).astype(datetime.datetime)


# ______________________________ROUTINE TO CALCULATE SOLAR IRRADIATION STARTS HERE______________________________________
########################################################################################################################


### The year of the simulation should be distinct.
### DLS is an array that build Day Light Saving table hours for entire year. Final built array is "day_light_savings".

dt_year_end = datetime.datetime(dt_start.year, 12, 31).timetuple().tm_yday
forecast_day = dt_start.timetuple().tm_yday
DLS = np.zeros(dt_year_end)
dt_daylight_saving_on = datetime.datetime(dt_start.year, 3, 31).timetuple().tm_yday
dt_daylight_saving_off = datetime.datetime(dt_start.year, 10, 27).timetuple().tm_yday
DLS[dt_daylight_saving_on: dt_daylight_saving_off] = 1
day_light_savings = DLS[forecast_day:forecast_day + FORECAST_HORIZON].repeat(24*(3600/STEP))

### "sun_declination_angle" is a function of specific day of the year.
### "d" is an array with dimension (1, FORECAST_HORIZON*(24*(3600/STEP), although the values are equal for one day.
forecast_request_day = dt_start.timetuple().tm_yday
d = 23.45 * np.sin(np.deg2rad(360/365) * (284 + (forecast_request_day)+np.arange(FORECAST_HORIZON)))
sun_declination_angle = np.repeat(d, 24*(3600/STEP))

### Equation of Time (EoT) returns the exact local solat time drift from official time.
### It can be in minutes or hour, here it is calculated based on hours.
### It is again a vector,  which is equal for specific day.
B = np.radians((360/365)*(forecast_request_day + np.arange(FORECAST_HORIZON) - 81))
eot = (0.1645*np.sin(2*B)) - (0.1255*np.cos(B)) - (0.025*np.sin(B)) ## in hour
# eot = (9.87*np.sin(2*B)) - (7.53*np.cos(B)) - (1.5*np.sin(B))  ## in minutes
equation_of_time = eot.repeat(24*(3600/STEP))


# This section gets the offset from UTC for the location of interest. 
# The offset should be without daylight-saving shift, so it is calculated for epoch = 0 (1970,1,1)
#tf = timezonefinder.TimezoneFinder()
#timezone_str = tf.certain_timezone_at(lat=LATITUDE, lng=LONGITUDE)
#timezone = pytz.timezone(timezone_str)
time_difference_from_UTC = 0 #timezone.utcoffset(datetime.datetime(1970,1,1)).seconds / 3600

# Local Solar Time (lst) calculation
lst = forecast_time_horizon_array + ((1/15) * (time_difference_from_UTC * 15 - LONGITUDE)) + equation_of_time - day_light_savings

# solar angle hour
h = 15*(lst -12)

# Calculation of solar zenith with respect to the exact point of forecast demand. The result is an array of (1, lenght(HORIZON) * 24*(3600/STEP))
cos_zenith = np.cos(np.deg2rad(LATITUDE))*np.cos(np.deg2rad(h))*np.cos(np.deg2rad(sun_declination_angle)) + \
np.sin(np.deg2rad(LATITUDE))*np.sin(np.deg2rad(sun_declination_angle))
solar_zenith = np.rad2deg(np.arccos(cos_zenith))

# Calculation of solar altitude with respect to the exact point of forecast demand. The result is an array of (1, lenght(HORIZON) * 24*(3600/STEP))
# at the end, the negative Altitude values are set to zero as it refers to the time that sun is below the horizon 
sin_altitude = np.cos(np.deg2rad(LATITUDE))*np.cos(np.deg2rad(h))*np.cos(np.deg2rad(sun_declination_angle)) + \
np.sin(np.deg2rad(LATITUDE))*np.sin(np.deg2rad(sun_declination_angle))
solar_altitude = np.rad2deg(np.arcsin(sin_altitude))
solar_altitude[solar_altitude<0] = 0

# Solar Azimuth with respect to the point of simulation. The result is an array of (1, lenght(HORIZON) * 24*(3600/STEP)). 
# It is set to zero for times that the sun's angle with respect to the point of simulation is between 180 and 360 degree.
cos_azimuth =  (1/np.cos(np.deg2rad(solar_altitude))) * ((np.cos(np.deg2rad(sun_declination_angle))*np.sin(np.deg2rad(LATITUDE))\
                                                    *np.cos(np.deg2rad(h)))-(np.sin(np.deg2rad(sun_declination_angle))\
                                                                             *np.cos(np.deg2rad(LATITUDE))))
arccos_azimuth = np.arccos(cos_azimuth)
arccos_azimuth[np.argwhere(np.isnan(arccos_azimuth))] = 0.0
solar_azimuth = np.rad2deg(arccos_azimuth)

# Here the declination of the solar PANEL comes into account. This refers to the panel's azimuth.
surface_solar_azimuth_values = abs(solar_azimuth - DECLINATION)

# Here the TILT declination of the panel comes into effect.
cos_teta = np.cos(np.deg2rad(solar_altitude)) * np.cos(np.deg2rad(surface_solar_azimuth_values)) * np.sin(np.deg2rad(TILT))+\
np.sin(np.deg2rad(solar_altitude)) * np.cos(np.deg2rad(TILT))
incidence_angle_values = np.arccos(cos_teta)

# Following lines of scripts compute the Normal Direct Sun Rays Irradiance on the panel, using the ASHRAE constant values from lookup table.
indexes = [sim_time.month for sim_time in sim_time_array]
A = lookup_table[indexes][:,0]
B = lookup_table[indexes][:,1]
zero_values_index = np.where(solar_altitude==0)
solar_altitude[zero_values_index] = 1
irradiation_direct_normal = (A * np.exp(-B/(np.sin(np.deg2rad(solar_altitude)))))
solar_altitude[zero_values_index] = 0
irradiation_direct_normal[zero_values_index]=0

# Direct flux of sun's rays to the subject panel.
direct_flux = irradiation_direct_normal * np.cos(np.deg2rad(incidence_angle_values))
diffuse_flux_horizontal = lookup_table[dt_start.month][2] * irradiation_direct_normal
diffuse_flux_panel = diffuse_flux_horizontal * ((1+np.cos(np.deg2rad(TILT))) / 2)

# Accounting another important element of the total irradiation which is reflected radiation.
# The reflected radiation highly depends on the surronding environments and covering materials. In the following versions, 
# finding those coefficient will be the duty of a Machine Learning routine 
reflected_radiation = reflect_coeffs['browned_grass'] * direct_flux * ((1-np.cos(TILT))/2)
reflected_radiations = reflected_radiation

#The total irradiation which is in a simplified version the sum of direct, diffuse and reflected radiations, considering the sun's angular position.
irradiation_total = np.sin(np.deg2rad(solar_altitude)) *  (direct_flux + diffuse_flux_panel + reflected_radiations)

# Add the noise to the "pure" solar radiation vector.
appliedNoiseIrradiation, WD = addNoise(irradiation_total, STEP, LATITUDE, LONGITUDE)

# Compute the final result by performing a convolution to obtain a smooth curve.
final_results = convolution(appliedNoiseIrradiation)

print("\nSolar radiation prediction successfully computed.\n")

# **********************************************************************


# **** UPDATE SUNRISE AND SUNSET IN CONFIGURATION FILE ****
'''
Replaces the configuration file with a new one, updating the content.
    * file_path: path of the file to modify
    * pattern: what to look inside the file
    * subst: string to add to the file (in the line below the line with "pattern")
'''
def replace(file_path, pattern, subst):
    #Create temp file
    fh, abs_path = mkstemp()
    #Open a new file
    with fdopen(fh,'w') as new_file:
        #Open the old file
        with open(file_path) as old_file:
            #Iterate all the lines of the old file
            for line in old_file:
                #If we found the correct pattern (es. "[sunrise]"), then modify next line with new value
                if pattern in line:
                    #Write the line with the pattern to the new file
                    new_file.write(line)
                    #Write the new string in the line below
                    new_file.write(subst + "\n")
                    #Skip one row, with the old content
                    next(old_file) 
                #Otherwise just write the old line without replacing stuff
                else:
                    new_file.write(line)
                
    #Remove original file
    remove(file_path)
    #Move new file to replace the old one
    move(abs_path, file_path)

# Compute sunrise and sunset
sunrise_index = np.where(irradiation_total!=0)[0][0]
sunset_index = np.where(irradiation_total!=0)[0][-1]
sunrise_time = sim_time_array[sunrise_index] + datetime.timedelta(hours = DLS[forecast_day-1])
sunset_time = sim_time_array[sunset_index] + datetime.timedelta(hours = DLS[forecast_day+1])

# Check if the automatic update for sunrise/sunset is enabled
enabled = "false"
with open("/home/PVforecast-Paper/pvforecast.config","r") as f:
    for line in f:
        searchphrase = "[updateEnabled]"
        if searchphrase in line:
            # Found it, then save the value
            enabled = next(f)
if(enabled == "true\n"):
	# Replace content in the configuration file
	replace("/home/PVforecast-Paper/pvforecast.config", "[sunrise]", sunrise_time.strftime("%H"))
	replace("/home/PVforecast-Paper/pvforecast.config", "[sunset]", sunset_time.strftime("%H"))


# *********************** MQTT UPLOAD SECTION ************************
'''
Upload the results to ThingsBoard with correct timestamp associated. Furthermore, save the forecast and all the used data in a log file.
'''

# Create MQTT client
client = mqtt.Client()
# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
client.connect(THINGSBOARD_HOST, BROKER_PORT, 60)
client.loop_start()
# Declare data format
sensor_data = {"ts":0, "pv_forecast":0}
# THE TIMESTAMP ARE 1 HOUR EARLIER BECAUSE IN UTC FORMAT
dt_start_TIMESTAMP = tempo.mktime(dt_start.timetuple())
dt_end_TIMESTAMP = tempo.mktime(dt_end.timetuple())
# THE CURRENT TIMESTAMP VARIABLE, in UNIX milliseconds format
current_TIMESTAMP = int(dt_start_TIMESTAMP * 1000)

# UPLOAD THE FORECAST WITH CORRECT TIMESTAMP
# --> Only the prediction referring to the future is uploaded
# oraTsRoma refers is the timestamp at which the computation (prediction) is done
ora = datetime.datetime.combine(datetime.datetime.now().date(), datetime.datetime.now().time())
oraTsRoma = int(tempo.mktime(ora.timetuple()) * 1000)
print("\nI am sending the following data to LinksBoard:\n")
try:

    # Open the log file (.csv) and write the title
    try:
        logTitle = ['Timestamp', ' Theory_Irradiation', 'Forecast_Irradiation', 'Cloud_Low', 'Cloud_Mid', 'Cloud_High', 'Cloud_Tot', 'Temperature']
        fileName = "log-" + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + ".csv"
        filePath = "/home/PVforecast-Paper/prediction-logs/"
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
            sensor_data['pv_forecast'] = pv_value
            		# Send data to ThingsBoard via MQTT
            client.publish('SolarForecastTopic', json.dumps(sensor_data), 1)
            print("Upload timestamp: ", pv_timestamp, "(", datetime.datetime.fromtimestamp(pv_timestamp/1000), ") | Value: ", pv_value)
        # THE DELAY IS NECESSARY TO AVOID THE "WEB_SOCKET: TOO MANY REQUESTS" ERROR
        #tempo.sleep(0.05)
        # Save the results in the log file
        # The line has the following format: ['Timestamp', ' Theory_Irradiation', 'Forecast_Irradiation', 'Cloud_Low', 'Cloud_Mid', 'Cloud_High', 'Cloud_Tot', 'Temperature']
        try:
            logDataLine = [pv_timestamp,str(irradiation_total[i]),str(pv_value),WD['cloud_low_level'][i],WD['cloud_mid_level'][i],WD['cloud_high_level'][i],WD['cloud_total_perceptions'][i],WD['temperature'][i]]
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
