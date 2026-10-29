"""Frida 驱动：附加到 Viddo，加载 hook.js，把日志落盘。"""
import sys
import time
from pathlib import Path

import frida

PKG = "saver.ins.fb.twitter.storydownloader"
HOST = "127.0.0.1:27042"
LOG = Path(__file__).with_name("hook_out.log")


def on_message(msg, data):
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
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else dev.get_process(PKG).pid
    print(f"[driver] attach pid={pid}", flush=True)
    session = dev.attach(pid)
    script = session.create_script(Path(__file__).with_name("hook2.js").read_text(encoding="utf-8"))
    script.on("message", on_message)
    # console.log -> message
    script.set_log_handler(lambda level, text: on_message({"type": "send", "payload": text}, None))
    script.load()
    print("[driver] hooked, waiting… (Ctrl+C 结束)", flush=True)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
