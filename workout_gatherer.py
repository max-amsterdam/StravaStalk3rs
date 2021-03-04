"""
This file contains the logic for scraping workout data from a given athlete's profile page on strava.com
"""
from bs4 import BeautifulSoup
from selenium import webdriver
from datetime import datetime
import time
import os
import time
import re
import json


meter_to_miles_conversion_factor = .0006213712


def activity_class(css_class):
    return css_class is not None and "activity" in css_class and "entity-details" in css_class and "feed-entry" in css_class


def parse_athlete_activities_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    activities_result = []
    activities = soup.find_all(class_=activity_class)
    print(len(activities))

    for activity in activities:
        curr_act_json = {}
        # MANDATORY ATTRIBUTES (all activities should have these: if not, error will occur)

        # athlete name
        athlete_tag = activity.find_all("a", attrs={"class": "entry-athlete", "href": re.compile("/athletes/*")})
        if len(athlete_tag) > 1:
            print("ERROR: Find call on athlete tag returned more than 1 result: {}".format(athlete_tag))
            return
        else:
            athlete_tag = athlete_tag[0]

        athlete_name = athlete_tag.string.strip()
        curr_act_json['athlete_name'] = athlete_name

        # timestamp start
        timestamp_tag = activity.find_all("time", attrs={"class": "timestamp"})
        if len(timestamp_tag) > 1:
            print("ERROR: Find call on timestamp tag returned more than 1 result: {}".format(timestamp_tag))
            return
        else:
            timestamp_tag = timestamp_tag[0]

        timestamp_start = timestamp_tag['datetime']
        curr_act_json['timestamp_start'] = timestamp_start 

        # activity ID
        title_tag = activity.find_all("a", href=re.compile("activities/"), attrs={"class": ""})
        if len(title_tag) > 1:
            print("ERROR: Find call on title tag returned more than 1 result: {}".format(title_tag))
            return
        else:
            title_tag = title_tag[0]

        activity_id = title_tag['href'].split("/")[2]
        curr_act_json['activity_id'] = activity_id 

        # title
        title = title_tag.string.strip()
        curr_act_json['title'] = title 

        # elapsed time
        elapsed_time_tag = activity.find_all("li", attrs={"title": "Time"})
        if len(elapsed_time_tag) > 1:
            print("ERROR: Find call on elapsed time tag returned more than 1 result: {}".format(elapsed_time_tag))
            return
        else:
            elapsed_time_tag = elapsed_time_tag[0]

        elapsed_time_children = elapsed_time_tag.contents
        i = 0
        total_time_seconds = 0
        while i < len(elapsed_time_children):
            num = int(elapsed_time_children[i].strip())
            unit = elapsed_time_children[i + 1]['title']

            if unit == "hour":
                total_time_seconds += num * 60 * 60
            elif unit == "minute":
                total_time_seconds += num * 60
            elif unit == "second":
                total_time_seconds += num

            i += 2

        curr_act_json['elapsed_time_minutes'] = round(total_time_seconds / 60.0, 2)

        # type
        app_icon_tags = activity.find_all("span", attrs={"class": "app-icon"})
        app_icon_tag = None
        for t in app_icon_tags:
            if len(t.get_text(strip=True)) == 0:
                app_icon_tag = t
                break

        if not app_icon_tag:
            print("ERROR: Loop to find app icon tag did not work. All returned app_icon_tags: {}".format(app_icon_tags))
            return

        classes = app_icon_tag['class']
        # we are looking for the workout type via "icon-<type>". We need to ignore "icon-dark" and "icon-lg"
        activity_type = None
        for c in classes:
            if c != "app-icon" and (c != "icon-dark" or c != "icon-light") and (c != "icon-lg" or c != "icon-md" or c != "icon-sm"):
                # this is the type icon!
                activity_type = c.split("-")[1]
                break

        if not activity_type:
            print("ERROR: unable to find activity type")
            return

        curr_act_json['activity_type'] = activity_type

        # OPTIONAL ATTRIBUTES (not all activities will have these)
        # distance*
        distance_tag = activity.find_all("li", attrs={"title": "Distance"})

        if len(distance_tag) > 1:
            print("ERROR: Find call on distance tag returned more than 1 result: {}".format(distance_tag))
        elif len(distance_tag) == 1:
            # add distance if it exists, if not, ignore
            distance_tag = distance_tag[0]
            children = distance_tag.contents
            num = float(children[0].strip().replace(',', ''))  # number of miles OR meters
            unit = children[1]['title']

            curr_act_json["distance"] = {
                "value": num,
                "unit": unit
            }

        # pace*
        pace_tag = activity.find_all("li", attrs={"title": "Pace"})
        if len(pace_tag) > 1:
            print("ERROR: Find call on pace tag returned more than 1 result: {}".format(pace_tag))
        elif len(pace_tag) == 1:
            # add pace if it exists, if not, ignore
            pace_tag = pace_tag[0]
            children = pace_tag.contents
            pace = children[0].strip()
            unit = children[1]['title']

            curr_act_json["pace"] = {
                "value": pace,
                "unit": unit 
            }

        # elevation gain*
        elev_gain_tag = activity.find_all("li", attrs={"title": "Elev Gain"})
        if len(elev_gain_tag) > 1:
            print("ERROR: Find call on pace tag returned more than 1 result: {}".format(pace_tag))
        elif len(elev_gain_tag) == 1:
            # add elev gain if it exists, if not, ignore
            elev_gain_tag = elev_gain_tag[0]
            children = elev_gain_tag.contents
            num = float(children[0].strip().replace(',', ''))
            unit = children[1]['title']

            curr_act_json["elevation_gain"] = {
                "value": num,
                "unit": unit
            }

        activities_result.append(curr_act_json)

    return activities_result


