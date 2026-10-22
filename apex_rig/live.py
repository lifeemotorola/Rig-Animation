# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - live mocap over WiFi.

Blender runs a tiny web server.  You open the printed address on your phone
(camera, same WiFi), and the phone drives the rig live:

* The page uses the phone's **front camera** and, when the device has internet,
  MediaPipe Face Landmarker to compute the 52 ARKit-style blendshapes plus a
  head rotation.  Every frame is sent to Blender over a WebSocket.
* If MediaPipe cannot load (no internet on the phone), the page falls back to a
  built-in motion tracker: the face is located by skin-tone/darkness contrast
  and the head rotation plus a handful of expression channels are estimated
  from the tracked region.  Lower quality, but it always works offline.
* Blender maps the blendshapes onto the Apex face controls, drives neck/head
  rotation with limits and smoothing, shows a live preview in the N-panel and
  can record everything into a keyed action ("Take 1"...).

No external Python packages are required on the Blender side: the HTTP server
and the WebSocket framing are implemented here with the standard library.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import socket
import ssl
import struct
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy
from mathutils import Euler, Quaternion, Vector

from . import utils

DEFAULT_PORT = 8770
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

STATE = {
    "server": None,
    "thread": None,
    "queue": [],
    "lock": threading.Lock(),
    "frames": 0,
    "last_seen": 0.0,
    "last_payload": {},
    "clients": 0,
    "recording": False,
    "take": [],
    "take_name": "",
    "applied": {},
    "fps": 0.0,
    "last_times": [],
}


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------
def local_ip() -> str:
    """Best-effort LAN address of this machine."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        probe.close()


# Browsers only expose the camera (getUserMedia) on secure pages.  A phone
# opening http://<LAN-IP>:port is NOT a secure page, so the camera silently
# fails.  The server therefore speaks HTTPS with a self-signed certificate
# generated locally (needs the openssl command); the phone accepts it once.
TLS_STATE = {"ip": "", "ctx": None, "der": b""}


def _tls_material(ip: str):
    """Create (or reuse) a self-signed certificate for *ip*. Returns paths.

    Built in pure Python (see selfsign.py), so no openssl binary is needed.
    """
    from . import selfsign
    base = os.path.join(tempfile.gettempdir(), "apex_live_tls")
    os.makedirs(base, exist_ok=True)
    safe = re.sub(r"[^0-9A-Za-z.]", "_", ip)
    cert = os.path.join(base, f"cert_{safe}.pem")
    key = os.path.join(base, f"key_{safe}.pem")
    if not (os.path.exists(cert) and os.path.exists(key)):
        cert_pem, key_pem, _der = selfsign.generate(ip)
        with open(key, "w", encoding="ascii") as fh:
            fh.write(key_pem)
        with open(cert, "w", encoding="ascii") as fh:
            fh.write(cert_pem)
    return cert, key


def _tls_context(ip: str):
    """Server-side SSL context for *ip*, or None when TLS is unavailable."""
    if TLS_STATE["ctx"] is not None and TLS_STATE["ip"] == ip:
        return TLS_STATE["ctx"]
    try:
        cert, key = _tls_material(ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        with open(cert, "rb") as fh:
            pem = fh.read().decode("ascii")
        TLS_STATE.update(ip=ip, ctx=ctx, der=ssl.PEM_cert_to_DER_cert(pem))
        return ctx
    except Exception as exc:          # no openssl, or unwritable temp dir
        utils.log.warning("live mocap: HTTPS unavailable (%s); using http", exc)
        return None


def scheme_for(ip: str) -> str:
    return "https" if _tls_context(ip) is not None else "http"


def server_url(port: int | None = None, token: str = "") -> str:
    port = port or bpy.context.scene.apex_settings.live_port
    ip = local_ip()
    url = f"{scheme_for(ip)}://{ip}:{int(port)}/"
    if token:
        url += f"?t={token}"
    return url


# ---------------------------------------------------------------------------
# Minimal WebSocket server (RFC 6455: handshake + text/binary frames)
# ---------------------------------------------------------------------------
def _ws_accept(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _ws_read(conn) -> tuple[int, bytes] | None:
    header = conn.recv(2)
    if len(header) < 2:
        return None
    opcode = header[0] & 0x0F
    masked = header[1] & 0x80
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", conn.recv(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", conn.recv(8))[0]
    mask = conn.recv(4) if masked else b""
    data = b""
    while len(data) < length:
        chunk = conn.recv(min(65536, length - len(data)))
        if not chunk:
            return None
        data += chunk
    if masked:
        data = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
    return opcode, data


def _ws_send(conn, payload: str, opcode: int = 0x1) -> None:
    data = payload.encode("utf-8")
    header = bytearray()
    header.append(0x80 | opcode)
    length = len(data)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    conn.sendall(bytes(header) + data)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):        # keep the console clean
        return

    # ---- page -----------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/cert":            # install this once on the phone if needed
            body = TLS_STATE["der"]
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "application/x-x509-ca-cert")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/status":
            payload = json.dumps({
                "ok": True,
                "frames": STATE["frames"],
                "clients": STATE["clients"],
                "recording": STATE["recording"],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/frame":          # HTTP fallback when WebSocket is blocked
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else b"{}"
        if self.path.split("?")[0] == "/frame":
            _ingest(data)
        self.send_response(204)
        self.end_headers()

    # ---- websocket ------------------------------------------------------
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def _maybe_websocket(self) -> bool:
        if (self.headers.get("Upgrade") or "").lower() != "websocket":
            return False
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = _ws_accept(key)
        self.wfile.write(
            ("HTTP/1.1 101 Switching Protocols\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode("ascii"))
        self.wfile.flush()
        self.close_connection = True
        STATE["clients"] += 1
        try:
            _ws_send(self.connection, json.dumps({"type": "hello",
                                                 "rig": _rig_name()}))
            while STATE["server"] is not None:
                frame = _ws_read(self.connection)
                if frame is None:
                    break
                opcode, data = frame
                if opcode == 0x8:            # close
                    break
                if opcode == 0x9:            # ping
                    _ws_send(self.connection, data.decode("utf-8", "ignore"), 0xA)
                    continue
                _ingest(data)
        except Exception:
            pass
        finally:
            STATE["clients"] = max(0, STATE["clients"] - 1)
        return True

    def do_GET_ws(self):                 # pragma: no cover - never used
        pass


def _rig_name() -> str:
    for ob in bpy.data.objects:
        if ob.type == "ARMATURE" and utils.is_apex_rig(ob):
            return ob.name
    return ""


def _ingest(data: bytes) -> None:
    """Queue a payload from a phone (called on a worker thread)."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return
    now = time.time()
    STATE["last_times"].append(now)
    STATE["last_times"] = STATE["last_times"][-40:]
    with STATE["lock"]:
        STATE["queue"].append(payload)
        if len(STATE["queue"]) > 240:            # never grow without bound
            STATE["queue"] = STATE["queue"][-120:]


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------
class LiveServer:
    def __init__(self, port: int = DEFAULT_PORT, host: str = "0.0.0.0"):
        self.port = int(port)
        self.host = host
        self.httpd = None
        self.thread = None

    def start(self):
        handler = type("ApexLiveHandler", (_Handler,), {
            "do_GET": lambda self: (self._maybe_websocket() or
                                    _Handler.do_GET(self)),
        })
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        ctx = _tls_context(local_ip())
        if ctx is not None:
            self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True,
                                                    do_handshake_on_connect=False)
        STATE["server"] = self
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="ApexLiveHTTP", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        STATE["server"] = None
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
            except Exception:
                pass
            try:
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None
        self.thread = None


