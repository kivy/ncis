"""
NCIS
"""

import importlib
import pkgutil
import json
import weakref
import time
import sys
from flask import Flask, request, Response
from functools import partial
from threading import Thread, Event
from time import sleep
from collections import deque

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
API_VERSION = 1

# internal
_thread = None

#: Global flask application. You don't need to use it directly.
app = Flask("ncis")

#: Route decorator for the NCIS app
route = None

#: (internal) Stream event to trigger the stream endpoint to flush
stream_event = Event()
stream_q = deque(maxlen=10000)

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
            ref_id = obj_id = None
            try:
                ref = weakref.ref(obj)
                ref_id = id(ref)
                ncis_weakrefs[ref_id] = ref
                obj_id = id(obj)
            except TypeError:
                pass
            return {
                "__pyobject__": {
                    "type": type(obj).__name__,
                    "id": ref_id,
                    "original_id": obj_id
                }
            }


def jsonify(val, get_response=True):
    data = json.dumps(val, cls=PythonObjectEncoder)
    if get_response:
        return Response(data, mimetype="application/json")
    return data


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


def install(host=None, port=None, plugins=None, redirect_stdout=True):
    global _thread
    if host is None:
        host = DEFAULT_HOST
    if port is None:
        port = DEFAULT_PORT
    if plugins is None:
        plugins = list(ncis_plugins.keys())

    if redirect_stdout:
        install_stdout_redirect()

    _thread = Thread(target=_run_ncis, kwargs={
        "host": host,
        "port": port,
        "plugins": plugins,
    })
    _thread.daemon = True
    _thread.start()


def _run_ncis(host, port, plugins):
    global route
    for name in plugins:
        route = partial(route_prefix, name.replace("ncis_", ""))
        mod = importlib.import_module(name)
        ncis_plugins[name] = mod

    app.run(host=host, port=port, threaded=True)


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


def ncis_stream_push(event, data, binary=False):
    if not binary:
        data = jsonify(data, get_response=False)
    stream_q.appendleft({"event": event, "data": data})
    stream_event.set()


def install_stdout_redirect():
    class NCISProxyFile(object):
        def __init__(self, name, pipe, *args, **kwargs):
            super(NCISProxyFile, self).__init__(*args, **kwargs)
            self.name = name
            self.pipe = pipe

        def write(self, buf, *args, **kw):
            try:
                ncis_stream_push(self.name, buf)
            finally:
                return self.pipe.write(buf, *args, **kw)

        def flush(self, *args, **kw):
            self.pipe.flush(*args, **kw)

    sys.stdout = NCISProxyFile("stdout", sys.stdout)
    sys.stderr = NCISProxyFile("stderr", sys.stderr)


@app.route("/_/stream")
def ncis_stream():
    def _stream():
        yield 'retry: 20000\n\n'
        while True:
            stream_event.wait(10)
            stream_event.clear()
            while True:
                try:
                    entry = stream_q.pop()
                except IndexError:
                    break

                yield 'event: {}\n'.format(entry["event"])
                yield 'data: {}\n\n'.format(entry["data"])
    return Response(_stream(), mimetype="text/event-stream")