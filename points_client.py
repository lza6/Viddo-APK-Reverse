"""videoshowapp points/zone API 客户端（3DES/ECB/PKCS5）。

密钥派生见 u2.b.a(NetExecutor.CURRENT_PUBLIC_KEY, 3, "UTF-8")：
  base64("532311sdf") -> "NTMyMzExc2Rm" -> 补 X 到 24 字节。
"""
from __future__ import annotations

import base64
import json
import random
import time
import uuid

import requests
from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad

PUBLIC_KEY = "532311sdf"
HOST = "https://apis.videoshowapp.com/zone/1.0.1"
PKG = "saver.ins.fb.twitter.storydownloader"
APP_VERSION = "4.0.4.1"
CHANNEL = "GOOGLEPLAY"


def des3_key() -> bytes:
    b64 = base64.b64encode(PUBLIC_KEY.encode()).decode()
    if len(b64) < 24:
        b64 = b64 + "X" * (24 - len(b64))
    elif len(b64) > 24:
        b64 = b64[:12] + b64[-12:]
    return b64.encode()


def des3_encrypt(text: str) -> bytes:
    cipher = DES3.new(des3_key(), DES3.MODE_ECB)
    return cipher.encrypt(pad(text.encode(), 8))


def des3_decrypt(blob: bytes) -> str:
    from Crypto.Util.Padding import unpad

    cipher = DES3.new(des3_key(), DES3.MODE_ECB)
    return unpad(cipher.decrypt(blob), 8).decode()


class PointsClient:
    def __init__(self, android_id: str | None = None, model: str = "Pixel 7", brand: str = "google"):
        self.android_id = android_id or uuid.uuid4().hex[:16]
        self.model = model
        self.brand = brand
        self.session = requests.Session()
        self.session.trust_env = False

    # --- 标识 ---
    @property
    def uu_id(self) -> str:
        return "jrxc_" + self.android_id

    @property
    def device_uuid(self) -> str:
        return self.android_id

    def base_map(self) -> dict:
        return {
            "deviceUuid": self.device_uuid,
            "uuId": self.uu_id,
            "userId": "",
            "pkgName": PKG,
            "lang": "en",
            "versionName": APP_VERSION,
            "channelName": CHANNEL,
            "requestId": f"{time.time_ns()}{random.randint(0, 9999)}",
        }

    def post(self, path: str, extra: dict | None = None, timeout: int = 25) -> dict:
        payload = self.base_map()
        if extra:
            payload.update(extra)
        body = des3_encrypt(json.dumps(payload, separators=(",", ":")))
        headers = {
            "x-uuid": self.uu_id,
            "x-deviceuuid": self.device_uuid,
            "x-userid": "",
            "x-openid": "",
            "x-appinfo": f"{CHANNEL}/{PKG}/{APP_VERSION}/1/{self.model}/{self.brand}",
            "Content-Type": "application/wxt;charset=UTF-8",
        }
        url = f"{HOST}/{path}"
        r = self.session.post(url, data=body, headers=headers, timeout=timeout)
        raw = r.content
        out = {"http": r.status_code}
        try:
            out["plain"] = raw.decode("utf-8", "replace")
        except Exception:
            out["plain"] = ""
        try:
            out["decrypted"] = des3_decrypt(raw)
        except Exception:
            out["decrypted"] = None
        return out


if __name__ == "__main__":
    c = PointsClient()
    for path in [
        "/point/consume/getConsumePointConfig.htm?osType=1",
        "/point/user/getPointBalanceInfo.htm?osType=1",
        "/clientDevice/getServerParamInfo.html?osType=1",
    ]:
        res = c.post(path)
        print("=== ", path)
        print(json.dumps(res, ensure_ascii=False)[:1200])
