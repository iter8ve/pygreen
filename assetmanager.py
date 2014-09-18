import haml
import webassets
from webassets.bundle import wrap
import pathlib
import os
import logging
import time

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class AssetManager(object):

    def _load_asset_bundles(self, config_path):
        if os.path.isfile(config_path):
            loader = webassets.loaders.YAMLLoader(config_path)
            return loader.load_bundles()
        return None

    def _adjust_bundle_outputs(self, bundles):
        for bundle in bundles.values():
            old_path, old_ext = os.path.splitext(bundle.output)
            bundle.output = ''.join((old_path, '.%(version)s', old_ext))
        return bundles

    def _setup_environment(self, bundles, production):
        if bundles is None:
            return None

        if production:
            bundles = self._adjust_bundle_outputs(bundles)

        env_config = {
            'directory': self._resolve_assets_dir(),
            'UGLIFYJS_EXTRA_ARGS': ['-c', '-m'],
            'SASS_DEBUG_INFO': False
        }

        if production:
            env_config.update({
                'debug': False,
                'manifest': 'cache',
                'cache': True,
                'auto_build': False,
                'url_expire': True
            })
        else:
            env_config.update({
                'debug': 'merge',
                'manifest': None,
                'cache': False,
                'auto_build': False,
                'url_expire': False
            })

        environment = webassets.Environment(**env_config)
        environment.url= ''

        for name, bundle in bundles.iteritems():
            log.debug("registering %s" % name)
            environment.register(name, bundle)
        return environment

    def __init__(self, config_path, production=False):
        log.debug("production %s" % production)
        bundles = self._load_asset_bundles(config_path)
        self.environment = self._setup_environment(bundles, production)

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
        if self.environment:
            for bundle in self.environment:
                if bundle.contents:
                    globs.extend(bundle.contents)
                if bundle.depends:
                    globs.extend(bundle.depends)
        return globs

    def build_environment(self, force=False):
        if self.environment:
            log.debug("building environment...")
            if force:
                log.debug("forcing update...")
            for bundle in self.environment:
                bundle.build(force=force)

    def asset_urls(self):
        urls = {}
        for name, bundle in self.environment._named_bundles.iteritems():
            urls[name] = [url.split('?')[0] for url in bundle.urls()]
        return urls

