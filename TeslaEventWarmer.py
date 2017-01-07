# TeslaEventWarmer.py
# Application that will scrape Google Calendar for an event, then warm up your Tesla at a given interval beforehand
# 
# Matt Dyson (matt@thedysons.net)
# 06/01/17

import gflags
import httplib2
import datetime
import pytz
import dateutil.parser
import logging
import sys
import argparse
import time

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
from oauth2client import tools

import Credentials # File with variables CLIENT_ID, CLIENT_SECRET, DEVELOPER_KEY, CALENDAR, TESLA_EMAIL, TESLA_PASSWORD

import teslajson

log = logging.getLogger('root')
log.setLevel(logging.DEBUG)

stream = logging.StreamHandler(sys.stdout)
stream.setLevel(logging.DEBUG)

formatter = logging.Formatter('[%(asctime)s] %(levelname)8s: %(message)s')
stream.setFormatter(formatter)

log.addHandler(stream)

FLAGS = gflags.FLAGS

class EventGatherer:
   def __init__(self):
      self.FLOW = OAuth2WebServerFlow(
         client_id=Credentials.CLIENT_ID,
         client_secret=Credentials.CLIENT_SECRET,
         scope='https://www.googleapis.com/auth/calendar',
         user_agent='TelsaEventWarmer/1.0'
      )

      self.storage = Storage('calendar.dat')
      self.credentials = self.storage.get()
      if not self.checkCredentials():
         log.error("GCal credentials have expired")
         return

      http = httplib2.Http()
      http = self.credentials.authorize(http)

      self.service = build(
         serviceName='calendar',
         version='v3',
         http=http,
         developerKey=Credentials.DEVELOPER_KEY
      )

   def checkCredentials(self):
      return not (self.credentials is None or self.credentials.invalid == True)

   def generateAuth(self):
      flags = tools.argparser.parse_args(args=["--noauth_local_webserver"])
      self.credentials = tools.run_flow(self.FLOW, self.storage, flags)

   def getNextEvent(self,skipMins=0):
      log.debug("Fetching details of next event")
      if not self.checkCredentials():
         raise Exception("GCal credentials not authorized")

      time = datetime.datetime.now()
      time += datetime.timedelta(minutes=skipMins) # In case we want to ignore events in a certain time

      result = self.service.events().list(
         calendarId=Credentials.CALENDAR,
         maxResults='1',
         orderBy='startTime',
         singleEvents='true',
         timeMin="%sZ" % (time.isoformat())
      ).execute()

      events = result.get('items', [])
      return events[0]

   def getNextEventTime(self,skipMins=0):
      log.debug("Fetching next event time")
      nextEvent = self.getNextEvent(skipMins)
      start = dateutil.parser.parse(nextEvent['start']['dateTime'])

      return start

if __name__ == '__main__':
   log.info("Starting up TeslaEventWarmer")

   parser = argparse.ArgumentParser(description='Warm up your Tesla according to Google Calendar Events')
   parser.add_argument('--gauth', action='store_true')
   parser.add_argument('--tauth', action='store_true')
   args = parser.parse_args()

   if args.gauth:
      # Check our GCal authentication
      log.info("Running GCal credential check")
      eg = EventGatherer()
      try:
         if not eg.checkCredentials():
            raise Exception("Credential check failed")
      except:
         log.info("GCal credentials not correct, please generate new code")
         eg.generateAuth()
         eg = EventGatherer()

      # We should now have good credentials, so try gathering an event
      log.info("GCal credentials seem good, next event at: %s" % (eg.getNextEventTime()))
      sys.exit()

   if args.tauth:
      # Check our Tesla authentication
      log.info("Running Tesla credential check")
      try:
         c = teslajson.Connection(Credentials.TESLA_EMAIL, Credentials.TESLA_PASSWORD)
         v = c.vehicles[0]
         log.info("Credentials seem okay, waking up vehicle to fetch information")
         v.wake_up()
         log.info("Fetching data from car")
         log.info("Tesla credentials seem good, current range is %s miles" % (v.data_request('charge_state')['ideal_battery_range']))
      except:
         log.error("Exception with Tesla authentication, check email and password", exc_info=True)

      sys.exit()

   # We want to start running the daemon
   log.info("Starting daemon")

   nextStartup = 0
   isStarted = False
   initialStart = True
   lastEventUpdate = 0

   eventGatherer = EventGatherer()
   tesla = teslajson.Connection(Credentials.TESLA_EMAIL, Credentials.TESLA_PASSWORD)
   vehicle = tesla.vehicles[0]

   while True:
      now = datetime.datetime.now(pytz.timezone('Europe/London'))
      halfhour = now - datetime.timedelta(minutes=30)
      refresh = now - datetime.timedelta(hours=1)

      if nextStartup == 0:
         # Find ourselves the next event
         try:
            # If we're just starting up, get all events. Otherwise, ignore ones in the next configured period
            if initialStart:
               event = eventGatherer.getNextEventTime()
            else:
               event = eventGatherer.getNextEventTime(skipMins=Credentials.MINS_BEFORE)

            nextStartup = event - datetime.timedelta(minutes=Credentials.MINS_BEFORE)

            lastEventUpdate = now
            initialStart = False
            log.info("Found event at %s, setting conditioning for %s" % (event,nextStartup))
         except:
            log.error("There was an error trying to find an event", exc_info=True)
            # Wait before trying again, we don't want to get beyond this point without an event set
            time.sleep(60)
            continue

      if lastEventUpdate < refresh:
         log.info("Checking for any event updates")
         nextStartup = 0
         isStarted = False
         continue

      if nextStartup < halfhour:
         # We've either been attempting this for half an hour, or it was successful, so reset to the next event
         log.info("Resetting event")
         nextStartup = 0
         isStarted = False
         continue

      if nextStartup < now and not isStarted:
         # The assigned startup time has passed, and we haven't sent a start command yet, so lets do it!
         log.info("Start time of %s has passed, attempting to start conditioning" % (nextStartup))
         try:
            vehicle.wake_up()
            state = vehicle.data_request('climate_state')
            log.info("Vehicle currently at %sC inside, outside temperature is %sC. Attempting to set temperature" % (state['inside_temp'], state['outside_temp']))
            temp = "{0:04.1f}".format(Credentials.TEMPERATURE)
            data = { "driver_temp": temp, "passenger_temp": temp }
            vehicle.command("set_temps", data)
            log.info("Temperature set to %s" % (temp))
            vehicle.command("auto_conditioning_start")
            log.info("Conditioning started")
            isStarted = True
         except:
            log.error("There was an error attempting to start conditioning", exc_info=True)
      
      # Sleep 60s before looping
      time.sleep(60)