# ---------------------------------------------------------------------------
# Blendshape -> Apex face mapping
# ---------------------------------------------------------------------------
def _bs(payload: dict, name: str, default: float = 0.0) -> float:
    shapes = payload.get("blendshapes") or {}
    try:
        return float(shapes.get(name, default))
    except (TypeError, ValueError):
        return default


def payload_to_face(payload: dict) -> dict:
    """Convert a phone payload into Apex facial control values."""
    out = {}

    def add(prop, value, gain=1.0, cap=1.0):
        out[prop] = min(cap, max(-cap, out.get(prop, 0.0) + value * gain))

    # jaw
    add("jaw_open", _bs(payload, "jawOpen"), 1.25)
    add("jaw_side", _bs(payload, "jawRight") - _bs(payload, "jawLeft"), 1.1)
    add("jaw_thrust", _bs(payload, "jawForward"), 1.0)
    add("chin_raise", -_bs(payload, "mouthShrugLower"), 0.8)

    # lips
    add("lip_up_raise", max(_bs(payload, "mouthUpperUpLeft"),
                            _bs(payload, "mouthUpperUpRight")), 1.15)
    add("lip_low_drop", max(_bs(payload, "mouthLowerDownLeft"),
                            _bs(payload, "mouthLowerDownRight")), 1.1)
    add("lip_roll_up", _bs(payload, "mouthRollUpper"), 1.0)
    add("lip_roll_low", _bs(payload, "mouthRollLower"), 1.0)
    add("mouth_pucker", max(_bs(payload, "mouthPucker"),
                            _bs(payload, "mouthFunnel")), 1.15)
    add("mouth_smile.L", _bs(payload, "mouthSmileLeft"), 1.05)
    add("mouth_smile.R", _bs(payload, "mouthSmileRight"), 1.05)
    add("mouth_frown.L", _bs(payload, "mouthFrownLeft"), 1.0)
    add("mouth_frown.R", _bs(payload, "mouthFrownRight"), 1.0)
    add("mouth_stretch.L", _bs(payload, "mouthStretchLeft"), 1.0)
    add("mouth_stretch.R", _bs(payload, "mouthStretchRight"), 1.0)

    # cheeks / brows
    add("cheek_raise.L", max(_bs(payload, "cheekSquintLeft"),
                             _bs(payload, "mouthDimpleLeft") * 0.6), 1.0)
    add("cheek_raise.R", max(_bs(payload, "cheekSquintRight"),
                             _bs(payload, "mouthDimpleRight") * 0.6), 1.0)
    add("brow_raise.L", _bs(payload, "browOuterUpLeft"), 1.1)
    add("brow_raise.R", _bs(payload, "browOuterUpRight"), 1.1)
    add("brow_inner_up", _bs(payload, "browInnerUp"), 1.1)
    add("brow_furrow", max(_bs(payload, "browDownLeft"),
                           _bs(payload, "browDownRight")), 1.1)

    # eyes
    add("blink.L", _bs(payload, "eyeBlinkLeft"), 1.15)
    add("blink.R", _bs(payload, "eyeBlinkRight"), 1.15)
    add("squint.L", max(_bs(payload, "eyeSquintLeft"),
                        _bs(payload, "cheekSquintLeft") * 0.4), 1.0)
    add("squint.R", max(_bs(payload, "eyeSquintRight"),
                        _bs(payload, "cheekSquintRight") * 0.4), 1.0)
    look_x = (_bs(payload, "eyeLookOutLeft") + _bs(payload, "eyeLookInRight")
              - _bs(payload, "eyeLookInLeft") - _bs(payload, "eyeLookOutRight"))
    add("eye_look_x", look_x * 0.75, 1.0)
    look_y = (_bs(payload, "eyeLookUpLeft") + _bs(payload, "eyeLookUpRight")
              - _bs(payload, "eyeLookDownLeft") - _bs(payload, "eyeLookDownRight"))
    add("eye_look_y", look_y * 0.75, 1.0)

    # nose / tongue
    add("nose_wrinkle", max(_bs(payload, "noseSneerLeft"),
                            _bs(payload, "noseSneerRight")), 1.1)
    add("nose_flare.L", _bs(payload, "cheekPuff") * 0.6, 1.0)
    add("nose_flare.R", _bs(payload, "cheekPuff") * 0.6, 1.0)
    add("tongue_out", _bs(payload, "tongueOut"), 1.0)

    # a phone payload may also carry explicit values (manual sliders / fallback)
    for key, value in payload.items():
        if key.startswith("face_"):
            out[key[5:]] = float(value)
    return out


