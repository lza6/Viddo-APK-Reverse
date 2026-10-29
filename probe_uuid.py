"""Viddo v4.0.4.1 第一步链路验证：v4/getUuid"""
import time
import requests

BASE = "https://aicup-v2.magicutapp.com/"
PKG = "saver.ins.fb.twitter.storydownloader"
APP_ID = "YZ080"


def form(android_id: str, uid: str = "") -> dict:
    return {
        "appId": APP_ID,
        "uuId": "jrxc_" + android_id,
        "pkgName": PKG,
        "lang": "en_US",
        "country": "US",
        "channelName": "GOOGLEPLAY",
        "appVersion": "4.0.4.1",
        "version": "35",
        "appTime": str(int(time.time() * 1000)),
        "isVip": "false",
        "uId": uid,
    }


def probe(android_id: str):
    url = BASE + "v4/getUuid"
    payload = form(android_id)
    print("POST", url)
    print("form:", payload)
    t0 = time.time()
    r = requests.post(url, data=payload, timeout=25)
    ms = int((time.time() - t0) * 1000)
    print(f"[{r.status_code}] {ms}ms ct={r.headers.get('content-type')}")
    print("body:", r.text[:2000])
    return r


if __name__ == "__main__":
    probe("0f1e2d3c4b5a6978")
