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


def parse_athlete_activities_html(html: str, athlete_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    activities_result = []
    activities = soup.find_all(class_=activity_class)
    print(len(activities))

    for activity in activities:
        curr_act_json = {}
        if 'min-view' not in activity['class']:
            curr_act_json['has_gps'] = True
        else:
            curr_act_json['has_gps'] = False

        # MANDATORY ATTRIBUTES (all activities should have these: if not, error will occur)

        # athlete id
        curr_act_json['athlete_id'] = athlete_id

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


def validate_inputs(athlete_id: int, month: str, email: str, password: str) -> (bool, str):
    if not isinstance(athlete_id, str):
        return False, "Athlete ID must be an string"
    if not isinstance(month, str) or len(month) != 6:
        return False, "Month must be a string with length 6. Examples: '202001' for January 2020, '199811' for November 1998. You supplied: {}".format(athlete_id)
    if not isinstance(email, str) or '@' not in email:
        return False, "Email must be a string in email format. Examples 'test@gmail.com'. You supplied: {}".format(email)
    if not isinstance(password, str) or len(password) == 0:
        return False, "Password must be a string with at least length 1."

    return True, ""


def get_activities_in_month(months: list[str]) -> list[dict]:
    """Gather a month's worth of Strava activities for an athlete

    This function implements to core scraping techniques to gather the necessary HTML pages,
    then aggregates the formatted workouts into a form suitable for database storage.

    Note: to supply the email and password for the account which will scrape the data, environmental
    variables 'EMAIL' and 'PASSWORD' must be set.

    Args:
        months (list[str]): list of months in YYYYMM format

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

    all_activities = []

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

    for month in months:
        valid, message = validate_inputs(athlete_id, month, email, password)
        if not valid:
            print("Cannot get activities, invalid input: {}".format(message))

        # get the webpage of activities for the requested month
        url = f'https://www.strava.com/athletes/{athlete_id}#interval?interval={month}&interval_type=month&chart_type=hours&year_offset=0'
        print("Sending request on url: {}".format(url))
        driver.get(url)
        time.sleep(5)  # sleep to allow ajax to fill all the workouts and comply with terms of service

        all_activities.extend(parse_athlete_activities_html(driver.page_source, athlete_id))

    # at this point, have all required activities. Now, we want to get the GPS data for every activity
    # that has GPS data attached to it.
    for a in all_activities:
        if a['has_gps']:
            activity_id = a['activity_id']

            url = f'https://www.strava.com/activities/{activity_id}/route'

            print("Sending request on url: {}".format(url))
            driver.get(url)
            time.sleep(5)  # Again, sleeping here to allow the page to load, and comply with terms of service (only 1 web request per 5 seconds)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            script_json = soup.find_all(attrs={"id": "__NEXT_DATA__", "type": "application/json"})

            json_contents = json.loads(script_json[0].contents[0])

            activity_stream = json_contents.get("props").get("pageProps").get("activityStream")

            a['activity_stream'] = activity_stream

    result_json = {
        "timestamp_generated": datetime.utcnow().isoformat(),
        "months_included": months,
        "activities": all_activities
    }

    f = open("./result.json", "w")
    f.write(json.dumps(result_json, indent=4))
    f.close()

    return result_json


if __name__ == "__main__":
    # get activities for every month in 2020 and first 3 months of 2021
    months = ["202001", "202002", "202003", "202004", "202005", "202006", "202007", 
              "202008", "202009", "202010", "202011", "202012", "202101", "202102", "202103"]

    get_activities_in_month(months)