# ---------------------------------------------------------------------------
# Applying a payload to the rig (main thread only)
# ---------------------------------------------------------------------------
_last_head = Quaternion((1, 0, 0, 0))


def apply_payload(arm, payload: dict, settings=None, smooth: float = 0.55) -> dict:
    """Apply one tracked frame to *arm*; returns what was applied."""
    from . import face as face_mod

    if arm is None:
        return {}
    applied = {}

    if face_mod.has_face(arm):
        values = payload_to_face(payload)
        current = face_mod.get_face(arm)
        blended = {}
        for name, value in values.items():
            if name not in current:
                continue
            spec = face_mod.FACE_PROPS.get(name)
            if spec is None:
                continue
            value = max(spec[1], min(spec[2], value))
            old = current.get(name, 0.0)
            alpha = 1.0 if not smooth else max(0.05, min(1.0, 1.0 - smooth))
            blended[name] = old + (value - old) * alpha
        face_mod.set_face(arm, blended)
        applied.update(blended)

    # head rotation from the phone (degrees, camera space)
    global _last_head
    euler = payload.get("head") or {}
    try:
        pitch = float(euler.get("pitch", 0.0))
        yaw = float(euler.get("yaw", 0.0))
        roll = float(euler.get("roll", 0.0))
    except (TypeError, ValueError):
        pitch = yaw = roll = 0.0
    if any(abs(v) > 1e-4 for v in (pitch, yaw, roll)):
        if getattr(settings, "live_head", True):
            yaw = max(-70.0, min(70.0, yaw))
            pitch = max(-45.0, min(45.0, pitch))
            roll = max(-40.0, min(40.0, roll))
            # spread the rotation over neck + head for a natural result
            neck = arm.pose.bones.get("neck")
            head = arm.pose.bones.get("head")
            if neck is not None and head is not None:
                if neck.rotation_mode != "XYZ":
                    neck.rotation_mode = "XYZ"
                if head.rotation_mode != "XYZ":
                    head.rotation_mode = "XYZ"
                target_neck = Euler((math.radians(pitch * 0.35),
                                     math.radians(roll * 0.35),
                                     math.radians(yaw * 0.35)), "XYZ")
                target_head = Euler((math.radians(pitch * 0.65),
                                     math.radians(roll * 0.65),
                                     math.radians(yaw * 0.65)), "XYZ")
                alpha = 0.45
                neck.rotation_euler[0] += (target_neck[0] - neck.rotation_euler[0]) * alpha
                neck.rotation_euler[1] += (target_neck[1] - neck.rotation_euler[1]) * alpha
                neck.rotation_euler[2] += (target_neck[2] - neck.rotation_euler[2]) * alpha
                head.rotation_euler[0] += (target_head[0] - head.rotation_euler[0]) * alpha
                head.rotation_euler[1] += (target_head[1] - head.rotation_euler[1]) * alpha
                head.rotation_euler[2] += (target_head[2] - head.rotation_euler[2]) * alpha
                applied["neck_pitch"] = pitch
                applied["neck_yaw"] = yaw
    utils.refresh(arm)
    return applied


