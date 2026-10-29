# Viddo v4.0.4.1 (Pro) — APK 逆向 R1

> 目标：`saver.ins.fb.twitter.storydownloader` v4.0.4.1（品牌 **Viddo**，厂商 energysh）
> 产出：协议还原 + 本地上游客户端 + 网关 + demo 页 + 第一轮压测
> 结论：**协议全通，生成执行被服务端配置闸门阻断**（详见 `docs/PROTOCOL.md` §5）

---

## 状态表

| 项 | 状态 | 证据 |
|---|---|---|
| APK 解包 / 版本 / 组件测绘 | ✅ | `docs/REVERSE_REPORT.md` §1 |
| Flutter AOT 反编译（Dart 3.4.3） | ✅ | `blutter_out/asm/quickart/**` |
| Java 反编译 | ✅ | `jadx_out/`（14 处失败已用 `--show-bad-code` 补齐） |
| L2 AI 服务端点表 | ✅ 静态+实测 | 2 个功能启用，其余 `400 该功能未启用` |
| RSA / MD5 签名 / multipart 格式 | ✅ 已验证 | 提交返回受理 key |
| L1 3DES 信封 + 积分体系 | ✅ 已验证 | 建号/配置/领点/余额全通 |
| S3 临时凭证签发行为 | ✅ 已验证（脱敏记录） | `GET /api/s3creds` |
| 任务真实出片 | ❌ 阻断 | 轮询 `1404/1405`，需 R2 抓包 |
| 第一轮压测 | ✅ | `stress/stress_round1.json` |

---

## 目录

```
viddo404/
├ viddo_client.py          # L2 AI 服务客户端（身份/RSA/签名/提交/轮询）
├ points_client.py         # L1 积分服务客户端（3DES 信封）
├ gateway/server.py        # 本地网关 :8971（标准库，无框架依赖）
├ demo/index.html          # 交互式 demo（真实打上游）
├ stress/stress_r1.py      # 第一轮压测
├ probe_uuid.py            # 最小连通性探测
├ probe_consumetypes.py    # consumeType 穷举探测
├ docs/PROTOCOL.md         # ★ 协议手册（实现用）
├ docs/REVERSE_REPORT.md   # 逆向与压测报告（含安全发现）
├ docs/NEWAPI_INTEGRATION.md # 若后续打通，接入 new-api 的方案
└ apktool_out/ jadx_out/ blutter_out/   # 反编译产物（体积大，不入库）
```

## 运行

依赖：Python 3.10+、`requests`、`pycryptodome`。

```powershell
cd D:\apk-analysis\viddo404

# 1. 最小连通性 + 签名样例
python viddo_client.py

# 2. 积分链路自检
python points_client.py

# 3. 网关 + demo
python gateway\server.py
#   浏览器打开 http://127.0.0.1:8971

# 4. 压测（温和规模）
python stress\stress_r1.py --conc 16 --n 200
```

> 注意：本机 `HTTP(S)_PROXY` 指向的本地端口不可用，所有客户端已设 `Session.trust_env=False` 直连。

## 一键自检（curl）

```powershell
curl http://127.0.0.1:8971/api/health
curl -X POST http://127.0.0.1:8971/api/identity -H 'content-type: application/json' -d '{\"android_id\":\"demo00000000001\"}'
curl "http://127.0.0.1:8971/api/s3creds?tag=texttovideo"
curl -X POST http://127.0.0.1:8971/api/task -H 'content-type: application/json' -d '{\"prompt\":\"a cat\",\"consume_type\":\"92\",\"point_id\":\"<pointId>\"}'
```

---

## 关键结论（一句话版）

提交协议（RSA 参数加密 + md5 签名 + multipart）已被完整复现且上游受理；
真正拦路的是服务端"共用表"要求 `(consumeType, platFormId)` 必须是真实配置行——
App 自身积分表 70 个 consumeType、数字空间 1..160、全部 consumeId 均已穷举排除，
只能靠 R2 在真机/模拟器里抓一次 UI 真实生成请求来定案。

详见 `docs/PROTOCOL.md` §5「阻断点」。

---

## 脱敏

- 上游 S3 临时凭证（AK/SK）在网关层与文档中一律脱敏，只保留"是否签发"。
- 保留的常量（3DES key、RSA 公钥、appId）均来自 APK 静态常量，可现场复算验证，不属于泄露第三方机密。
