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
FORECAST_HORIZON = 1 # [days] This value must be between 1 and 6 days
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
arg_panel_declination = DECLINATION
arg_panel_tilt = TILT
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

reflect_coeffs = {'browned_grass':0.2,
                  'bare_soil':0.1,
                  'fresh_snow':0.87,
                  'dirty_snow':0.5}

def daylight_saving_table(dt_start, FORECAST_HORIZON, STEP):
    dt_year_end = datetime.datetime(dt_start.year, 12, 31).timetuple().tm_yday
    forecast_day = dt_start.timetuple().tm_yday
    DLS = np.zeros(dt_year_end)
    dt_daylight_saving_on = datetime.datetime(dt_start.year, 3, 31).timetuple().tm_yday
    dt_daylight_saving_off = datetime.datetime(dt_start.year, 10, 27).timetuple().tm_yday
    DLS[dt_daylight_saving_on: dt_daylight_saving_off] = 1
    DLS_forecast = DLS[forecast_day:forecast_day+FORECAST_HORIZON].repeat(24*(3600/STEP))
    return DLS_forecast

def sun_declination(n):
    '''
    this function computes the sun's declination angle with respect to a certain point
    :param n: day of the year (integer)
    :return: 
    '''
    d = 23.45 * np.sin((360/365) * (284+n))
    B = (360/365)*(n-81)
    return d

sun_declination_vect = np.vectorize(sun_declination)

def equation_of_time_func(n):
    B = np.radians((360/365)*(n-81))
    eot = (0.165*np.sin(2*B)) - (0.126*np.cos(B)) - (0.025*np.sin(B)) ## in hour
#    eot = (9.87*np.sin(2*B)) - (7.53*np.cos(B)) - (1.5*np.sin(B))  ## in minutes
    return eot
eot_vect = np.vectorize(equation_of_time_func)

def local_solar_time(clock_time, equ_of_time, latitude, DT, time_difference_from_GMT = 1):
    lst = clock_time + ((1/15) * (time_difference_from_GMT - latitude)) + equ_of_time - DT
    return lst

local_solar_time_vect = np.vectorize(local_solar_time)

def solar_hour_angle(lst):
    h = 15*(lst -12)
    return h

def zenith_func(lat, h, d):
    cos_zenith = np.cos(np.deg2rad(lat))*np.cos(np.deg2rad(h))*np.cos(np.deg2rad(d)) + \
    np.sin(np.deg2rad(lat))*np.sin(np.deg2rad(d))
    return np.arccos(cos_zenith)

def altitude_func(lat, h, d):
    sin_altitude = np.cos(np.deg2rad(lat))*np.cos(np.deg2rad(h))*np.cos(np.deg2rad(d)) + \
    np.sin(np.deg2rad(lat))*np.sin(np.deg2rad(d))
    return np.arcsin(sin_altitude)

def azimuth_func(alt, lat, h, d):
    cos_azimuth =  (1/np.cos(alt)) * ((np.cos(np.deg2rad(d))*np.sin(np.deg2rad(lat))*np.cos(np.deg2rad(h)))-(np.sin(np.deg2rad(d))*np.cos(np.deg2rad(lat))))
    arccos_azimuth = np.arccos(cos_azimuth)
    arccos_azimuth[np.argwhere(np.isnan(arccos_azimuth))] = 0.0
    return arccos_azimuth

def direct_normal_flux(a_alt):
    A = lookup_table[dt_start.month][0]
    B = lookup_table[dt_start.month][1]
    return (A * np.exp(-B/np.sin(solar_altitude)))

def diffuse_solar_flux_horizon(direct_flux):
    return lookup_table[dt_start.month][2] * direct_flux

def diffuse_solar_flux_panel(I_dH, sigma):
    I_d = I_dH * ((1+np.cos(sigma)) / 2)
    return I_d

def direct_to_panel_flux(I_DN, teta):
    return I_DN * np.cos(teta)


def reflected_flux(I_D, ro_g):
    reflected_radiation = ro_g['browned_grass'] * I_D * ((1-np.cos(TILT))/2)
    return reflected_radiation

def surface_solar_azimuth(solar_azimuth, arg_panel_declination):
    #TODO some things to be taken into account; angle conventions for azimuth
    return abs(solar_azimuth - arg_panel_declination)

def incidence_angle(solar_altitude_, panel_azimuth_, panel_tilt_):
    cos_teta = np.cos(solar_altitude_) * np.cos(panel_azimuth_) * np.sin(panel_tilt_)+np.sin(solar_altitude_) * np.cos(panel_tilt_)
    return np.arccos(cos_teta)

# This method performs a convolution of the array passed as parameter, to smooth impact of noises
def convolution(array):
    box_pts = 21
    box = np.ones(box_pts) / box_pts
    return np.convolve(array, box, mode='same')


# THIS FUNCTION DOESN'T USE PANDAS
def addNoise(irradiations, sim_step, lat, lon):
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

# here the functions one by one are called to generate the forecast/ The order and output of the calls will be documented 
# a dedicated manual

#________________________ THIS PART IS SUBJECT TO MORE ELABORATION ____________________________

forecast_time_horizon_array = np.arange(0, 24*FORECAST_HORIZON, STEP/3600)
dt_start = datetime.datetime.combine(datetime.datetime.now().date(), 
                                     datetime.time(0,0,0))
dt_end = datetime.datetime.combine(datetime.datetime.now().date() + 
                                   datetime.timedelta(days=FORECAST_HORIZON), 
                                   datetime.time(0,0,0))
sim_time_array = np.arange(dt_start, dt_end, datetime.timedelta(seconds=STEP)).astype(datetime.datetime)

#________________________ THIS PART IS SUBJECT TO MORE ELABORATION____________________________


day_of_the_year = dt_start.timetuple().tm_yday

sun_declination_value = sun_declination(day_of_the_year)
equation_of_time = equation_of_time_func(day_of_the_year)
day_light_savings = daylight_saving_table(dt_start, FORECAST_HORIZON, STEP)
local_solar_time_values = local_solar_time(forecast_time_horizon_array, equation_of_time, LATITUDE, day_light_savings)
solar_hour_angle_value = solar_hour_angle(local_solar_time_values)
solar_zenith = zenith_func(LATITUDE, solar_hour_angle_value, sun_declination_value)
solar_altitude = altitude_func(LATITUDE, solar_hour_angle_value, sun_declination_value)
solar_altitude[solar_altitude<0] = 0
solar_azimuth = azimuth_func(solar_altitude, LATITUDE, solar_hour_angle_value, sun_declination_value)
surface_solar_azimuth_values = surface_solar_azimuth(DECLINATION, solar_azimuth)
incidence_angle_values = incidence_angle(solar_altitude, surface_solar_azimuth_values, TILT)

irradiation_direct_normal = direct_normal_flux(solar_altitude) 
direct_flux = direct_to_panel_flux(irradiation_direct_normal, incidence_angle_values)
diffuse_flux_horizontal = diffuse_solar_flux_horizon(irradiation_direct_normal) 
diffuse_flux_panel = diffuse_solar_flux_panel(diffuse_flux_horizontal, TILT) 
reflected_radiations = reflected_flux(direct_flux, reflect_coeffs)

irradiation_total = direct_flux + diffuse_flux_panel + reflected_radiations


# Add the noise to the "pure" solar radiation vector
appliedNoiseIrradiation, WD = addNoise(irradiation_total, STEP, LATITUDE, LONGITUDE)

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
            sensor_data['values']['pv_forecast'] = pv_value
            		# Send data to ThingsBoard via MQTT
            client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
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
