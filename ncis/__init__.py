"""
"""

import importlib
import pkgutil
from bottle import request, Bottle, abort, run
from functools import partial

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
API_VERSION = 1


app = Bottle()

route = None

nsic_plugins = {
    name
    for finder, name, ispkg
    in pkgutil.iter_modules()
    if name.startswith("ncis_")
}


def route_prefix(prefix, name, *largs, **kwargs):
    return app.route("/{}{}".format(prefix, name))


def install(host=None, port=None, plugins=None):
    global route
    if host is None:
        host = DEFAULT_HOST
    if port is None:
        port = DEFAULT_PORT
    if plugins is None:
        plugins = list(nsic_plugins.keys())
    for name in plugins:
        route = partial(route_prefix, name.replace("ncis_", ""))
        mod = importlib.import_module(name)
        nsic_plugins[name] = mod

    run(host=host, port=port)