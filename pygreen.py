#! /usr/bin/python

# PyGreen
# Copyright (c) 2013, Nicolas Vanhoren
#
# Released under the MIT license
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
# AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import unicode_literals, print_function

import flask
from flask.ext.assets import Environment, Bundle
from flask.config import Config as FlaskConfig
import os.path
from mako.lookup import TemplateLookup
from mako.lexer import Lexer
import os
import os.path
import wsgiref.handlers
import sys
import logging
import re
import argparse
import sys
import markdown
import pathlib
import haml
import shutil
from assetmanager import AssetManager
from livereload import Server

_logger = logging.getLogger(__name__)

def create_app(static_folder='static', template_folder=None,
        root_path=".", config_file=None):
    app = flask.Flask('pygreen',
        static_folder=static_folder, template_folder=template_folder)
    app.root_path = root_path
    if config_file:
        app.config.from_pyfile(config_file)
    return app

def configure_views(app, file_renderer, postprocessor=None):
    app.add_url_rule('/', "root",
        lambda: file_renderer('index.haml', postprocessor),
        methods=['GET', 'POST', 'PUT', 'DELETE']
    )
    app.add_url_rule('/<path:path>', "all_files",
        lambda path: file_renderer(path, postprocessor),
        methods=['GET', 'POST', 'PUT', 'DELETE']
    )


def change_href_to_html(val):
    pattern = r'\.(haml|mako)'
    return re.sub(pattern, '.html', val)


def config_to_dict(root_path, config_file):
    config = FlaskConfig(root_path)
    config.from_pyfile(config_file)
    return dict((k, v) for k, v in config.iteritems())


class PolyLexer(Lexer):
    """
    Supports transparent preprocessing of .haml templates
    """
    def parse(self):
        fname, ext = os.path.splitext(self.filename)
        if ext == ".haml":
            self.preprocessor.insert(0, haml.preprocessor)
        return super(PolyLexer, self).parse()


