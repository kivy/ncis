"""
NCIS
"""

import importlib
import pkgutil
import json
import weakref
from bottle import request, Bottle, abort, run, response
from functools import partial
from threading import Thread

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
API_VERSION = 1

# internal
_thread = None

#: Global bottle application. You don't need to use it directly.
app = Bottle()

#: Route decorator for the NCIS app
route = None

#: List of the plugin automatically discovered that will be imported at
#: :func:`install()`
ncis_plugins = {
    name: None
    for finder, name, ispkg
    in pkgutil.iter_modules()
    if name.startswith("ncis_")
}

#: List of all weakref to save for the json decoder
ncis_weakrefs = {}

class PythonObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            ref_id = None
            try:
                ref = weakref.ref(obj)
                ncis_weakrefs[id(ref)] = obj
                ref_id = id(ref)
            except TypeError:
                pass
            return {
                "__pyobject__": {
                    "type": type(obj).__name__,
                    "id": ref_id
                }
            }


def jsonify(val):
    response.content_type = "application/json"
    return json.dumps(val, cls=PythonObjectEncoder)


def api_response(resp=None):
    """In a API endpoint, return a JSON "ok" response, with your response
    attached to it::

    ```
    {
        "status": "ok",
        "response": YOUR_RESPONSE_HERE
    }
    ```
    """
    return jsonify({
        "status": "ok",
        "response": resp
    })

def api_error(error):
    """In a API endpoint, return a JSON "error" response, with your error
    attached to it::

    ```
    {
        "status": "ok",
        "error": YOUR_ERROR_HERE
    }
    ```
    """
    return jsonify({
        "status": "error",
        "error": error
    })


def route_prefix(prefix, name, *largs, **kwargs):
    return app.route("/{}{}".format(prefix, name), *largs, **kwargs)


def install(host=None, port=None, plugins=None):
    global _thread
    if host is None:
        host = DEFAULT_HOST
    if port is None:
        port = DEFAULT_PORT
    if plugins is None:
        plugins = list(ncis_plugins.keys())

    _thread = Thread(target=_run_ncis, kwargs={
        "host": host,
        "port": port,
        "plugins": plugins
    })
    _thread.daemon = True
    _thread.start()


def _run_ncis(host, port, plugins):
    global route
    for name in plugins:
        route = partial(route_prefix, name.replace("ncis_", ""))
        mod = importlib.import_module(name)
        ncis_plugins[name] = mod

    run(app, host=host, port=port)


@app.route("/_/version")
def ncis_version():
    plugins = {
        name: {
            "version": getattr(mod, "__version__", None),
            "author": getattr(mod, "__author__", None)
        } for name, mod in ncis_plugins.items()
    }
    return api_response({
        "version": API_VERSION,
        "plugins": plugins
    })


@app.route("/_/endpoints")
def ncis_endpoints():
    endpoints = [route.rule for route in app.routes]
    return api_response(endpoints)


@app.route("/_/help/<path:path>")
def ncis_help(path):
    path = "/" + path
    for route in app.routes:
        if route.rule == path:
            return api_response({
                "doc": getattr(route.callback, "__doc__", None)
            })
    return api_error("Not found")