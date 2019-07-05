/**
 * @file generic_parser.c
 *
 * @author Andrea Molino
 * @author Smart Energy - LINKS Foundation
 *
 * @date 05/03/2019
 *
 * @version 2.0.0
 *
 * @brief Tool for parsing configuration files
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

#define MAX_TAG_LEN 125

typedef enum{F_INTEGER, F_FLOAT, F_DOUBLE, F_STRING, F_CHAR} field_t;

/**
 * @brief This method saves into a variable (third argument) the value of the field corresponding to a certain tag in the specified file.
 * 
 * file_name: Name of the file
 * field_name: Name of the field (tag) to look for
 * variable: Pointer to the variable where we wish to save the value of the tag (if found)
 * field_type: Type of value for the tag
 * field_len: How many different values (one per row) are specified within the same tag
 *
 */
int getVal(char *file_name, char *field_name, void *variable, field_t field_type, int field_len){

	FILE *fin;
	int found = 0;
	char charo;
	char term;
	char term_str[2];
	char stringa[MAX_TAG_LEN];
	char tmp_str[MAX_TAG_LEN];
	int cnt;

	fin = fopen(file_name,"r");

	tmp_str[0] = '\0';

	if(fin == NULL){
		perror("Error while opening the file.\n");
		return -1;
	}

	while((fscanf(fin, "%c", &charo) != EOF) && (found==0)){

		if(charo == '['){

			fscanf(fin, "%s", stringa);

			term = ' ';

			do{
				fscanf(fin,"%c", &term);
				term_str[0] = term;
				term_str[1] = '\0';
				strcat(stringa, term_str);
			}while ((term != ']') && (term != '\n'));


			if(strstr(stringa,field_name) != NULL){

				// Tag found
				found = 1;

				for(cnt=0; cnt<field_len; cnt++){

					switch(field_type){
						case F_INTEGER:
							if(!fscanf(fin,"%d", &((int*)variable)[cnt])){
								fclose(fin);
								return -1;
							}
							break;

						case F_FLOAT:
							if(!fscanf(fin,"%f", &((float*)variable)[cnt])){
								fclose(fin);
								return -1;
							}
							break;

						case F_DOUBLE:
							if(!fscanf(fin,"%lf", &((double*)variable)[cnt])){
								fclose(fin);
								return -1;
							}
							break;

						case F_STRING:
							if(cnt == 0)
								((char*)variable)[0] = '\0';

							if(!fscanf(fin,"%s", (tmp_str))){
								// String not found
								((char*)tmp_str)[0] = '\0';
								strcat((char*)variable, tmp_str);
								fclose(fin);
								return -1;
							}else
								// String found
								if((((char*)tmp_str)[0] == '[') || (((char*)tmp_str)[0] == '#')){
									// Found an empty string, still it is a string!
									((char*)tmp_str)[0] = '\0';
									strcat((char*)variable, tmp_str);
									fclose(fin);
									return 1;
								}else{
									// Concatenate the string with the previous one of the array
									if(cnt != 0){
										strcat((char*)variable, " ");
									}
									strcat((char*)variable, tmp_str);

								}


						break;

						case F_CHAR:
							if(!fscanf(fin,"%c", &((char*)variable)[cnt])){
								fclose(fin);
								return -1;
							}
							break;

						default:
							if(!fscanf(fin,"%f", &((float*)variable)[cnt])){
								fclose(fin);
								return -1;
							}
							break;

					}
				}

				fclose(fin);
				return 1;

			}
		}


	};

	fclose(fin);

	return 0;

}