def pump(arm, settings=None, max_frames: int = 8) -> int:
    """Apply queued frames (called from a timer or by the tests)."""
    if arm is None:
        return 0
    applied = 0
    for _ in range(max_frames):
        with STATE["lock"]:
            if not STATE["queue"]:
                break
            payload = STATE["queue"].pop(0)
        STATE["frames"] += 1
        STATE["last_seen"] = time.time()
        STATE["last_payload"] = payload
        STATE["applied"] = apply_payload(arm, payload, settings)
        if STATE["recording"]:
            STATE["take"].append((STATE["frames"], payload))
        applied += 1
    times = STATE["last_times"]
    if len(times) > 3:
        span = times[-1] - times[0]
        STATE["fps"] = round((len(times) - 1) / span, 1) if span > 0 else 0.0
    return applied


def _timer():
    """Blender timer: keeps applying frames while the server is running."""
    scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "apex_settings", None) if scene else None
    if settings is None:
        return 0.05
    arm = utils.active_rig() or utils.first_rig()
    if arm is not None:
        pump(arm, settings)
        settings.live_frames = STATE["frames"]
        settings.live_fps = STATE["fps"]
        settings.live_clients = STATE["clients"]
    if STATE["server"] is None:
        return None
    return 0.033


def start(port: int | None = None) -> str:
    """Start the server and register the Blender timer. Returns the URL."""
    stop()
    scene = bpy.context.scene
    settings = getattr(scene, "apex_settings", None)
    port = int(port or (settings.live_port if settings else DEFAULT_PORT))
    server = LiveServer(port).start()
    STATE["server"] = server
    STATE["frames"] = 0
    STATE["last_times"] = []
    try:
        bpy.app.timers.register(_timer, first_interval=0.05, persistent=True)
    except Exception as exc:
        utils.log.debug("live timer not registered: %s", exc)
    if settings is not None:
        settings.live_port = port
        settings.live_url = server_url(port, settings.live_token)
    return server_url(port, settings.live_token if settings else "")


