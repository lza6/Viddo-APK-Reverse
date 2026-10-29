# Viddo → new-api 对接指南（R1/R2 实测版）

> 目标读者：负责在 new-api 里落地这个渠道的工程会话
> 上游：`saver.ins.fb.twitter.storydownloader` v4.0.4.1（品牌 Viddo，厂商 energysh）
> 状态：**协议已全部还原并用真实请求验证；生成执行被上游「共用表」阻断，当前不能上线**
>
> 请先读第 0 节，再决定是否动工。第 1~4 节是可直接照抄的实现规格。

---

## 0. 现在能不能接？——不能，原因精确到字段

| 环节 | 实测结果 | 能否替代/绕过 |
|---|---|---|
| 造号（`v4/getUuid`） | ✅ 零鉴权，200/200 成功，无速率限制 | — |
| 参数加密 + 签名 | ✅ 完全还原，上游照收 | — |
| 任务提交 `v3/texttovideonew` | ✅ 100% 返回 task key | — |
| 任务执行 | ❌ 轮询立刻 `1403/1404/1405` | **不能**：闸门在服务端 DB（`appId=YZ080` 的共用表没有该功能行） |
| 真实客户端能否生成 | ❌ 点 Create 本地弹 `Token Error`，零出网 | **不能**（见 `docs/R2_CAPTURE.md`） |

即：**下单成功、取不到货，且官方客户端自己也取不到货**。
在拿到能跑通的一次真实生成之前，任何渠道实现都会 100% 返回失败——不要写。

一旦你（或后续会话）拿到了可用的一组 `(consumeType, platFormId)`，按下面第 1~5 节直接实现即可，无需再逆向。

---

## 1. 上游接口规格（照抄即可）

### 1.1 常量

```go
const (
    BaseURL     = "https://aicup-v2.magicutapp.com/"
    AppID       = "YZ080"
    PkgName     = "saver.ins.fb.twitter.storydownloader"
    ChannelName = "GOOGLEPLAY"
    AppVersion  = "4.0.4.1"
    VersionCode = "35"
    // RSA 公钥（PKCS#1 v1.5，2048bit，客户端常量，非机密）
    RSAPubKey = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC89/6HolP425cyY2E0A9l8P05WFLywJd1xm8V4bbysY++/UyRxndOhq6jbn9uo8uO5vHCnFE6xVyKSSjxD19491QryKTJT7K78qckPyprrPb6L9lwQFXUjw8OWqR65Elj3anx22PVm6wfEbVzfIj/tnGdYrtAzXJPaiY1izlzPhQIDAQAB"
)
```

### 1.2 设备身份

| 字段 | 规则 |
|---|---|
| `uuId`（header/表单） | `"jrxc_" + android_id`，android_id 任意 16 位 hex → **可无限造号** |
| `uId`（会话 token） | `POST v4/getUuid` 返回的 `data`；有效期约 15 分钟（客户端按 900000ms 缓存） |
| `isVip` | `"true"` / `"false"`；影响 `priority`（`99` / `50`） |

### 1.3 步骤 ①：取会话 token

```http
POST https://aicup-v2.magicutapp.com/v4/getUuid
Content-Type: application/x-www-form-urlencoded

appId=YZ080&uuId=jrxc_<android_id>&pkgName=saver.ins.fb.twitter.storydownloader
&lang=en_US&country=US&channelName=GOOGLEPLAY&appVersion=4.0.4.1&version=35
&appTime=<ms>&isVip=false&uId=
```

响应：

```json
{"success":true,"code":0,"data":"<uuid>","message":"success","currentTime":1793308773198,"other":null,"process":0}
```

> 附带能力（仅记录，不建议使用）：追加 `functionTag=texttovideo` 时，`other` 会下发
> AWS S3 临时凭证（`bucketName/accessKey/secretKey/region/dir`）。**不要做超出图片上传的用途。**

### 1.4 步骤 ②：签名 + 加密

```
appTime = 当前毫秒字符串
priority = isVip ? "99" : "50"
sign     = md5_hex(pkgName + uId + appTime)          // 小写 hex，32 字符
payload  = json({
    "appTime":  appTime,
    "priority": priority,
    "uId":      uId,
    "pkgName":  pkgName,
    "platFormId": <平台名，如 "tencent">,     // ← 需真实值
    "pointId":    <积分用户 id>,              // ← 见 §1.6
    "consumeType":<消耗类型，如 "92">         // ← 需真实值
})
decrypt  = base64( RSA_PKCS1v15(payload) )    // 明文按 117 字节分块加密后拼接，base64 去换行
```

### 1.5 步骤 ③：提交任务（multipart）

