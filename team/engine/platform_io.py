"""
How the engine talks to OpenEgiz: telemetry goes MQTT -> Ditto (Ditto
protocol commands on telemetry/<name>, like the Example Mine); twin state is
read back from the Ditto HTTP API.
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import paho.mqtt.client as mqtt

from params import NS

log = logging.getLogger("io")

DITTO_URL = os.environ.get("DITTO_URL", "http://localhost:8080").rstrip("/")
DITTO_USER = os.environ.get("DITTO_USER", "ditto")
DITTO_PASSWORD = os.environ.get("DITTO_PASSWORD", "")
AUTH = "Basic " + base64.b64encode(f"{DITTO_USER}:{DITTO_PASSWORD}".encode()).decode()


def ditto(method, path, body=None, timeout=20):
    request = urllib.request.Request(
        f"{DITTO_URL}/api/2{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Authorization": AUTH, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return response.status, (json.loads(raw) if raw else None)


def get_things(names):
    """{name: thing} for the given twin names; missing twins are left out."""
    ids = ",".join(f"{NS}:{n}" for n in names)
    _, things = ditto("GET", "/things?ids=" + urllib.parse.quote(ids, safe=",:"))
    return {t["thingId"].split(":", 1)[1]: t for t in things or []}


def prop(thing, feature, key="value", default=None):
    try:
        return thing["features"][feature]["properties"][key]
    except (KeyError, TypeError):
        return default


def connect_mqtt(client_id):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{client_id}-{os.getpid()}")
    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    for _ in range(60):
        try:
            client.connect(host, port, keepalive=30)
            break
        except OSError as exc:
            log.warning("MQTT %s:%s not reachable (%s), retrying", host, port, exc)
            time.sleep(2)
    else:
        raise SystemExit(f"giving up on MQTT {host}:{port}")
    client.loop_start()
    return client


def publish_features(client, name, features):
    """Replace all features of one twin through Ditto (topic telemetry/<name>)."""
    message = {
        "topic": f"{NS}/{name}/things/twin/commands/modify",
        "path": "/features",
        "value": {feature: {"properties": props} for feature, props in features.items()},
    }
    client.publish(f"telemetry/{name}", json.dumps(message), qos=0)


def wait_for_ditto(names, attempts=100):
    for _ in range(attempts):
        try:
            if len(get_things(names)) == len(names):
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            log.info("waiting for Ditto: %s", exc)
        time.sleep(3)
    raise SystemExit("twins did not appear in Ditto")
