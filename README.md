# Tesla Event Warmer
A Python script that reads events from Google Calendar, and will set the climate control on your Tesla at a specified time before events.

No more remembering to set manually through the app, or relying on the auto-conditioning!

# Requirements
 * https://github.com/gglockner/teslajson
 * python-dev
 * google-api-python-client (from pip)
 * python-gflags (from pip)
 * python-dateutil (from pip)

# Setup
Once the above libraries have been installed, create a file called "Credentials.py", and enter the following:
```
CLIENT_ID='<Google developer client ID>'
CLIENT_SECRET='<Google developer client secret>'
DEVELOPER_KEY='<Google developer key>'
CALENDAR='<Address of the Google Calendar you want to gather events from>'
TESLA_EMAIL='<Email address of your Tesla account>'
TESLA_PASSWORD='<Password of your Tesla account (will not be passed on anywhere)>'
MINS_BEFORE=<Number of minutes before an event that you want to start conditioning>
TEMPERATURE=<Temperature to set for conditioning>
```
Run `python TeslaEventWarmer.py --tauth` to check the Tesla authentication

Run `python TeslaEventWarmer.py --gauth` which will guide you through authenticating with Google

Once both of these return successfully, you can run the script without any arguments, and it will find the next event on your calendar, and begin pre-conditioning appropriately! The script is designed to run as a [supervisord](http://supervisord.org) job.
