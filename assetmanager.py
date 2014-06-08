import haml
import webassets
from webassets.bundle import wrap
import pathlib
import os
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
            logger.debug("registering %s" % name)
            environment.register(name, bundle)
        return environment

    def __init__(self, config_path):
        bundles = self._load_asset_bundles(config_path)
        self.environment = self._setup_environment(bundles)

    def _resolve_assets_dir(self):
        for dirpath, dirnames, files in os.walk('.'):
            if 'assets' in dirnames:
                return os.path.join(dirpath, 'assets')
        return None

    def files_to_watch(self):
        """
        List of paths resolved from globs in bundle configs
        """
        files, depends = [], []
        ctx = wrap(self.environment, None)
        for bundle in self.environment:
            files.extend(bundle.resolve_contents(force=True))
            depends.extend(bundle.resolve_depends(ctx))
        orig, abspaths = zip(*files)
        abspaths = list(abspaths)
        abspaths.extend(depends)
        return set(abspaths)

    def globs_to_watch(self):
        """
        List of raw globs from bundle configs
        """
        globs = []
        for bundle in self.environment:
            if bundle.contents:
                globs.extend(bundle.contents)
            if bundle.depends:
                globs.extend(bundle.depends)
        return globs



    def build_environment(self):
        logger.debug("building environment...")
        for bundle in self.environment:
            bundle.build()