def stop() -> None:
    server = STATE.get("server")
    if isinstance(server, LiveServer):
        server.stop()
    STATE["server"] = None
    try:
        if bpy.app.timers.is_registered(_timer):
            bpy.app.timers.unregister(_timer)
    except Exception:
        pass


def is_running() -> bool:
    return STATE["server"] is not None


# ---------------------------------------------------------------------------
# Recording / baking
# ---------------------------------------------------------------------------
def start_recording(name: str = "") -> None:
    STATE["take"] = []
    STATE["take_name"] = name or f"Apex_Live_{time.strftime('%H%M%S')}"
    STATE["recording"] = True


def stop_recording() -> int:
    STATE["recording"] = False
    return len(STATE["take"])


def bake_take(arm, fps: float = 30.0, name: str | None = None):
    """Turn the recorded take into a keyframe action on the rig."""
    from . import face as face_mod

    take = STATE["take"]
    if not take or arm is None:
        return None
    action = bpy.data.actions.new(utils.unique_name(
        name or STATE["take_name"] or "Apex_Live", bpy.data.actions))
    action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    try:
        arm.animation_data.action_slot = (action.slots[0] if action.slots
                                          else action.slots.new(id_type="OBJECT",
                                                                name=arm.name))
    except Exception:
        pass
    props_bone = arm.pose.bones.get(arm.get("root_bone", "root"))
    has_face = face_mod.has_face(arm)
    scene = bpy.context.scene
    for index, payload in take:
        frame = int(round(index * max(1.0, 30.0) / max(fps, 1.0)))
        scene.frame_set(max(1, frame))
        # re-apply without smoothing so the baked curves follow the take
        if has_face:
            face_mod.set_face(arm, payload_to_face(payload))
            if props_bone is not None:
                for prop in face_mod.FACE_PROPS:
                    if prop in props_bone.keys():
                        props_bone.keyframe_insert(f'["{prop}"]', frame=max(1, frame))
        head = payload.get("head") or {}
        for bone_name, factor in (("neck", 0.35), ("head", 0.65)):
            pb = arm.pose.bones.get(bone_name)
            if pb is None:
                continue
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (
                math.radians(float(head.get("pitch", 0.0)) * factor),
                math.radians(float(head.get("roll", 0.0)) * factor),
                math.radians(float(head.get("yaw", 0.0)) * factor),
            )
            pb.keyframe_insert("rotation_euler", frame=max(1, frame))
    return action


# ---------------------------------------------------------------------------
# Phone page
# ---------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Apex Live Mocap</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font:14px/1.4 system-ui,sans-serif;background:#0d1117;color:#e6edf3;
     display:flex;flex-direction:column;height:100vh;overflow:hidden}
header{padding:10px 14px;background:#161b22;border-bottom:1px solid #30363d;
       display:flex;align-items:center;gap:10px}
