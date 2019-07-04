/**
 * @file pvforecastd.c
 *
 * @author Alessandro Bortoletto - LINKS Foundation | Hamidreza Mirtaheri - LINKS Foundation 
 *
 * @date 03/07/2019
 *
 * @version 2.0
 *
 * @brief This daemon executes a python script which performs a solar radiation prediction (W/m2) for a given location.
 */ 

#include <sys/types.h>
#include <sys/stat.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <errno.h>
#include <unistd.h>
#include <syslog.h>
#include <string.h>
#include <time.h>

#include "generic_parser.c"
#include "generic_logger.c"

int main(void) {
        
	/* Our process ID and Session ID */
	pid_t pid, sid;
	
	/* Fork off the parent process */
	pid = fork();
	if(pid < 0){
		exit(EXIT_FAILURE);
	}
	/* If we got a good PID, then we can exit the parent process. */
	if(pid > 0){
		exit(EXIT_SUCCESS);
	}

	/* Change the file mode mask */
	umask(0);
			
	/* Open logs here */
	// Pointer to the log file
	FILE *fpLog;
	// Variable with the log message (only text or with data inside)
	char* logMessage;
	char dataMessage[500];
	// Verbosity variable (1 = true, 0 = false)
	int verbose = 1;
	// Open the log in append mode
	fpLog = fopen("/home/PVforecast-Paper/pvforecast.log","a");
	// Log the opening of the log
	logMessage = "The log has been successfully opened.";
	NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);

	// Log the forking from parent and PID
	sprintf(dataMessage, "The process has been forked from parent, with PID %d.", getpid());
	NewLog(fpLog, LOG_SEVERITY_INFO, dataMessage, verbose);
		
	/* Create a new SID for the child process */
	sid = setsid();
	if(sid < 0){
		/* Log the failure */
		logMessage = "Failed to get a new SID.";
		NewLog(fpLog, LOG_SEVERITY_ERROR, logMessage, verbose);		
		exit(EXIT_FAILURE);
	}
	logMessage = "Got a new SID for the child process.";
	NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);

	/* Close out the standard file descriptors --> To reduce security problems, since we don't use them */
	close(STDIN_FILENO);
	close(STDOUT_FILENO);
	close(STDERR_FILENO);
	logMessage = "All standard file descriptors have been closed.";
	NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);
	
	/* Daemon-specific initialization variables goes here */

	// Configuration file path
	char* file_name = "/home/PVforecast-Paper/pvforecast.config";

	// The following variables are used to save the tags from the configuration file
	int loopSleepSeconds = 3600; // Daemon default is 3600 seconds
	char latitude[MAX_TAG_LEN];
	char longitude[MAX_TAG_LEN];
	char timestep[MAX_TAG_LEN];
	char horizon[MAX_TAG_LEN];
	char address[MAX_TAG_LEN];
	char port[MAX_TAG_LEN];
	char token[MAX_TAG_LEN];
	int sunrise = 5;
	int sunset = 22;

	// The following variables specify the tag names within the configuration file
	char* field_loopSleepSeconds = "loopSleepSeconds";
	char* field_latitude = "latitude";
	char* field_longitude = "longitude";
	char* field_timestep = "timestep";
	char* field_horizon = "horizon";
	char* field_address = "address";
	char* field_port = "port";
	char* field_token = "token";
	char* field_sunrise = "sunrise";
	char* field_sunset = "sunset";

	// The following variables are used to concatenate the different tags to create a single command for system()
	char command[400];
	char* script_call = "python3 /home/PVforecast-Paper/python-codes/pv_forecast_script.py";
	char* space = " ";

	/* Log the beginning of the reading operations */
	logMessage = "Reading the configuration file...";
	NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);

	/* Import the configuration variables from file */
	getVal(file_name,field_loopSleepSeconds,&loopSleepSeconds,F_INTEGER,1);
	getVal(file_name,field_latitude,&latitude,F_STRING,1);
	getVal(file_name,field_longitude,&longitude,F_STRING,1);
	getVal(file_name,field_timestep,&timestep,F_STRING,1);
	getVal(file_name,field_horizon,&horizon,F_STRING,1);
	getVal(file_name,field_address,&address,F_STRING,1);
	getVal(file_name,field_port,&port,F_STRING,1);
	getVal(file_name,field_token,&token,F_STRING,1);
	// Log the retrieved data
	sprintf(dataMessage, "I retrieved the following data from the configuration file: %d %s %s %s %s %s %s %s",loopSleepSeconds,latitude,longitude,timestep,horizon,address,port,token);
	NewLog(fpLog, LOG_SEVERITY_INFO, dataMessage, verbose);
	
	/* Preapare the command line string for system() */
	// First instance the command string
	strcpy(command,"");
	// Then add all the parts
	strcat(command,script_call);
	strcat(command,space);
	strcat(command,latitude);
	strcat(command,space);
	strcat(command,longitude);
	strcat(command,space);
	strcat(command,timestep);
	strcat(command,space);
	strcat(command,horizon);
	strcat(command,space);
	strcat(command,address);
	strcat(command,space);
	strcat(command,port);
	strcat(command,space);
	strcat(command,token);
	
	logMessage = "Command has been successfully composed!";
	NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);

	// Eliminate the first bad character of the command, if it is not the "p" --> Don't ask me why GCC is so dumb
	/*if(command[0]!='p'){
		int i;
		for(i = 1; i<strlen(command); i++){
			command[i-1]=command[i];
		}
	}*/
	
	logMessage = "Starting the main loop now.";
	NewLog(fpLog, LOG_SEVERITY_INFO, logMessage, verbose);

	/* Declare time data structure and variables useful to check the time in the main loop */
	struct tm ts;
	time_t timestamp;

	/* The main daemon loop starts here */
	while(1){

		/* Execute the script only during daytime! */
		timestamp = time(NULL);
		time(&timestamp);
		ts = *localtime(&timestamp);
		
		/* Update sunset and sunrise variables from .config file */
		getVal(file_name,field_sunrise,&sunrise,F_INTEGER,1);
		getVal(file_name,field_sunset,&sunset,F_INTEGER,1);
		// Log the retrieved data
		sprintf(dataMessage, "I retrieved the following data for sunrise and sunset: sunrise %d, sunset %d",sunrise,sunset);
		NewLog(fpLog, LOG_SEVERITY_INFO, dataMessage, verbose);

		if(ts.tm_hour<sunrise-1 || ts.tm_hour>sunset){
			logMessage = "It is night, so I will not update the solar radiation forecast.";
			NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);
		}
		else{
			logMessage = "It is day, I will proceed to update the solar radiation forecast.";
			NewLog(fpLog, LOG_SEVERITY_TRACE, logMessage, verbose);
		
			/* Execute the command with "system(string)" */
			sprintf(dataMessage, "Executing system command: %s", command);
			NewLog(fpLog, LOG_SEVERITY_TRACE, dataMessage, verbose);
			int status = system(command);
			
			/* Log the exitcode (e.g. 127=command not found, 0=all good, etc.) */
			sprintf(dataMessage, "Script executed! Exitcode: %d", status/256);
			NewLog(fpLog, LOG_SEVERITY_INFO, dataMessage, verbose);
		}
			
		/* wait until the next loop */
		sprintf(dataMessage, "The daemon is going to sleep for %d seconds.", loopSleepSeconds);
		NewLog(fpLog, LOG_SEVERITY_INFO, dataMessage, verbose);
		sleep(loopSleepSeconds); 

	}

	/* Close the log */
	logMessage = "The daemon is going to be closed... Bye bye!";
	NewLog(fpLog, LOG_SEVERITY_INFO, logMessage, verbose);
	fclose(fpLog);		

	/* Exit with success */
	exit(EXIT_SUCCESS);

}

