from astral import Astral
from obscura.camera import Camera
from pprint import pprint as pp
import gphoto2 as gp
import sched
from datetime import datetime
import time
import os

def get_sun(date="today", depression="astronomical", cityname="Boston"):
    astral = Astral()
    astral.solar_depression = depression
    city = astral[cityname]
    calendar = parsedatetime.Calendar()
    dateinfo = calendar.parse(date)
    date_ts = time.mktime(dateinfo[0])
    date_dt = datetime.fromtimestamp(date_ts)
    return city.sun(date=date_dt, local=True)

def after_dark(**kw):
    sun_info = get_sun(**kw)
    dusk = sun_info["dusk"]
    dusk = dusk.replace(tzinfo=None)
    return dusk < datetime.now()

class Intervalometer(object):
    def __init__(self, period, enable_callback=None):
        self.period = period
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.enable_callback = enable_callback if enable_callback != None else lambda: True
        self.schedule()

    def schedule(self):
        self.scheduler.enter(self.period, 10, self.trigger, ())

    def trigger(self):
        if not self.enable_callback():
            print "No Trigger"
        else:
            print "Trigger"
        self.schedule()

    def run(self):
        self.scheduler.run()

class TimelapseDriver(object):
    AperatureWidgetName = "main.capturesettings.aperture"
    ShutterspeedWidgetName = "main.capturesettings.shutterspeed"

    def __init__(self, camera):
        self.camera = camera
        cfg = self.camera.config
        #cam["settings.capturetarget"] = "Memory card"
        self.fstops = {float(val): val for val in list(cfg.lookup(self.AperatureWidgetName).choices)}
        self.sspeeds = {}
        for ss in cfg.lookup(self.ShutterspeedWidgetName).choices:
            speed = ss.split("/")
            if len(speed) == 1:
                speed = float(speed[0])
            else:
                speed = float(speed[0]) / float(speed[1])
            self.sspeeds[speed] = ss

    def matrix(self):
        stops = self.fstops.keys()
        stops.sort()
        speeds = [speed for speed in self.sspeeds.keys() if speed > .001 and speed < 1]
        speeds.sort()
        for fstop in stops:
            self.camera[self.AperatureWidgetName] = self.fstops[fstop]
            for speed in speeds:
                print speed, fstop
                self.camera[self.ShutterspeedWidgetName] = self.sspeeds[speed]
                prefix = "matrix/%s" % fstop
                if not os.path.isdir(prefix):
                    os.makedirs(prefix)
                self.camera.capture(copy=True, prefix=prefix, stubfn="_%s" % speed)
                self.camera.delete_all_files_on_camera()

#i = Intervalometer(1, enable_callback=after_dark)
#i.run()

camera = Camera()
timelapse = TimelapseDriver(camera)
timelapse.matrix()