header b{font-size:15px;letter-spacing:.3px}
.dot{width:9px;height:9px;border-radius:50%;background:#f85149}
.dot.on{background:#3fb950;box-shadow:0 0 8px #3fb950}
#wrap{position:relative;flex:1;background:#000;overflow:hidden}
video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}
#overlay{position:absolute;inset:0;pointer-events:none}
footer{padding:10px 14px;background:#161b22;border-top:1px solid #30363d;
       display:grid;grid-template-columns:1fr 1fr;gap:8px}
button{padding:11px;border-radius:9px;border:1px solid #30363d;background:#21262d;
       color:#e6edf3;font-size:14px;font-weight:600}
button.primary{background:#1f6feb;border-color:#1f6feb}
button:active{transform:scale(.98)}
#stat{position:absolute;left:10px;top:10px;font:11px/1.35 ui-monospace,monospace;
      background:#000a;padding:7px 9px;border-radius:7px;white-space:pre;pointer-events:none}
#msg{position:absolute;inset:auto 12px 12px 12px;background:#000b;padding:11px;
     border-radius:9px;font-size:12.5px;display:none}
</style></head>
<body>
<header><span class="dot" id="dot"></span><b>Apex Live Mocap</b>
  <span id="mode" style="margin-left:auto;font-size:12px;color:#8b949e">idle</span></header>
<div id="wrap">
  <video id="video" playsinline muted autoplay></video>
  <canvas id="overlay"></canvas>
  <div id="stat">waiting for camera…</div>
  <div id="msg"></div>
</div>
<footer>
  <button id="start" class="primary">Start camera</button>
  <button id="stop">Stop</button>
</footer>
<script type="module">
const video = document.getElementById('video');
const overlay = document.getElementById('overlay');
const statBox = document.getElementById('stat');
const dot = document.getElementById('dot');
const modeEl = document.getElementById('mode');
const msg = document.getElementById('msg');

let ws = null, running = false, lastSent = 0, sent = 0;
let landmarker = null, useMediaPipe = false;
let prevFrame = null, trackBox = null, t0 = performance.now();

function log(t){ statBox.textContent = t; }
function show(m){ msg.style.display='block'; msg.textContent=m; }

// ---------- socket ----------
function connect(){
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { dot.classList.add('on'); modeEl.textContent='connected'; };
  ws.onclose = () => { dot.classList.remove('on'); modeEl.textContent='reconnecting';
                       setTimeout(connect, 800); };
  ws.onerror = () => {};
}
function send(payload){
  const now = performance.now();
  const fps = 30;
  if (now - lastSent < 1000/fps) return;
  lastSent = now; sent++;
  const body = JSON.stringify(payload);
  if (ws && ws.readyState === 1) ws.send(body);
  else fetch('/frame', {method:'POST', body});
}
connect();

// ---------- camera ----------
async function startCamera(){
  if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
    throw new Error('The browser blocked the camera because this page is not secure (plain http). '
      + 'Open the https:// address shown in Blender, tap "Advanced" then "Proceed", '
      + 'and make sure the link starts with https://. If it still fails, install the certificate from '
      + location.origin + '/cert and try again.');
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {facingMode:'user', width:{ideal:640}, height:{ideal:480}, frameRate:{ideal:30}},
    audio: false
  });
  video.srcObject = stream;
  await video.play();
  running = true;
  dot.classList.add('on');
  document.getElementById('start').textContent = 'Camera on';
}

// ---------- MediaPipe (preferred) ----------
async function startMediaPipe(){
  try{
    const mp = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14');
    const files = await mp.FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm');
    landmarker = await mp.FaceLandmarker.createFromOptions(files, {
      baseOptions:{modelAssetPath:
        'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
        delegate:'GPU'},
      runningMode:'VIDEO', numFaces:1, outputFaceBlendshapes:true,
      outputFacialTransformationMatrixes:true
    });
    useMediaPipe = true;
    modeEl.textContent = 'MediaPipe 52 blendshapes';
    return true;
  }catch(e){
    useMediaPipe = false;
    modeEl.textContent = 'offline tracker';
    show('MediaPipe could not load (phone has no internet). Using the built-in offline tracker: head rotation + jaw/brows/blink estimates.');
    return false;
  }
}