```http
POST https://aicup-v2.magicutapp.com/v3/texttovideonew
Content-Type: multipart/form-data

# 表单字段（与 §1.3 相同的一组）
appId, uuId, pkgName, lang, country, channelName, appVersion, version, appTime, isVip
# 三个核心 part
decrypt = <上面算出的密文>
sign    = <上面算出的签名>
content = {"prompt":"a cat walking on grass","aspect_ratio":"9:16"}   # 明文 JSON
# 图生视频才需要
imageFileName = "<ms>_image.jpg"
imagefile     = <JPEG 二进制，媒体类型 app/octet-stream>
```

响应（受理即返回 key）：

```json
{"success":true,"code":0,"data":"MCKT1581a626706e49a2ba6dee3d555c85b5_texttovideonew","message":"success","process":0}
```

`content` 明文结构（按功能不同）：

| 功能 | content 键 |
|---|---|
| 纯文生视频 | `prompt`, `aspect_ratio`（可选 `style` 里的其它键） |
| 图生视频 | `aspect_ratio` 或 `width`/`height`, `platFormId`, `imagefile`, 以及 style JSON 的键 |
| 视频续写 | `aspect_ratio`, `video_id`, style JSON 的键 |

### 1.6 步骤 ④：轮询

```http
POST https://aicup-v2.magicutapp.com/v4/downLoad/<key>
```

无 body、无鉴权。响应字段：`code / data / message / process / currentTime`，
`process` 是进度，`data` 是结果（多结果时形如 `[{...}]`，可取 `imageData` / `maskData`）。

### 1.7 积分用户（拿 pointId，可选自动化）

上游积分在另一套域名（3DES 信封）：

```
key  = base64("532311sdf") 补齐 'X' 到 24 字节
body = DESede/ECB/PKCS5( json(params) )
Header: x-uuid / x-deviceuuid / x-userid / x-openid / x-appinfo
        x-appinfo = "GOOGLEPLAY/<pkg>/4.0.4.1/1/<MODEL>/<BRAND>"
Content-Type: application/wxt;charset=UTF-8
```

| 用途 | 路径（相对 `https://apis.videoshowapp.com/zone/1.0.1/`） | 参数 |
|---|---|---|
| 建积分用户 | `point/user/getNewUserPointInfo.htm?osType=1` | — → 返回 `pointId` |
| 查余额 | `point/user/getPointBalanceInfo.htm?osType=1` | `pointId` |
| 消耗配置 | `point/consume/getConsumePointConfig.htm?osType=1` | `pointId` |
| 任务奖励表 | `point/task/getTaskUserPointConfig.htm?osType=1` | `pointId` |
| 领任务奖励 | `point/task/doAddTaskPoint.htm?osType=1` | `pointId`, `taskId` |

> 已实测：`taskId=1`(每日登录 +20)、`56`(7日签到首日 +20)、`60`/`61`/`62`(+5)、`193`(激励广告 +2) 均可直接领取，单设备首日 ≈ 57 点。
> **注意**：新用户注册按 IP 限流（实测 6/100 成功，之后固定 `{"retCode":0,"retMsg":"device limit"}`）。

---

## 2. 生成前必须补齐的两个参数（唯一的硬门槛）

| 参数 | 语义 | 已知信息 |
|---|---|---|
| `consumeType` | 积分消耗项编号 | App 积分表里 `functionTag=texttovideonew` 有 70 个（30~140 点档位，含多个 0 点免费档），但**全部被上游判为"功能不存在"** |
| `platFormId` | 平台名（字符串） | `tencent` / `volcengine` 可被服务端解析（不抛异常）；其余平台名与纯数字一律 `500 ApiPlatform is null` |

已穷举排除（不要重复）：
`70 个 consumeType` × `{tencent, volcengine}` 二维扫描 140 次、数字 `1..160`、
全部 `consumeId`（459~2592）、`functionTag`/`type`/`check`/`uuId` 附加字段、
`function_configs`+`isVip`+`point_id` 组合参数 —— **全部返回 1405**。

取得真实值的唯一途径：见 `docs/R2_CAPTURE.md` §5（换原版 APK 抓一次成功生成）。

---

## 3. new-api 侧实现建议（拿到参数后再动工）

### 3.1 渠道形态

属于 **task 类视频渠道**（与 AIVM / AI Cartoon Pet 同族），不建议做成 chat 渠道。

| new-api 入口 | 上游动作 |
|---|---|
| `POST /v1/video/generations` | §1.3 取 token → §1.4 签名 → §1.5 提交 → 返回 `task_id = key` |
| 轮询（任务查询） | `POST v4/downLoad/<key>`，把上游 `process` 映射为进度，`data` 映射为视频 URL |
| `GET /v1/video/generations/{id}` | 同上 |

