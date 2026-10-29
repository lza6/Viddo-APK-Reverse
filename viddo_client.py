"""Viddo v4.0.4.1 protocol client (round-1 reverse engineering).

协议要点（静态还原 + 实测）：
  base      = https://aicup-v2.magicutapp.com/
  appId     = YZ080, channel = GOOGLEPLAY, pkg = saver.ins.fb.twitter.storydownloader
  设备身份  = uuId = "jrxc_" + android_id
  会话 UUID = POST v4/getUuid (form)  -> data
  签名      = md5(pkgName + uId + appTime)  (小写 hex)
  decrypt   = base64(RSA/ECB/PKCS1Padding( json_content )) 去掉换行
  content   = 明文 params JSON
  任务      = POST v3/<action> multipart(decrypt, sign, content[, imagefile])
  轮询      = POST v4/downLoad/<key>  (无 body)
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

BASE = "https://aicup-v2.magicutapp.com/"
APP_ID = "YZ080"
PKG = "saver.ins.fb.twitter.storydownloader"
CHANNEL = "GOOGLEPLAY"
APP_VERSION = "4.0.4.1"
VERSION_CODE = "35"

RSA_PUB_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC89/6HolP425cyY2E0A9l8P05WFLywJd1xm8V4bbysY++"
    "/UyRxndOhq6jbn9uo8uO5vHCnFE6xVyKSSjxD19491QryKTJT7K78qckPyprrPb6L9lwQFXUjw8OWqR65Elj"
    "3anx22PVm6wfEbVzfIj/tnGdYrtAzXJPaiY1izlzPhQIDAQAB"
)

# AiFunAction -> (endpoint, action alias)  见 com.energysh.aiservice.api.AiFunAction
ACTIONS = {
    "texttovideo": ("v3/texttovideonew", "TextToVideo"),
    "texttovideo2": ("v3/texttovideonew", "TextToVideo2"),
    "imagetovideo": ("v3/texttovideonew", "ImageToVideo2"),
    "videoextend": ("v3/videoextend", "TextToVideoExtend"),
    "videofaceswap": ("v3/videofaceswap", "VideoSwapFace"),
}


def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def rsa_encrypt(plain: str) -> str:
    """RSA/ECB/PKCS1Padding，分块 117 字节（与 j2.h.a 一致），自定义 Base64 去换行。"""
    key = RSA.import_key(base64.b64decode(RSA_PUB_B64))
    cipher = PKCS1_v1_5.new(key)
    raw = plain.encode("utf-8")
    out = b""
    for i in range(0, len(raw), 117):
        chunk = raw[i : i + 117]
        out += cipher.encrypt(chunk)
    return base64.b64encode(out).decode("ascii").replace("\n", "")


@dataclass
class Device:
    """一台虚拟设备。uuId 只由 android_id 决定，可无限扩号。"""

    android_id: str
    is_vip: bool = False
    lang: str = "en_US"
    country: str = "US"
    u_id: str = ""          # 服务端下发的会话 UUID（v4/getUuid）
    uuid_at: float = 0.0
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        # 环境里 HTTP(S)_PROXY 指向一个不可用的本地端口，直连更快更稳。
        self.session.trust_env = False

    @property
    def uuid_header(self) -> str:
        return "jrxc_" + self.android_id

    @property
    def priority(self) -> str:
        return "99" if self.is_vip else "50"

    def base_form(self) -> dict:
        return {
            "appId": APP_ID,
            "uuId": self.uuid_header,
            "pkgName": PKG,
            "lang": self.lang,
            "country": self.country,
            "channelName": CHANNEL,
            "appVersion": APP_VERSION,
            "version": VERSION_CODE,
            "appTime": str(int(time.time() * 1000)),
            "isVip": "true" if self.is_vip else "false",
            "uId": self.u_id,
        }

    def _post(self, url: str, tries: int = 5, **kw):
        """上游偶发 TLS EOF，做有限次重试。"""
        last = None
        for _ in range(tries):
            try:
                return self.session.post(url, **kw)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as exc:
                last = exc
                time.sleep(1.5)
        raise last  # type: ignore[misc]

    # ---------- v4/getUuid ----------
    def refresh_uuid(self, timeout: int = 20) -> str:
        r = self._post(BASE + "v4/getUuid", data=self.base_form(), timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if not j.get("success"):
            raise RuntimeError(f"getUuid failed: {j}")
        self.u_id = j.get("data") or ""
        self.uuid_at = time.time()
        return self.u_id

    def ensure_uuid(self, ttl: int = 840) -> str:
        if not self.u_id or time.time() - self.uuid_at > ttl:
            return self.refresh_uuid()
        return self.u_id

    # ---------- 签名 + 加密 ----------
    def signed_payload(self, extra: dict, action_alias: str = "TextToVideo") -> tuple[str, str]:
        self.ensure_uuid()
        app_time = str(int(time.time() * 1000))
        body = {
            "appTime": app_time,
            "priority": self.priority,
            "uId": self.u_id,
            "pkgName": PKG,
            **extra,
        }
        sign = md5_hex(PKG + self.u_id + app_time)
        return rsa_encrypt(json.dumps(body, ensure_ascii=False, separators=(",", ":"))), sign

    # ---------- 提交任务 ----------
    def submit_frames(
        self,
        endpoint: str,
        content: dict,
        extra_signed: dict,
        images: list[tuple[str, bytes]] | None = None,
        timeout: int = 60,
    ) -> dict:
        decrypt, sign = self.signed_payload(extra_signed)
        parts: list[tuple[str, tuple]] = []
        for name, blob in images or []:
            fname = f"{int(time.time() * 1000)}_image.jpg"
            parts.append(("imageFileName", (None, fname)))
            parts.append(("imagefile", (fname, blob, "app/octet-stream")))
        files = list(parts)
        files.append(("decrypt", (None, decrypt)))
        files.append(("sign", (None, sign)))
        files.append(("content", (None, json.dumps(content, ensure_ascii=False))))
        form = self.base_form()
        form.pop("uId", None)
        r = self._post(BASE + endpoint, data=form, files=files, timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {"http": r.status_code, "raw": r.text[:500]}

    # ---------- 轮询 ----------
    def poll(self, key: str, timeout: int = 20) -> dict:
        r = self._post(BASE + "v4/downLoad/" + key, timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {"http": r.status_code, "raw": r.text[:500]}


if __name__ == "__main__":
    dev = Device(android_id="0f1e2d3c4b5a6978")
    print("uuid:", dev.refresh_uuid())
    print("priority:", dev.priority)
    dec, sig = dev.signed_payload({"pointId": "", "consumeType": "1"})
    print("sign:", sig)
    print("decrypt len:", len(dec))
