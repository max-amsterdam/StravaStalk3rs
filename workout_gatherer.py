"""
This file contains the logic for scraping workout data from a given athlete's profile page on strava.com

Some of the code, structure, and libraries used were inspired by this repo: https://github.com/oleksmaistrenko/strava-google-sheets
"""
from bs4 import BeautifulSoup
from selenium import webdriver
import datetime
import os
import time
import re

count = 1

def human_readable_time_to_machine(activity_date_day):
    if activity_date_day == 'Today':
        return datetime.date.today().strftime('%B %-d, %Y')
    if activity_date_day == 'Yesterday':
        return (datetime.date.today() - datetime.timedelta(days=1)).strftime('%B %-d, %Y')

def parse_athlete_activity_info(athlete_info):
    '''
    get activity info from athlete selection
    '''
    activity_athlete = athlete_info.xpath(".//a[contains(@class, 'entry-athlete')]")[0].text.strip()
    activity_distance = athlete_info.xpath(".//li[@title='Distance']")[0].text.strip()
    try:
        activity_elevation_gain = athlete_info.xpath(".//li[@title='Elev Gain']")[0].text.strip().replace(',', '')
    except IndexError:
        activity_elevation_gain = ''
    return activity_athlete, activity_distance, activity_elevation_gain


def parse_athlete_activities_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    activities_result = []
    activities = soup.find_all(attrs={"class": "activity entity-details feed-entry"})
    print(len(activities))

    for activity in activities:
        # MANDATORY ATTRIBUTES (all activities should have these: if not, error will occur)

        # athlete name
        athlete_tag = activity.find_all("a", attrs={"class": "entry-athlete", "href": re.compile("/athletes/*")})
        if len(athlete_tag) > 1:
            print("ERROR: Find call on athlete tag returned more than 1 result: {}".format(athlete_tag))
            return
        else:
            athlete_tag = athlete_tag[0]

        athlete_name = athlete_tag.string.strip()

        # timestamp start
        timestamp_tag = activity.find_all("time", attrs={"class": "timestamp"})
        if len(timestamp_tag) > 1:
            print("ERROR: Find call on timestamp tag returned more than 1 result: {}".format(timestamp_tag))
            return
        else:
            timestamp_tag = timestamp_tag[0]

        timestamp_start = timestamp_tag['datetime']

        # activity ID
        title_tag = activity.find_all("a", href=re.compile("activities/"), attrs={"class": ""})
        if len(title_tag) > 1:
            print("ERROR: Find call on title tag returned more than 1 result: {}".format(title_tag))
            return
        else:
            title_tag = title_tag[0]

        activity_id = title_tag['href'].split("/")[2]

        # title
        title = title_tag.string
        print("{} completed {} (id {}) at {}".format(athlete_name, title, activity_id, timestamp_start))

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

        # type

        app_icon_tag = activity.find_all("span", attrs={"class": "app-icon"})

        # OPTIONAL ATTRIBUTES (not all activities will have these)
        # distance*
        # pace*
        # average HR*
        # calories*


    # tree = html.fromstring(activity_html.text)

    # last_timestamp = ''
    # records = list()

    # activities = tree.xpath("//div[@class='activity entity-details feed-entry']")
    # print("HTML of found activites: {}".format(activities))
    # print("Number of activities found: {}".format(activities))

    # # single activities
    # for activity in tree.xpath("//div[@class='activity entity-details feed-entry']"):
    #     # activitiy time stamp
    #     activity_timestamp = activity.xpath("./@data-rank")[0]
    #     # activitiy date
    #     activity_date = activity.xpath(".//div[@class='entry-head']/time")[0].text.strip()
    #     activity_date_day, activity_date_time, *_ = activity_date.split(" at ")
    #     activity_date = human_readable_time_to_machine(activity_date_day)
    #     # athlete info
    #     activity_athlete, activity_distance, activity_elevation_gain = parse_athlete_activity_info(activity)
    #     records.append({
    #         "athlete_name": activity_athlete,
    #         "activity_day": activity_date_day,
    #         "activity_time": activity_date_time,
    #         "activity_distance": activity_distance,
    #         "activity_elevation_gain": activity_elevation_gain
    #     })
    #     last_timestamp = activity_timestamp
    
    # # group activities
    # for activity in tree.xpath("//div[@class='feed-entry group-activity']"):
    #     # activitiy time stamp
    #     activity_timestamp = activity.xpath("./@data-rank")[0]
    #     # activitiy date
    #     activity_date = activity.xpath(".//div[@class='entry-head']/time")[0].text.strip()
    #     activity_date_day, activity_date_time, *_ = activity_date.split(" at ")
    #     activity_date = human_readable_time_to_machine(activity_date_day)
    #     for athlete_info in activity.xpath(".//li[@class='entity-details feed-entry']"):
    #         # athlete info
    #         activity_athlete, activity_distance, activity_elevation_gain = parse_athlete_activity_info(athlete_info)
    #         records.append({
    #             "athlete_name": activity_athlete,
    #             "activity_day": activity_date_day,
    #             "activity_time": activity_date_time,
    #             "activity_distance": activity_distance,
    #             "activity_elevation_gain": activity_elevation_gain
    #         })
    #     if last_timestamp < activity_timestamp:
    #         last_timestamp = activity_timestamp

    # return last_timestamp, records


def validate_inputs(athlete_id: int, month: str, year: str, email: str, password: str) -> (bool, str):
    if not isinstance(athlete_id, int):
        return False, "Athlete ID must be an integer "
    if not isinstance(month, str) or len(month) != 2:
        return False, "Month must be a string with length 2. Examples: '01' for January, '11' for November. You supplied: {}".format(athlete_id)
    if not isinstance(year, str) or len(year) != 4:
        return False, "Year must be a string with length 4. Examples: '2021' for 2021, '1998' for 1998. You supplied: {}".format(year)
    if not isinstance(email, str) or '@' not in email:
        return False, "Email must be a string in email format. Examples 'test@gmail.com'. You supplied: {}".format(email)
    if not isinstance(password, str) or len(password) == 0:
        return False, "Password must be a string with at least length 1."

    return True, ""


def get_activities_in_month(athlete_id: int, month: str, year: str) -> list[dict]:
    """Gather a month's worth of Strava activities for an athlete

    This function implements to core scraping techniques to gather the necessary HTML pages,
    then aggregates the formatted workouts into a form suitable for database storage.

    Note: to supply the email and password for the account which will scrape the data, environmental
    variables 'EMAIL' and 'PASSWORD' must be set.

    Args:
        athlete_id (int): ID of the athlete to gather activities for. This is a Strava construct
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
    except:
        print("Failed to get activities: EMAIL, PASSWORD, and CHROME_DRIVER_PATH environmental variables must be set.")
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

    activities = parse_athlete_activities_html(driver.page_source)

    # # TODO: gather corresponding GPX routes for every activity (will require storing of acitivity_id)

    # # close the session
    # session_requests.close()

    # return activities

if __name__ == "__main__":
    # athlete_id = int(input("Athlete ID: "))
    # month = input("Month: ")
    # year = input("Year: ")
    athlete_id = 55006593
    month = "10"
    year = "2020"
    get_activities_in_month(athlete_id, month, year)