import haml
import webassets
from webassets.bundle import wrap
import pathlib
import os
import logging
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, callable, lock=None):
        super(FileModifiedHandler, self).__init__()
        self.callable = callable
        self.lock = lock

    def _process(self, event):
        if self.lock:
            self.lock.acquire()
            print("handling %s at %s" % (event.event_type, event.src_path))
            self.lock.release()
        else:
            print("handling %s at %s" % (event.event_type, event.src_path))
        self.callable()

    def on_modified(self, event):
        self._process(event)

    # def on_created(self, event):
    #     self._process(event)

    # def on_deleted(self, event):
    #     self._process(event)

class AssetManager(object):

    def _load_asset_bundles(self, config_path):
        if os.path.isfile(config_path):
            loader = webassets.loaders.YAMLLoader(config_path)
            return loader.load_bundles()
        return None

    def _setup_environment(self, bundles):
        environment = webassets.Environment()
        environment.directory = self._resolve_assets_dir()
        for name, bundle in bundles.iteritems():
            environment.register(name, bundle)
        return environment

    def __init__(self, config_path, rebuild=False, lock=None):
        bundles = self._load_asset_bundles(config_path)
        self.environment = self._setup_environment(bundles)
        self.lock = lock
        if rebuild:
            self._setup_rebuild()
        else:
            self.build_environment()

    def _resolve_assets_dir(self):
        for dirpath, dirnames, files in os.walk('.'):
            if 'assets' in dirnames:
                return os.path.join(dirpath, 'assets')
        return None

    def files_to_watch(self):
        files = []
        ctx = wrap(self.environment, None)
        for bundle in self.environment:
            files.extend(bundle.resolve_contents(force=True))
        orig, abspaths = zip(*files)
        abspaths = list(abspaths)
        abspaths.extend(bundle.resolve_depends(ctx))
        return set(abspaths)

    def message(self, val):
        if self.lock:
            self.lock.acquire()
            print(val)
            self.lock.release()
        else:
            print(val)

    def _setup_rebuild(self):
        pass
        # watched = self._resolve_assets_dir()
        # self.message("watching %s" % watched)
        # rebuilder = FileModifiedHandler(self.build_environment, self.lock)
        # observer = Observer()
        # observer.schedule(rebuilder, watched, recursive=True)
        # observer.daemon = True
        # observer.start()
        # observer.join()

    def build_environment(self):
        print "building environment..."
        for bundle in self.environment:
            bundle.build()

