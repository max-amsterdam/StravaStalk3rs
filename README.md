# Strava Stalk3ers

This repo contains code for scraping workout data from Strava's workout platform. 

The code is capable of gathering metadata and GPS data for every public workout of a specific Strava user. The program then writes this data locally to a JSON formatted file. 

Note, this code requires a Strava account to work properly. Variables such as the email and password of the scraping account, a link to a Chrome driver for scraping, the Strava athlete ID of the athlete to be scraped, and the months of workout data to scrape will all need to be input as either environmental variables or within the code itself. 

Before using this tool, please be aware of [Strava's Terms of Service](https://www.strava.com/legal/terms).

Note: this code was created for the Privacy in a Networked World course at Columbia University for the Spring 2021 semester. 
