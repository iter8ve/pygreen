import haml
import webassets
from webassets.bundle import wrap
import pathlib
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, callable):
        super(FileModifiedHandler, self).__init__()
        self.callable = callable

    def on_modified(self):
        self.callable()

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

    def __init__(self, config_path, rebuild=False):
        bundles = self._load_asset_bundles(config_path)
        self.environment = self._setup_environment(bundles)
        if rebuild:
            self._setup_rebuild()

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


    def _setup_rebuild(self):
        watched = self._resolve_assets_dir()
        rebuilder = FileModifiedHandler(self.environment)
        observer = Observer()
        observer.schedule(rebuilder, watched, recursive=True)
        observer.start()

    def build_environment(self):
        for bundle in self.environment:
            bundle.build()