class PyGreen(object):

    def __init__(self):
        # a set of strings that identifies the extension of the files
        # that should be processed using Mako
        self.template_exts = set(["html", "mako", "haml"])

        # the folder where the files to serve are located. Do not set
        # directly, use set_folder instead
        self.folder = "."

        # Process templates at instantiation
        self.templates = self._get_templates()

        # Set production to false as a default
        self.production = False

        self.manager = self._setup_manager()

        # A list of regular expression. Files whose the name match
        # one of those regular expressions will not be outputed when generating
        # a static version of the web site
        self.file_exclusion = [
            r".*\.py",
            r"(^|.*\/)\..*",
            r".*\.webassets-cache"
        ]

        # Support additional directories by
        # only accepting these on static page generation
        def dirpath_allowed(dirpath):
            allowed = set(("static", "templates"))
            disallowed = set(("includes", "layouts"))
            parts = set(pathlib.Path(dirpath).parts)
            return (parts & allowed) and not (parts & disallowed)

        def is_public(path):
            for ex in self.file_exclusion:
                if re.match(ex, path):
                    return False
            return True

        def base_lister():
            files = []
            for dirpath, dirnames, filenames in os.walk(self.folder):
                if dirpath_allowed(dirpath):
                    for f in filenames:
                        absp = os.path.join(dirpath, f)
                        path = os.path.relpath(absp, self.folder)
                        if is_public(path):
                            files.append(path)
            return files

        # A list of functions. Each function must return a list of paths
        # of files to export during the generation of the static web site.
        # The default one simply returns all the files contained in the folder.
        # It is necessary to define new listers when new routes are defined
        # in the Flask application, or the static site generation routine
        # will not be able to detect the files to export.
        self.file_listers = [base_lister]

        def file_renderer(path, postprocessor=None):
            if is_public(path):
                if path.split(".")[-1] in self.template_exts and \
                        self.templates.has_template(path):
                    t = self.templates.get_template(path)
                    data = t.render_unicode(pygreen=self,
                        config=config_to_dict(self.folder, self.config_file),
                        asset_urls=self.manager.asset_urls())
                    if callable(postprocessor):
                        data = postprocessor(data)
                    try:
                        return data.encode(t.module._source_encoding)
                    except:
                        return data
                if os.path.exists(os.path.join(self.folder, path)):
                    return flask.send_file(path)
            flask.abort(404)

        # The default function used to render files. Could be modified to change the way files are
        # generated, like using another template language or transforming css...
        self.file_renderer = file_renderer

    def set_folder(self, folder):
        """
        Sets the folder where the files to serve are located.
        """
        self.folder = folder
        self.templates.directories[0] = folder
        self.templates.directories[1] = os.path.join(folder, 'templates')

    def _get_templates(self):
        template_dir = os.path.join(self.folder, 'templates')
        return TemplateLookup(directories=[self.folder, template_dir],
            imports=["from markdown import markdown",
                     "from filters import smartydown, sectionize"],
            input_encoding='iso-8859-1',
            collection_size=100,
            lexer_cls=PolyLexer
        )

    def set_production(self, val=False):
        if val not in (True, False):
            raise ArgumentError('Value must be True or False')
        self.production = val
        self.manager = self._setup_manager()

    def _setup_manager(self):
        assets_config_path = os.path.relpath('assets.yml', self.folder)
        return AssetManager(assets_config_path,
            production=self.production)

    def run(self, host='0.0.0.0', port=8080, reload_assets=True):
        """
        Launch a development web server.
        """
        app = create_app(root_path=self.folder, config_file=self.config_file)
        configure_views(app, self.file_renderer)
        if reload_assets:
            app.before_first_request(self.manager.build_environment)
        app.run(host=host, port=port, debug=True,
            extra_files=self.manager.files_to_watch())

    def run_livereload(self):
        app = create_app(root_path=self.folder, config_file=self.config_file)
        configure_views(app, self.file_renderer)
        server = Server(app)
        for glob_pattern in self.manager.globs_to_watch():
            server.watch('assets/%s' % glob_pattern,
                self.manager.build_environment)
        server.watch('templates/*', self.manager.build_environment)
        server.watch('templates/**/*', self.manager.build_environment)
        server.serve(host="0.0.0.0")

    def get(self, path):
        """
        Get the content of a file, indentified by its path relative to the folder configured
        in PyGreen. If the file extension is one of the extensions that should be processed
        through Mako, it will be processed.
        """
        app = create_app(root_path=self.folder, config_file=self.config_file)
        configure_views(app, self.file_renderer,
            postprocessor=change_href_to_html)
        data = app.test_client().get("/%s" % path).data
        return data

    # Support templates directory (vice root directory only) and
    # .haml or .mako suffix (vice .html) for static generation.
    def _process_path(self, input_path):
        p = pathlib.Path(input_path)
        if p.parts[0] == 'templates':
            p = p.relative_to('templates')
        if p.suffix in ('.haml', '.mako'):
            p = p.with_suffix('.html')
        return str(p)

    def gen_static(self, output_folder, overwrite):
        """
        Generates a complete static version of the web site and stores it in
        output_folder.
        """
        # remove existing output_folder + contents
        if overwrite and os.path.exists(output_folder):
            shutil.rmtree(output_folder)

        files = []
        for l in self.file_listers:
            files += l()
        for f in files:
            _logger.info("generating %s" % f)
            content = self.get(f)
            loc = os.path.join(output_folder, self._process_path(f))
            d = os.path.dirname(loc)
            if not os.path.exists(d):
                os.makedirs(d)
            with open(loc, "wb") as file_:
                file_.write(content)

    def cli(self, cmd_args=None):
        """
        The command line interface of PyGreen.
        """
        logging.basicConfig(level=logging.INFO, format='%(message)s')

        parser = \
            argparse.ArgumentParser(description='PyGreen, micro web framework/static web site generator')
        subparsers = parser.add_subparsers(dest='action')

        parser_serve = subparsers.add_parser('serve', help='serve the web site')
        parser_serve.add_argument('-p', '--port', type=int, default=8080,
            help='server port')
        parser_serve.add_argument('-f', '--folder', default=".",
            help='folder containing files to serve')
        parser_serve.add_argument('-d', '--disable-templates',
            action='store_true', default=False,
            help='just serve static files, do not invoke Mako')
        parser_serve.add_argument('-r', '--reload',
            action='store_true', default=True,
            help='server reloads assets')
        parser_serve.add_argument('-l', '--livereload',
            action='store_true', default=False,
            help='use livereload server')
        parser_serve.add_argument('-z', '--production',
            action="store_true", default=False,
            help='use production filters')
        parser_serve.add_argument('-c', '--config-file',
            default="default.cfg", help='config file')

        def serve():
            if args.disable_templates:
                self.template_exts = set([])
            config_rel_path = os.path.relpath(args.config_file, self.folder)
            self.config_file = os.path.abspath(config_rel_path)
            self.set_production(args.production)
            if args.livereload:
                self.run_livereload()
            else:
                self.run(port=args.port, reload_assets=args.reload)

        parser_serve.set_defaults(func=serve)

        parser_gen = subparsers.add_parser('gen',
            help='generate a static version of the site')
        parser_gen.add_argument('output',
            help='folder to store the files')
        parser_gen.add_argument('-f', '--folder', default=".",
            help='folder containing files to serve')
        parser_gen.add_argument('-o', '--overwrite',
            action="store_true", default=False,
            help='overwrite existing output folder')
        parser_gen.add_argument('-z', '--production',
            action="store_true", default=False,
            help='use production filters')
        parser_gen.add_argument('-c', '--config-file',
            default="default.cfg", help='config file')

        def gen():
            assets_config_path = os.path.relpath('assets.yml', self.folder)
            config_rel_path = os.path.relpath(args.config_file, self.folder)
            self.config_file = os.path.abspath(config_rel_path)
            self.set_production(args.production)
            self.manager.build_environment(force=True)
            self.gen_static(args.output, overwrite=args.overwrite)

        parser_gen.set_defaults(func=gen)

        args = parser.parse_args(cmd_args)

        self.set_folder(args.folder)

        print(parser.description)
        print("")

        args.func()

pygreen = PyGreen()

if __name__ == "__main__":
    pygreen.cli()
