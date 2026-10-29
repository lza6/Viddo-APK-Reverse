"""Viddo R1 压测：并发度 × 各链路端点。

被测对象是第三方上游，压测规模刻意保持温和（≤32 并发 / 数千请求），
目标是测出延迟分布与限流行为，而不是打垮服务。

用法: python stress/stress_r1.py [--conc 16] [--n 200]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from points_client import PointsClient  # noqa: E402
from viddo_client import BASE, APP_ID, PKG, Device, rsa_encrypt, md5_hex  # noqa: E402

OUT = Path(__file__).resolve().parent / "stress_round1.json"


class Stats:
    def __init__(self) -> None:
        self.lat: list[float] = []
        self.codes: dict[str, int] = {}
        self.errs: dict[str, int] = {}
        self.lock = threading.Lock()

    def add(self, ms: float, key: str) -> None:
        with self.lock:
            self.lat.append(ms)
            self.codes[key] = self.codes.get(key, 0) + 1

    def err(self, name: str) -> None:
        with self.lock:
            self.errs[name] = self.errs.get(name, 0) + 1

    def summary(self) -> dict:
        if not self.lat:
            return {"n": 0, "errors": self.errs}
        s = sorted(self.lat)
        return {
            "n": len(s),
            "ok": sum(v for k, v in self.codes.items() if k.startswith("ok")),
            "codes": self.codes,
            "errors": self.errs,
            "p50_ms": round(statistics.median(s), 1),
            "p90_ms": round(s[int(len(s) * 0.9) - 1], 1),
            "p99_ms": round(s[min(int(len(s) * 0.99), len(s) - 1)], 1),
            "max_ms": round(s[-1], 1),
            "mean_ms": round(statistics.fmean(s), 1),
        }


def get_uuid_once(i: int) -> tuple[float, str]:
    dev = Device(android_id=f"r1{i:016x}"[-16:])
    t0 = time.perf_counter()
    try:
        dev.refresh_uuid()
        return (time.perf_counter() - t0) * 1000, "ok"
    except Exception as exc:  # noqa: BLE001
        return (time.perf_counter() - t0) * 1000, f"err:{type(exc).__name__}"


def submit_once(i: int, pid: str) -> tuple[float, str]:
    dev = Device(android_id=f"s1{i:016x}"[-16:])
    t0 = time.perf_counter()
    try:
        dev.refresh_uuid()
        r = dev.submit_frames(
            "v3/texttovideonew",
            {"prompt": "stress test prompt", "aspect_ratio": "9:16"},
            {"platFormId": "", "pointId": pid, "consumeType": "92"},
        )
        if r.get("success"):
            return (time.perf_counter() - t0) * 1000, "ok:accepted"
        return (time.perf_counter() - t0) * 1000, f"code:{r.get('code')}"
    except Exception as exc:  # noqa: BLE001
        return (time.perf_counter() - t0) * 1000, f"err:{type(exc).__name__}"


def poll_once(i: int, key: str) -> tuple[float, str]:
    dev = Device(android_id=f"p1{i:016x}"[-16:])
    t0 = time.perf_counter()
    try:
        r = dev.poll(key)
        return (time.perf_counter() - t0) * 1000, f"code:{r.get('code')}"
    except Exception as exc:  # noqa: BLE001
        return (time.perf_counter() - t0) * 1000, f"err:{type(exc).__name__}"


def points_newuser_once(i: int) -> tuple[float, str]:
    c = PointsClient(android_id=f"n1{i:012x}"[-16:])
    t0 = time.perf_counter()
    try:
        r = c.post("point/user/getNewUserPointInfo.htm?osType=1")
        if '"retCode":1' in str(r.get("plain")):
            return (time.perf_counter() - t0) * 1000, "ok"
        return (time.perf_counter() - t0) * 1000, "ret:fail"
    except Exception as exc:  # noqa: BLE001
        return (time.perf_counter() - t0) * 1000, f"err:{type(exc).__name__}"


def run(name: str, fn, conc: int, n: int, *args) -> dict:
    st = Stats()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as pool:
        for ms, code in pool.map(lambda i: fn(i, *args), range(n)):
            st.add(ms, code)
    wall = time.perf_counter() - t0
    out = st.summary()
    out["wall_s"] = round(wall, 2)
    out["rps"] = round(n / wall, 2)
    out["endpoint"] = name
    out["conc"] = conc
    print(f"[{name}] n={n} conc={conc} rps={out['rps']} p50={out.get('p50_ms')} "
          f"p90={out.get('p90_ms')} p99={out.get('p99_ms')} codes={out['codes']} errs={out['errors']}")
    return out


def s3_creds_probe() -> dict:
    """验证 v4/getUuid + functionTag 是否签发 S3 临时凭证。"""
    import requests

    s = requests.Session()
    s.trust_env = False
    form = {
        "appId": APP_ID, "uuId": "jrxc_stress0000000001", "pkgName": PKG, "lang": "en_US",
        "country": "US", "channelName": "GOOGLEPLAY", "appVersion": "4.0.4.1", "version": "35",
        "appTime": str(int(time.time() * 1000)), "isVip": "false", "uId": "", "functionTag": "texttovideo",
    }
    t0 = time.perf_counter()
    r = s.post(BASE + "v4/getUuid", data=form, timeout=20)
    ms = (time.perf_counter() - t0) * 1000
    j = r.json()
    other = j.get("other") or {}
    return {
        "http": r.status_code,
        "ms": round(ms, 1),
        "bucket": other.get("bucketName"),
        "region": other.get("region"),
        "dir": other.get("dir"),
        "has_creds": bool(other.get("accessKey") and other.get("secretKey")),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=16)
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()

    pid = Path(__file__).resolve().parent.parent.joinpath("last_pid.txt")
    if pid.exists():
        point_id = pid.read_text().strip()
    else:
        c = PointsClient()
        point_id = json.loads(c.post("point/user/getNewUserPointInfo.htm?osType=1")["plain"])["pointId"]

    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "target": BASE, "conc": args.conc, "n": args.n}
    report["s3_creds"] = s3_creds_probe()
    report["get_uuid"] = run("v4/getUuid", get_uuid_once, args.conc, args.n)
    report["points_newuser"] = run("points/getNewUserPointInfo", points_newuser_once, min(args.conc, 8), args.n // 2)
    report["submit"] = run("v3/texttovideonew (submit)", submit_once, min(args.conc, 8), args.n // 4, point_id)
    # 单 key 轮询矩阵（用 submit 的最后一把 key 不现实，这里用一次性提交取 key）
    dev = Device(android_id="pollprobe0000001")
    dev.refresh_uuid()
    r = dev.submit_frames("v3/texttovideonew", {"prompt": "poll", "aspect_ratio": "9:16"},
                          {"platFormId": "", "pointId": point_id, "consumeType": "92"})
    if r.get("data"):
        report["poll"] = run("v4/downLoad/{key}", poll_once, min(args.conc, 16), args.n, r["data"])

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写出:", OUT)


if __name__ == "__main__":
    main()
