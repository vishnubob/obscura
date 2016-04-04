from astral import Astral
from obscura.camera import Camera
from pprint import pprint as pp
import gphoto2 as gp
import sched
from datetime import datetime
import parsedatetime
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
    dawn = sun_info["dawn"]
    dusk = dusk.replace(tzinfo=None)
    dawn = dawn.replace(tzinfo=None)
    now = datetime.now()
    return dusk < now or dawn > now

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
    RootPath = "/ginkgo/bitome/giles/winogradsky/matrix/"

    def __init__(self, camera, interval=60 * 60):
        self.interval = interval
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

    def get_path(self):
        datepath = time.strftime("%m.%d.%y")
        newroot = os.path.join(self.RootPath, datepath)
        if not os.path.exists(newroot):
            os.makedirs(newroot)
        next_count = len(os.listdir(newroot)) + 1
        newroot = os.path.join(newroot, str(next_count))
        if not os.path.exists(newroot):
            os.makedirs(newroot)
        return newroot

    def trigger(self):
        stops = self.fstops.keys()
        stops.sort()
        stops = [stop for stop in stops if stop <= 5.6]
        speeds = [speed for speed in self.sspeeds.keys() if speed >= (1 / 125.0) and speed <= (1 / 3.0)]
        speeds.sort()
        path = self.get_path()
        for fstop in stops:
            self.camera[self.AperatureWidgetName] = self.fstops[fstop]
            for speed in speeds:
                print speed, fstop
                self.camera[self.ShutterspeedWidgetName] = self.sspeeds[speed]
                prefix = os.path.join(path, str(fstop))
                if not os.path.isdir(prefix):
                    os.makedirs(prefix)
                self.camera.capture(copy=True, prefix=prefix, stubfn="_%s" % speed)
                time.sleep(20)
                self.camera.delete_all_files_on_camera()
                time.sleep(20)

    def run(self):
        self.running = True
        while self.running:
            if not after_dark():
                time.sleep(10)
                continue
            self.trigger()
            time.sleep(self.interval)

#i = Intervalometer(1, enable_callback=after_dark)
#i.run()
camera = Camera()
timelapse = TimelapseDriver(camera)
timelapse.run()