def validate_inputs(athlete_id: int, month: str, year: str, email: str, password: str) -> (bool, str):
    if not isinstance(athlete_id, str):
        return False, "Athlete ID must be an string"
    if not isinstance(month, str) or len(month) != 2:
        return False, "Month must be a string with length 2. Examples: '01' for January, '11' for November. You supplied: {}".format(athlete_id)
    if not isinstance(year, str) or len(year) != 4:
        return False, "Year must be a string with length 4. Examples: '2021' for 2021, '1998' for 1998. You supplied: {}".format(year)
    if not isinstance(email, str) or '@' not in email:
        return False, "Email must be a string in email format. Examples 'test@gmail.com'. You supplied: {}".format(email)
    if not isinstance(password, str) or len(password) == 0:
        return False, "Password must be a string with at least length 1."

    return True, ""


def get_activities_in_month(month: str, year: str) -> list[dict]:
    """Gather a month's worth of Strava activities for an athlete

    This function implements to core scraping techniques to gather the necessary HTML pages,
    then aggregates the formatted workouts into a form suitable for database storage.

    Note: to supply the email and password for the account which will scrape the data, environmental
    variables 'EMAIL' and 'PASSWORD' must be set.

    Args:
        month (str): month in MM format
        year (str): year in YY format

    Returns:
        List(Dict): A list of workout objects
    """
    # email and password for user who will be "scraping" the results
    try:
        email = os.environ['EMAIL']
        password = os.environ['PASSWORD']
        chrome_driver_path = os.environ['CHROME_DRIVER_PATH']
        athlete_id = os.environ['ATHLETE_ID']
    except:
        print("Failed to get activities: EMAIL, PASSWORD, and CHROME_DRIVER_PATH, ATHLETE_ID environmental variables must be set.")
        return

    valid, message = validate_inputs(athlete_id, month, year, email, password)
    if not valid:
        print("Cannot get activities, invalid input: {}".format(message))

    # get driver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')

    driver = webdriver.Chrome(chrome_driver_path, options=options)

    # get a token for this session
    login_url = 'https://www.strava.com/login'
    driver.get(login_url)

    driver.find_element_by_id('email').send_keys(email)
    driver.find_element_by_id('password').send_keys(password)
    driver.find_element_by_id('login-button').click()

    # get the webpage of activities for the requested month
    url = f'https://www.strava.com/athletes/{athlete_id}#interval?interval={year}{month}&interval_type=month&chart_type=hours&year_offset=0'
    print("Sending request on url: {}".format(url))
    driver.get(url)
    time.sleep(5)  # sleep to allow ajax to fill all the workouts

    return parse_athlete_activities_html(driver.page_source)

    # TODO: gather corresponding GPX routes for every activity (will require storing of acitivity_id)


if __name__ == "__main__":
    # get activities for every month in 2020
    months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    # months = ["08", "09"]
    year = "2020"
    all_activities = []
    for m in months:
        curr_activities = get_activities_in_month(m, year)
        print("Got {} activities from month {}".format(len(curr_activities), m))
        all_activities.extend(curr_activities)
    print("Total number of activities: {}".format(len(all_activities)))

    activities_json = {
        "activities": all_activities
    }

    f = open("activities_{}.json".format(time.time()), "w")
    f.write(json.dumps(all_activities, indent=4))