### 3.2 模型名 → 上游参数映射（建议）

```
viddo-t2v-tencent      -> { endpoint: v3/texttovideonew, platFormId: "tencent",    consumeType: <待填> }
viddo-t2v-volc         -> { endpoint: v3/texttovideonew, platFormId: "volcengine", consumeType: <待填> }
viddo-extend           -> { endpoint: v3/videoextend,    platFormId: "tencent",    consumeType: <待填> }
```

### 3.3 计费映射建议

上游按**点数**计价，且点数有有效期（`pointExpiresDay` 1~2 天），换算必须把过期损耗算进去：

| 档位 | 上游点数 | 建议 |
|---|---|---|
| 0 点（Vidu/VEO/AceSora/MiniMax/pixverse/seeddance） | 0 | 引流档，低价或免费 |
| 30 点（腾讯 / ComfyUI / nano+pix） | 30 | 基准档 |
| 40~50 点 | 40 / 50 | 中档 |
| 60~140 点（seedance 5s/10s/15s） | 60 / 100 / 140 | 按时长分档 |

### 3.4 错误码映射（务必照此转，避免把上游闸门当用户错误）

| 上游 code | 上游语义 | new-api 建议动作 |
|---|---|---|
| 0 | 受理 / 进行中 | 正常 |
| 400 | 该功能未启用 | 渠道配置错误 → 渠道置灰，告警 |
| 403 / 404 / 409 | 权限 / 资源 / 冲突 | 通用上游错误 |
| 1402 / 1403 | 积分参数有误 / 共用表未配置 | **运维配置缺失**：不重试，渠道标记不可用并告警 |
| 1404 | 积分系统用户不存在 | `pointId` 失效 → 重新建号后重试一次 |
| 1405 | 积分系统功能不存在 | **运维配置缺失**（当前就是这个）：不重试，渠道标记不可用 |
| 429 / 541xx | 上游限流 | 退避重试 |
| 500 `ApiPlatform ... null` | `platFormId` 非法 | 配置错误，不重试 |

### 3.5 运维参数

| 项 | 建议 |
|---|---|
| android_id 池 | 每设备一套 `uuId/uId/pointId`；建议池化并复用，勿高频新建（积分侧有 IP 限流） |
| uId 缓存 | 15 分钟；过期前主动刷新，避免任务提交时 401/1404 |
| 积分维护 | 后台定时用 `doAddTaskPoint` 补点（注意这是上游漏洞，仅作可用性兜底，别做规模套利） |
| 任务 key | 轮询端点**无鉴权**，网关必须维护 key↔用户映射，禁止把 key 直接回给终端用户 |
| 超时 | 实测提交 p50 ≈ 2.1s（跨洋），建议 connect 10s / read 30s，轮询间隔 4~5s |

---

## 4. 端到端验收清单（打通的最低标准）

1. `v4/getUuid` 返回 UUID；`AI-Service` 侧 uId 正常
2. 提交 `v3/texttovideonew` 返回 `data` 以 `_texttovideonew` 结尾
3. 轮询 `code=0` 且 `process` **从 0 递增**（这一步不递增就说明闸门没开，别再往下做）
4. 轮询最终返回可下载的视频 URL，实际下载可播放
5. new-api 里跑真实用户路径：下单 → 任务 → 出片 → 计费四条链路都通
6. 计费与实际点数一致（含 0 点免费档不扣费）

> 第 3 步是分水岭：**提交受理 ≠ 能出片**。R1 卡在这一步。

---

## 5. 风险与合规

- 该 App 是第三方商业产品（含内购/订阅）；渠道上线前需业务侧确认授权与合规边界。
- 上游 AI 服务零鉴权、可无限造号，属上游设计缺陷；**我们只做必要调用，不做批量养号/套利**。
- S3 临时凭证签发是上游缺陷，仅用于图片上传，不列举、不遍历 bucket。
- 积分任务可直接空领是上游漏洞：只用于小规模可用性兜底。
- 广告/内购/激励视频相关能力**不得**接入（涉及上游变现与第三方广告网络）。

---

## 6. 附：现成可用的代码

| 文件 | 说明 |
|---|---|
| `viddo_client.py` | 上面 §1.3~§1.6 的完整实现（Device 类：refresh_uuid / signed_payload / submit_frames / poll） |
| `points_client.py` | §1.7 的 3DES 客户端（PointsClient：post / 建号 / 配置 / 领点） |
| `gateway/server.py` | 本地网关参考实现（含 S3 凭证脱敏） |
| `demo/index.html` | 交互式验证页 |

Go 侧实现时注意两点：
1. RSA 必须**分块 117 字节**（`PKCS1v15`），一次加密长 JSON 会失败；
2. Base64 结果要去掉所有换行。
