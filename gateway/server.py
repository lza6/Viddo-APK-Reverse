"""Viddo R1 本地网关（纯标准库，无第三方依赖，仅需 pycryptodome + requests）。

暴露的都是**已实测可用**的上游能力：
  POST /api/identity          建虚拟设备并从上游取会话 UUID（v4/getUuid，零鉴权）
  GET  /api/s3creds           取上游签发的 AWS S3 临时凭证（v4/getUuid + functionTag）
  POST /api/task              提交 v3/texttovideonew 任务，返回上游 task key
  GET  /api/task/<key>        轮询 v4/downLoad/<key>
  POST /api/points/new        建积分用户，返回 pointId
  GET  /api/points/balance    查余额
  GET  /api/points/config     查消耗配置
  GET  /api/points/tasks      查任务奖励表
  POST /api/points/claim      领任务奖励
  GET  /                        demo 页面

运行时: python gateway/server.py  (默认 0.0.0.0:8971)
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from points_client import PointsClient  # noqa: E402
from viddo_client import APP_ID, BASE, Device  # noqa: E402

PORT = 8971
DEVICES: dict[str, Device] = {}
POINTS: dict[str, PointsClient] = {}


def device(android_id: str) -> Device:
    dev = DEVICES.get(android_id)
    if dev is None:
        dev = Device(android_id=android_id)
        DEVICES[android_id] = dev
    return dev


def points(android_id: str) -> PointsClient:
    cli = POINTS.get(android_id)
    if cli is None:
        cli = PointsClient(android_id=android_id)
        POINTS[android_id] = cli
    return cli


class Handler(BaseHTTPRequestHandler):
    server_version = "viddo-r1/0.1"

    # ---------- 工具 ----------
    def _send(self, code: int, payload: dict | bytes, ctype: str = "application/json; charset=utf-8") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---------- 路由 ----------
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                html = (ROOT / "demo" / "index.html").read_bytes()
                self._send(200, html, "text/html; charset=utf-8")
            elif u.path == "/api/health":
                self._send(200, {"ok": True, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "upstream": BASE})
            elif u.path == "/api/s3creds":
                tag = q.get("tag", "texttovideo")
                dev = device(q.get("android_id", "demo00000000001"))
                dev.refresh_uuid()
                import requests

                form = dev.base_form()
                form["functionTag"] = tag
                s = requests.Session()
                s.trust_env = False
                r = s.post(BASE + "v4/getUuid", data=form, timeout=25)
                up = r.json()
                # 凭证脱敏：只暴露"是否签发"，不把临时 AK/SK 打到前端/日志
                if isinstance(up.get("other"), dict):
                    up["other"] = {
                        **{k: v for k, v in up["other"].items() if k not in ("accessKey", "secretKey")},
                        "accessKey": (up["other"].get("accessKey") or "")[:8] + "****",
                        "secretKey": "****",
                        "creds_issued": bool(up["other"].get("accessKey")),
                    }
                self._send(200, {"upstream": up})
            elif u.path.startswith("/api/task/"):
                key = u.path.rsplit("/", 1)[-1]
                dev = device(q.get("android_id", "demo00000000001"))
                self._send(200, dev.poll(key))
            elif u.path == "/api/points/balance":
                cli = points(q.get("android_id", "demo00000000001"))
                pid = q.get("point_id") or json.loads(
                    cli.post("point/user/getNewUserPointInfo.htm?osType=1")["plain"]
                ).get("pointId", "")
                self._send(200, {"point_id": pid, "balance": cli.post(
                    "point/user/getPointBalanceInfo.htm?osType=1", {"pointId": pid})})
            elif u.path == "/api/points/config":
                cli = points(q.get("android_id", "demo00000000001"))
                pid = q.get("point_id") or json.loads(
                    cli.post("point/user/getNewUserPointInfo.htm?osType=1")["plain"]
                ).get("pointId", "")
                self._send(200, cli.post("point/consume/getConsumePointConfig.htm?osType=1", {"pointId": pid}))
            elif u.path == "/api/points/tasks":
                cli = points(q.get("android_id", "demo00000000001"))
                pid = q.get("point_id") or json.loads(
                    cli.post("point/user/getNewUserPointInfo.htm?osType=1")["plain"]
                ).get("pointId", "")
                self._send(200, cli.post("point/task/getTaskUserPointConfig.htm?osType=1", {"pointId": pid}))
            else:
                self._send(404, {"error": "not found", "path": u.path})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": type(exc).__name__, "detail": str(exc)[:300],
                             "trace": traceback.format_exc()[-800:]})

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        try:
            body = self._body()
            raw = u.path.split("/")[1:]  # ['api', ...]
            if u.path == "/api/identity":
                dev = device(body.get("android_id") or f"demo{int(time.time()*1000)%10**13:013d}")
                t0 = time.perf_counter()
                uid = dev.refresh_uuid()
                self._send(200, {"android_id": dev.android_id, "uuId": dev.uuid_header, "uId": uid,
                                 "priority": dev.priority, "elapsed_ms": round((time.perf_counter()-t0)*1000, 1)})
            elif u.path == "/api/task":
                dev = device(body.get("android_id") or "demo00000000001")
                dev.refresh_uuid()
                t0 = time.perf_counter()
                r = dev.submit_frames(
                    body.get("endpoint", "v3/texttovideonew"),
                    {"prompt": body.get("prompt", "a cat walking on grass"),
                     "aspect_ratio": body.get("aspect_ratio", "9:16")},
                    {"platFormId": body.get("platFormId", ""),
                     "pointId": body.get("point_id", ""),
                     "consumeType": body.get("consume_type", "92")},
                )
                self._send(200, {"upstream": r, "elapsed_ms": round((time.perf_counter()-t0)*1000, 1)})
            elif u.path == "/api/points/new":
                cli = points(body.get("android_id") or f"pt{int(time.time()*1000)%10**13:013d}")
                self._send(200, cli.post("point/user/getNewUserPointInfo.htm?osType=1"))
            elif u.path == "/api/points/claim":
                cli = points(body.get("android_id") or "demo00000000001")
                self._send(200, cli.post("point/task/doAddTaskPoint.htm?osType=1",
                                         {"pointId": body.get("point_id", ""),
                                          "taskId": str(body.get("task_id", "1"))}))
            else:
                self._send(404, {"error": "not found", "path": u.path, "seg": raw})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": type(exc).__name__, "detail": str(exc)[:300],
                             "trace": traceback.format_exc()[-800:]})


if __name__ == "__main__":
    print(f"viddo R1 gateway on http://127.0.0.1:{PORT}  (appId={APP_ID})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
