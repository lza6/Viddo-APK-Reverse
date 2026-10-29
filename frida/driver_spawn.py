"""Frida spawn 版：从进程启动就挂钩，抓首次初始化与生成请求。"""
import sys
import time
from pathlib import Path

import frida

PKG = "saver.ins.fb.twitter.storydownloader"
HOST = "127.0.0.1:27042"
HERE = Path(__file__).resolve().parent
LOG = HERE / "hook_spawn.log"


def on_message(msg, data=None):
    if msg.get("type") == "send":
        line = msg.get("payload")
    elif msg.get("type") == "error":
        line = "ERR " + str(msg.get("stack") or msg.get("description"))
    else:
        line = str(msg)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {line}\n")


def main() -> None:
    dev = frida.get_device_manager().add_remote_device(HOST)
    pid = dev.spawn([PKG])
    print(f"[driver] spawned pid={pid}", flush=True)
    session = dev.attach(pid)
    script = session.create_script((HERE / "hook3.js").read_text(encoding="utf-8"))
    script.on("message", on_message)
    script.set_log_handler(lambda level, text: on_message({"type": "send", "payload": text}))
    script.load()
    dev.resume(pid)
    print("[driver] resumed, waiting…", flush=True)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
