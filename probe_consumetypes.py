"""遍历 consumeType，找出 AI 后端"共用表"里真实存在的功能项。"""
import json
import time

from points_client import PointsClient
from viddo_client import BASE, Device

PID = open("last_pid.txt").read().strip()
PKG_FALLBACK = "saver.ins.fb.twitter.storydownloader"


def consume_list(pid: str) -> list[dict]:
    c = PointsClient()
    for _ in range(5):
        try:
            r = c.post("point/consume/getConsumePointConfig.htm?osType=1", {"pointId": pid})
            return json.loads(r["plain"]).get("consumeList", [])
        except Exception:
            time.sleep(2)
    return []


def message(raw: bytes) -> str:
    i = raw.find(b'"message":"')
    if i < 0:
        return ""
    return raw[i + 11 : i + 200].decode("utf-8", "replace").split('"')[0]


def main() -> None:
    items = [x for x in consume_list(PID) if x.get("functionTag") == "texttovideonew"]
    items.sort(key=lambda x: (x.get("pointNumber") or 0))
    print(f"候选 consumeType: {len(items)}（余额可用: 见前置脚本）")
    dev = Device(android_id="0f1e2d3c4b5a6978")
    dev.refresh_uuid()
    for it in items:
        ct = it["consumeType"]
        r = dev.submit_frames(
            "v3/texttovideonew",
            {"prompt": "a cat walking on grass", "aspect_ratio": "9:16"},
            {"platFormId": "", "pointId": PID, "consumeType": ct},
        )
        key = r.get("data")
        if not key:
            print(f"{ct:>14} {it.get('pointNumber')}pt submit-fail {str(r)[:120]}")
            continue
        raw = dev.session.post(BASE + "v4/downLoad/" + key, timeout=20).content
        try:
            j = json.loads(raw.decode())
        except Exception:
            j = {}
        print(f"{ct:>14} {it.get('pointNumber'):>3}pt code={j.get('code')} {message(raw)}")
        if j.get("code") not in (1405, 1403):
            print("  >>> 命中! 保留 key:", key)
            open("hit_consumetype.txt", "w").write(json.dumps({"consumeType": ct, "key": key, "info": it}, ensure_ascii=False))
            break
        time.sleep(0.5)


if __name__ == "__main__":
    main()