function mediaPipeFrame(){
  if (!landmarker || video.readyState < 2) return null;
  const now = performance.now();
  let res;
  try { res = landmarker.detectForVideo(video, now); } catch(e) { return null; }
  if (!res || !res.faceBlendshapes || !res.faceBlendshapes.length) return null;
  const shapes = {};
  for (const c of res.faceBlendshapes[0].categories) shapes[c.categoryName] = c.score;
  let head = {pitch:0,yaw:0,roll:0};
  const m = res.facialTransformationMatrixes && res.facialTransformationMatrixes[0];
  if (m && m.data && m.data.length >= 16){
    const d = m.data; // column-major 4x4
    const r00=d[0], r10=d[1], r20=d[2];
    const r21=d[6], r22=d[10];
    const sy = Math.hypot(r00, r10);
    head.pitch = Math.atan2(-r20, sy) * 180/Math.PI;
    head.yaw   = Math.atan2(r10, r00) * 180/Math.PI;
    head.roll  = Math.atan2(r21, r22) * 180/Math.PI;
  }
  return {type:'frame', blendshapes:shapes, head, source:'mediapipe'};
}

// ---------- offline fallback ----------
// Skin-tone face box + brightness-based blink/jaw estimates. Coarse but works
// with no network at all.
const work = document.createElement('canvas');
work.width = 160; work.height = 120;
const wctx = work.getContext('2d', {willReadFrequently:true});

function offlineFrame(){
  if (video.readyState < 2) return null;
  wctx.drawImage(video, 0, 0, work.width, work.height);
  const img = wctx.getImageData(0, 0, work.width, work.height).data;
  const W = work.width, H = work.height;
  let sx=0, sy=0, n=0, minX=W, maxX=0, minY=H, maxY=0;
  let dark=0, bright=0;
  for (let y=0; y<H; y+=2){
    for (let x=0; x<W; x+=2){
      const i = (y*W + x)*4;
      const r=img[i], g=img[i+1], b=img[i+2];
      const yv = 0.299*r + 0.587*g + 0.114*b;
      if (yv > 210) bright++;
      if (yv < 55) dark++;
      // skin test
      const skin = r>70 && g>40 && b>20 && r>g && g>b && (r-Math.min(g,b))>12;
      if (skin){ sx+=x; sy+=y; n++;
        if (x<minX) minX=x; if (x>maxX) maxX=x;
        if (y<minY) minY=y; if (y>maxY) maxY=y; }
    }
  }
  if (n < 40) return null;
  const cx = sx/n / W, cy = sy/n / H;
  const w = (maxX-minX)/W, h = (maxY-minY)/H;
  let yaw=0, pitch=0, roll=0;
  if (trackBox){
    yaw   = (cx - trackBox.cx) * 160;
    pitch = (cy - trackBox.cy) * 140;
    roll  = (trackBox.roll||0)*0.7 + (cx - trackBox.cx)*40*0.3;
  }
  trackBox = {cx, cy, w, h, roll};
  const mouth = Math.max(0, (h - 0.42)) * 2.2;           // crude jaw-open proxy
  const blink = Math.max(0, Math.min(1, (bright/(n*4+1)) * 3));
  return {type:'frame', source:'offline', head:{pitch, yaw, roll},
          blendshapes:{jawOpen:Math.min(1,mouth), eyeBlinkLeft:blink,
                       eyeBlinkRight:blink, mouthSmileLeft:0.1, mouthSmileRight:0.1},
          box:[minX/W, minY/H, maxX/W, maxY/H]};
}

// ---------- loop ----------
function loop(){
  requestAnimationFrame(loop);
  if (!running) return;
  const payload = (useMediaPipe ? mediaPipeFrame() : offlineFrame());
  if (payload) send(payload);
  const dt = (performance.now()-t0)/1000;
  log(`${useMediaPipe?'MediaPipe':'offline'}  sent ${sent}\n` +
      `${(sent/Math.max(dt,0.001)).toFixed(1)} fps  ${ws&&ws.readyState===1?'ws':'http'}`);
}

document.getElementById('start').onclick = async () => {
  try{
    await startCamera();
    await startMediaPipe();
    requestAnimationFrame(loop);
  }catch(e){ show('Camera error: '+e.message); }
};
document.getElementById('stop').onclick = () => {
  running = false;
  if (video.srcObject){ video.srcObject.getTracks().forEach(t=>t.stop()); video.srcObject=null; }
  document.getElementById('start').textContent = 'Start camera';
  modeEl.textContent = 'stopped';
};
</script></body></html>
"""
