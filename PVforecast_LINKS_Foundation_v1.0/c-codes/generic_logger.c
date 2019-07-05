/**
 * @file generic_logger.c
 *
 * @author Smart Energy - LINKS Foundation
 *
 * @date 05/03/2019
 *
 * @version 1.0.0
 *
 * @brief Functions to handle data logging
 *
 */

#include <stdio.h>
#include <string.h>
#include <time.h>

#define MAX_LOG_LENGTH 200

typedef enum{LOG_SEVERITY_ERROR, LOG_SEVERITY_WARNING, LOG_SEVERITY_TRACE, LOG_SEVERITY_INFO} severity_t;

/**
 * @brief function to save logging information
 * 
 * f: Pointer of the file to log
 * severity: Severity of the log message
 * logMessage: Log message content
 * verbose: 1 for verbose, 0 for NOT verbose output (print only errors, warnings and info)
 *
 */
int NewLog(FILE * f, severity_t severity, char *logMessage, int verbose){

	// If there is nothing to log, exit
	if (f == NULL) {
		return 1; ///< nothing to log actually
	}

	// Variable to save the severity tag
	char tag_string[8];

	// Definitions to handle the timestamp print
	time_t current_time;
	char *timestring;
	// Get the current time and parse in string format
	current_time = time(NULL);
	timestring = ctime(&current_time);
	timestring[strlen(timestring) - 1] = '\0';

	switch(severity){

		case LOG_SEVERITY_ERROR:
			strcpy(tag_string, "ERROR  ");
			break;

		case LOG_SEVERITY_WARNING:
			strcpy(tag_string, "WARNING");
			break;

		case LOG_SEVERITY_TRACE:
			strcpy(tag_string, "TRACE  ");
			break;

		case LOG_SEVERITY_INFO:
			strcpy(tag_string, "INFO   ");
			break;

		default:
			strcpy(tag_string, "???");
			break;

	}

	// If the log file is not a standard output
	if((f!=stdout) && (f!=stderr)){

		if (verbose){ 

			// If verbose, then always print
			fprintf(f, "[%s] %s: %s\n", timestring, tag_string, logMessage);

		}

		else {	// If not verbose, then only print errors and warnings and info

			if((severity == LOG_SEVERITY_ERROR)||(severity == LOG_SEVERITY_WARNING)||(severity == LOG_SEVERITY_INFO)){

				fprintf(f, "[%s] %s: %s\n", timestring, tag_string, logMessage);

			}

		}

		fflush(f);

	}

	// Logged successfully
	return 0;

}

