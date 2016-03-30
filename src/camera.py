import fcntl 
import os
import math
import gphoto2 as gp
import time
import glob
import subprocess
import re
import time
import traceback
import exifread
import itertools

USBDEVFS_RESET = ord('U') << (4*2) | 20

__all__ = ["Camera", "Config"]

def canon_path():
    #dev_re = re.compile("Bus (\d+) Device (\d+): ID 04a9:319a Canon, Inc. EOS 7D")
    dev_re = re.compile("Bus (\d+) Device (\d+):.*Canon, Inc..*")
    output = subprocess.check_output(["lsusb"]).split('\n')
    for line in output:
        m = dev_re.match(line)
        if m:
            return "/dev/bus/usb/%s/%s" % m.groups()

def reset_usb(port):
    fd = open(port, 'w')
    fcntl.ioctl(fd.fileno(), USBDEVFS_RESET)
    time.sleep(0.5)

class Config(object):
    WidgetTypes = {getattr(gp, name): name for name in dir(gp) if name.startswith("GP_WIDGET")}

    def __init__(self, widget, camera, context):
        self.widget = widget
        self.camera = camera
        self.context = context
        self.widget_id = widget.get_id()

    def lookup(self, name):
        parts = name.split('.')
        if parts[0] == self.name:
            parts = parts[1:]
        if len(parts) == 0:
            return self
        lookup = parts[0]
        remainder = str.join('.', parts[1:])
        for child in self.children:
            if child.name == lookup:
                if remainder:
                    return child.lookup(remainder)
                return child

    def dict(self, name='', choices=False):
        if name:
            name = "%s.%s" % (name, self.name)
        else:
            name = self.name
        res = {}
        if self.type in ("GP_WIDGET_SECTION", "GP_WIDGET_MENU", "GP_WIDGET_WINDOW"):
            for child in self.children:
                res.update(child.dict(name, choices))
        else:
            if choices:
                if self.type in ("GP_WIDGET_MENU", "GP_WIDGET_RADIO"):
                    res[name] = list(self.choices)
                elif self.type == "GP_WIDGET_TOGGLE":
                    res[name] = [1, 0]
                else:
                    res[name] = self.type
            else:
                res[name] = self.value
        return res

    @property
    def count_children(self):
        return self.widget.count_children()

    @property
    def count_choices(self):
        return self.widget.count_choices()

    @property
    def id(self):
        return self.widget.get_id()

    @property
    def type(self):
        return self.WidgetTypes[self.widget.get_type()]

    @property
    def label(self):
        return self.widget.get_label()

    @property
    def name(self):
        return self.widget.get_name()

    @property
    def parent(self):
        return self.__class__(self.widget.get_parent(), self.camera, self.context)

    @property
    def root(self):
        return self.__class__(self.widget.get_root(), self.camera, self.context)

    @property
    def children(self):
        for child_idx in range(self.count_children):
            child = self.widget.get_child(child_idx)
            yield self.__class__(child, self.camera, self.context)

    @property
    def choices(self):
        for choice_idx in range(self.count_choices):
            choice = self.widget.get_choice(choice_idx)
            yield choice

    def get_value(self):
        try:
            return self.widget.get_value()
        except:
            return None
    def set_value(self, val):
        #idx = list(self.choices).index(val)
        #self.widget.set_value(str(idx))
        self.widget.set_value(val)
        self.set_config()
    value = property(get_value, set_value)

    def get_range(self):
        return self.widget.get_range()
    def set_range(self, val):
        self.widget.set_range(val)
    range = property(get_range, set_range)

    def get_info(self):
        return self.widget.get_info()
    def set_info(self, val):
        self.widget.set_info(val)
    info = property(get_info, set_info)

    def get_readonly(self):
        return self.widget.get_readonly()
    def set_readonly(self, val):
        self.widget.set_readonly(val)
    readonly = property(get_readonly, set_readonly)

    def set_config(self):
        res = gp.gp_camera_set_config(self.camera, self.root.widget, self.context)
        gp.check_result(res)

class Camera(object):
    def __init__(self, port=None):
        if port == None:
            port = canon_path()
        assert port != None, "Could not find camera!"
        self.port = port
        self._camera = None
        self.last_image = None

    def __setitem__(self, name, value):
        cfg = self.config.lookup(name)
        cfg.value = value

    def __getitem__(self, name):
        return self.config.lookup(name).value

    @property
    def config(self):
        res = gp.gp_camera_get_config(*self.camera)
        widget = gp.check_result(res)
        (camera, context) = self.camera
        return Config(widget, camera, context)
         
    def capture(self, copy=False, prefix="", stubfn=""):
        (camera, context) = self.camera
        res = gp.gp_camera_capture(camera, gp.GP_CAPTURE_IMAGE, context)
        file_path = gp.check_result(res)
        if copy:
            return self.copy_file(file_path, prefix=prefix, stubfn=stubfn)
        else:
            return file_path

    def get_thumbnail(self, filename=None, refresh=False):
        filename = filename if filename != None else self.last_image
        if refresh or filename == None:
            fn = self.capture(copy=True)
            filename = fn
        with open(filename, 'rb') as fh:
            if filename.lower().endswith("cr2"):
                exif = exifread.process_file(fh)
                jpeg = exif["JPEGThumbnail"]
            else:
                jpeg = fh.read()
        return jpeg

    def copy_file(self, file_path, prefix="", stubfn=""):
        (camera, context) = self.camera
        target_fn = file_path.name
        target_fn = os.path.splitext(target_fn)
        target_fn = target_fn[0] + stubfn + target_fn[1]
        target_fn = os.path.join(prefix, target_fn)
        print('Copying image to %s' % target_fn)
        res = gp.gp_camera_file_get(camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL, context)
        camera_file = gp.check_result(res)
        res = gp.gp_file_save(camera_file, target_fn)
        gp.check_result(res)
        self.last_image = target_fn
        return target_fn

    @property
    def camera(self):
        if self._camera == None:
            self._context = gp.gp_context_new()
            self._camera = gp.check_result(gp.gp_camera_new())
            gp.check_result(gp.gp_camera_init(self._camera, self._context))
        return (self._camera, self._context)

    def walk(self, root=None):
        (camera, context) = self.camera
        root = root if root != None else "/"
        dirs = [name[0] for name in gp.check_result(gp.gp_camera_folder_list_folders(camera, root, context))]
        files = [name[0] for name in gp.check_result(gp.gp_camera_folder_list_files(camera, root, context))]
        yield (files, dirs, root)
        for directory in dirs:
            new_root = os.path.join(root, directory)
            for result in self.walk(root=new_root):
                yield result

    @property
    def default_path(self):
        picdir_re = re.compile("(\d\d\d)[^\d]+")
        paths = {}
        for (files, dirs, root) in self.walk():
            subdir = os.path.split(root)[-1]
            m = picdir_re.match(subdir)
            if not m:
                continue
            folder_num = int(m.groups()[0])
            paths[folder_num] = root
        max_key = max(paths.keys())
        return paths[max_key]

    def reset(self):
        self._camera = None
        reset_usb(self.port)

    def dump(self, prefix='', stubfn=''):
        self.download_all_files_on_camera(prefix=prefix, stubfn=stubfn)
        self.delete_all_files_on_camera()

    def get_files_on_camera(self, path=None):
        if path == None:
            path = self.default_path
        (camera, context) = self.camera
        res = gp.check_result(gp.gp_camera_folder_list_files(camera, path, context))
        res = [(path, x[0]) for x in res]
        return res

    def delete_all_files_on_camera(self, path=None):
        if path == None:
            path = self.default_path
        (camera, context) = self.camera
        res = gp.check_result(gp.gp_camera_folder_delete_all(camera, path, context))
        return res
    
    def download_all_files_on_camera(self, prefix='', stubfn=''):
        pics = self.get_files_on_camera()
        (camera, context) = self.camera
        files = []
        for (path, fn) in pics:
            if fn.lower().endswith("cr2"):
                _type = gp.GP_FILE_TYPE_RAW
            else:
                _type = gp.GP_FILE_TYPE_NORMAL
            target_fn = os.path.splitext(fn)
            target_fn = target_fn[0] + stubfn + target_fn[1]
            target_fn = os.path.join(prefix, target_fn)
            camera_file = gp.check_result(gp.gp_camera_file_get(camera, path, fn, _type, context))
            gp.check_result(gp.gp_file_save(camera_file, target_fn))

class CameraDirector(object):
    def __init__(self, camera):
        self.camera = camera
        self.start_ts = None
        self._pause = False
        self.interval = None
        self.last_shot = 0

    def get_pause(self):
        return self._pause
    
    def set_pause(self, val):
        self._pause = bool(val)
    pause = property(get_pause, set_pause)

    def schedule(self, interval):
        self.interval = interval
        self.start()

    def start(self):
        self.start_ts = time.time()
        self.last_shot = -1
    
    def stop(self):
        self.start_ts = None

    def tick(self):
        if self.start_ts == None or self.pause:
            return False
        delta = time.time() - self.start_ts
        shot_num = int(math.floor(delta / self.interval))
        if shot_num == self.last_shot:
            return False
        self.last_shot = shot_num
        retry = 5
        while retry:
            try:
                self.camera.capture(True)
                break
            except gp.GPhoto2Error:
                traceback.print_exc()
                self.camera.reset()
                continue
        return True

    def pretrigger(self, offset=2):
        if self.start_ts == None or self.pause:
            return False
        delta = time.time() - self.start_ts + offset
        shot_num = int(math.floor(delta / self.interval))
        if shot_num == self.last_shot:
            return False
        return True
