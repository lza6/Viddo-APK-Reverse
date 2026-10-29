# Viddo v4.0.4.1 (Pro) — 协议还原手册（R1）

> 目标 APK：`Viddo v4.0.4.1 (Pro).apk`
> md5 `b2d5bc6227e34b33fe45e5867c4efd04` · 129,077,925 B
> 包名 `saver.ins.fb.twitter.storydownloader` · versionName `4.0.4.1` · versionCode `35`
> minSdk 28 / targetSdk 35 · 仅 arm64-v8a · Flutter（Dart 3.4.3, snapshot `d20a1be77c3d3c41b2a5accaee1ce549`）
> 厂商：`energysh`（视频编辑产品线，Dart 命名空间 `com.energysh.quickart`，品牌 "Viddo"）

标注约定：**已验证** = 实际发请求观测；**静态确认** = 反编译阅读确认；**合理推断** = 有间接证据；**待验证** = 缺条件。

---

## 1. 域名与两套 API

| 层 | Base | 用途 | 鉴权 |
|----|------|------|------|
| L2 AI 服务 | `https://aicup-v2.magicutapp.com/` | 生成任务：提交/轮询/bucket 凭证 | 无会话鉴权，仅 `appId`+设备 UUID+签名 |
| L1 积分/支付 | `https://apis.videoshowapp.com/zone/1.0.1` | 积分用户、消耗配置、任务奖励、商品、Google 支付核销 | 3DES 信封 + `x-*` 头 |
| L1 素材/模板 | `https://camera.magicutapp.com/` | 主题包/素材/首页 tab | 明文 GET/POST（参数含 androidid） |
| L1 配置 | `https://api.videoshowapp.com/` | `videoshow/api/v2/config`（**当前 500**） | 明文 GET |
| L1 运营页 | `https://manage.magicutapp.com/appMagicCutApi/customizepage` | 隐私政策/服务条款 H5 | 明文 |
| 统计 | `https://analytics.enjoymobiserver.com/vsAnalytics/1.0.1` | 埋点 | 明文 |

L1 全部由 `com.energysh.points` / `com.energysh.net` / `c3.*` / `e3.*` 发出；L2 由 **`com.energysh.aiservice`** SDK 发出（该 SDK 被同厂 App 共用）。

### L2 初始化参数（静态确认，`com.energysh.quickart.server.ai.AIServiceSdk`）

```
appId      = "YZ080"
baseUrl    = "https://aicup-v2.magicutapp.com/"
channelName= "GOOGLEPLAY"
publicKey  = MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC89/6HolP425cyY2E0A9l8P05WFLywJd1xm8V4bbysY++/UyRxndOhq6jbn9uo8uO5vHCnFE6xVyKSSjxD19491QryKTJT7K78qckPyprrPb6L9lwQFXUjw8OWqR65Elj3anx22PVm6wfEbVzfIj/tnGdYrtAzXJPaiY1izlzPhQIDAQAB
```

---

## 2. L2 AI 服务

### 2.1 端点表（静态确认：`com.energysh.aiservice.api` + 全 smali 常量扫描）

| 端点 | 方法 | 说明 | 实测状态 |
|------|------|------|----------|
| `v4/getUuid` | POST form | 取会话 UUID；带 `functionTag` 时**额外下发 AWS S3 临时凭证** | **已验证 200** |
| `v4/getUuid`(functionTag=texttovideo) | POST form | 返回 `other` = `{bucketName, baseUrl, accessKey, secretKey, region, dir}` | **已验证 200** |
| `v3/texttovideonew` | POST multipart | 文生视频 / 图生视频 / 视频续写（共享端点） | **已验证受理**，执行被服务端拦（见 §5） |
| `v3/videoextend` | POST multipart | 视频延长 | 受理，执行被拦 |
| `v4/downLoad/{key}` | POST 空 body | 任务结果/进度轮询 | **已验证 200** |
| `v1/upload` `v3/inpaintUpload` `v3/increase` `v3/replaceSky` `v3/changeAgePic` `v3/texttomusic` `v3/changeFaceVideo` `v3/videofaceswap` `v5/chatgpt` `v5/translation` `v5/transcriptions` `v4/ocr` `v1/animeAvatar` `v1/addColor` `v1/picFaceDriven` | — | 同 SDK 其他能力 | **已验证返回 400「该功能未启用」** |

> 该 App 的 AI 后端只启用了 `texttovideonew` 与 `videoextend` 两个功能，其余端点在本 appId 下未开通（已验证）。

### 2.2 设备身份

```dart
uuId = "jrxc_" + android_id          // j2.c.l()
uId  = POST v4/getUuid 返回的 data    // 服务端会话 UUID，缓存于 SP("AI-Service", baseUrl)
```

`v4/getUuid` 表单字段（静态确认 `d.d()`）：

```
appId, uuId, pkgName, lang, country, channelName, appVersion, version,
appTime(ms), isVip, uId[, functionTag]
```

**无任何签名/证书校验，任意 `android_id` 均可无限号**（已验证：200 次并发建号全 200）。

### 2.3 请求签名与加密

```
sign    = md5_hex(pkgName + uId + appTime)                       // j2.g.a
priority= isVip ? "99" : "50"
payload = json({appTime, priority, uId, pkgName, ...extra})       // extra 由具体 multipart 决定
decrypt = base64( RSA/ECB/PKCS1Padding(payload) ) 去换行           // j2.h.a 分块 117B
```

- RSA 公钥见 §1，2048 bit，**PKCS#1 v1.5**（`Cipher.getInstance("RSA/ECB/PKCS1Padding")`），按 117 字节分块后拼接。
- Base64 为 SDK 内自带实现（`j2.d.a`），字符表为标准 Base64，无换行；`n.z(...)` 再兜底去 `\n`。

### 2.4 任务提交（multipart）

`POST {base}v3/texttovideonew`，`Content-Type: multipart/form-data`：

| part | 内容 |
|------|------|
| `decrypt` | 上述 RSA 密文 |
| `sign` | 上述 md5 签名 |
| `content` | **明文** 参数 JSON（`paramsJson`） |
| `imageFileName` | `"<ms>_image.jpg"`（仅图生视频，JPEG 100 质量压缩后上传） |
| `imagefile` | 文件 part（媒体类型 `app/octet-stream`） |

表单里同时带 §2.2 的基础字段（`appId/uuId/pkgName/lang/country/channelName/appVersion/version/appTime/isVip`）。

`content` 明文键（静态确认 `ImageToVideo3MultipartImpl` / `c0` / `d0`）：

```
prompt 侧（纯文生视频 c0）:  style JSON 全部键 + aspect_ratio
图生视频:                     width/height 或 aspect_ratio + platFormId + style 全部键 + imagefile
视频续写 d0:                  aspect_ratio + style 全部键 + video_id
```

RSA payload 的 `extra`：

```
纯文生视频:  platFormId, pointId, consumeType
图生视频:    imagefile, platFormId, check, pointId, consumeType
```

### 2.5 轮询

```
POST {base}v4/downLoad/{key}     // 无 body，无鉴权（key 即可）
→ {success, code, data, message, currentTime, process}
```

`data` 处理规则（静态确认 `ServiceApis.i/k`）：`process` 为进度；`data` 为结果串（多结果时形如 `[{...}]`），`imageData`/`maskData` 从中取；`code != 0` 即失败。

### 2.6 错误码（客户端常量 `com.energysh.aiservice.api.b`）

对实际排查有用的几个：

| code | 服务端 message | 含义 |
|------|----------------|------|
| 0 | success | 正常（提交受理 / 轮询进行中） |
| 400 | 该功能未启用 | 该 appId 未开通此端点 |
| 403 / 404 / 409 | — | 权限/资源/冲突 |
| 1402 / 1403 | 积分系统参数有误或共用表未配置 | `pointId` 为空 |
| 1404 | 积分系统用户不存在 | `pointId` 合法但服务器不认识 |
| 1405 | 积分系统功能不存在 | `consumeType` 在共用表里查不到功能行 |
| 500 | Server internal exception `Cannot invoke "com.magicut.transfer.entity.ApiPlatform.getId()" because "apiPlatform" is null` | `platFormId` 非空但查不到平台记录 |

---

## 3. L1 积分/支付 API（3DES 信封）

### 3.1 加密（静态确认 `u2.b` / `u2.d` / `r2.a`）

```
key_raw = "532311sdf"                       // NetExecutor.CURRENT_PUBLIC_KEY
key_b64 = base64_nolinebreak(key_raw)        // "NTMyMzExc2Rm"（12 字符）
key     = key_b64 补 'X' 到 24 字节          // "NTMyMzExc2RmXXXXXXXXXXXX"
cipher  = DESede/ECB/PKCS5Padding(key)
body    = cipher.encrypt(json(params))
```

- 请求头：`x-uuid`(=`jrxc_<android_id>`)、`x-deviceuuid`、`x-userid`、`x-openid`、`x-appinfo`(`channel/pkg/versionName/version?/MODEL/BRAND`)
- `Content-Type: application/wxt;charset=UTF-8`
- 响应为 JSON 明文（非加密）。

### 3.2 端点（静态确认 + 实测）

| 路径（相对 `/zone/1.0.1/`） | 参数 | 说明 | 实测 |
|---|---|---|---|
| `point/user/getNewUserPointInfo.htm?osType=1` | 无 | **建积分用户** → `{pointId, pointNumber}` | **已验证** |
| `point/consume/getConsumePointConfig.htm?osType=1` | `pointId` | 全部功能消耗项（`functionTag`/`consumeType`/点数） | **已验证** |
| `point/task/getTaskUserPointConfig.htm?osType=1` | `pointId` | 任务奖励表 | **已验证** |
| `point/task/doAddTaskPoint.htm?osType=1` | `pointId`+`taskId` | 领任务奖励 | **已验证**，无风控校验 |
| `point/user/getPointBalanceInfo.htm?osType=1` | `pointId` | 余额 | **已验证** |
| `point/detail/getDetailByPointId.htm?osType=1` | `pointId` | 积分流水 | **已验证** |
| `point/consume/doUnAIReducePoint.htm?osType=1` | — | 扣点 | 未测 |
| `googlePay/getProductList.html?osType=1` | — | 商品/活动表 | **已验证**（返回 viddo 内购商品） |
| `googlePay/verifyPurchaseVip.html` | — | 支付核销 | 未测 |

### 3.3 积分经济（实测快照 2026-10-30）

消耗项（`functionTag=texttovideonew`，节选，共 70 条）：

| consumeType | 描述 | 点数 |
|---|---|---|
| 92 / 93 | AI 特效-腾讯 / 腾讯-hot | 30 / 50 |
| 202 / 203 / 204 | 自己图生视频 / -hot / -new | 30 / 50 / 30 |
| 205/206/207 | 自己 ComfyUI / -new / -hot | 30 / 40 / 50 |
| 208/209 | 火山 vidu-hot / -new | 50 / 40 |
| 215/216/217 | nano+pix / -new / -hot | 30 / 40 / 50 |
| 154 | AI 特效-Wan | 40 |
| 628/632/633 | nano+seedance 10s/5s/15s | 100 / 60 / 140 |
| 196/197/198/199/200/210/643/644 | Vidu / VEO / AceSora / MiniMax / pixverse / seeddance | **0（免费档）** |
| `ai_editor_5s`/`ai_editor_10s` | Kling O1 | 30 / 45 |

任务奖励（全部可在无任何校验下领取，实测）：

| taskId | 任务 | 点数 | 实测 |
|---|---|---|---|
| 1 | 每日登录 | 20 | **成功 +20** |
| 56 | 7 日签到（首日） | 20 | **成功 +20** |
| 60 | 开启通知 | 5 | **成功 +5** |
| 61 | 应用评分 | 5 | **成功 +5** |
| 62 | 分享 | 5 | **成功 +5** |
| 193 | 激励广告 | 2（15 次/天） | **成功 +2** |
| 290 | Make 3 videos | 30 | 未测 |

单设备首日可白拿 **≈ 57 点**（实测累计到 57），足够 1 次 30 点档或多次 0 点档生成。

---

## 4. 客户端复现（本目录代码）

| 文件 | 作用 |
|------|------|
| `viddo_client.py` | L2 客户端：设备身份 / RSA / 签名 / multipart 提交 / 轮询 |
| `points_client.py` | L1 客户端：3DES 信封 / 积分用户 / 配置 / 领点 |
| `gateway/server.py` | 本地网关（标准库实现，8971 端口） |
| `demo/index.html` | 交互式 demo（真实打上游） |
| `stress/stress_r1.py` | 第一轮压测脚本 |
| `probe_uuid.py` / `probe_consumetypes.py` | 定位探测脚本 |

一键自检：

```powershell
cd D:\apk-analysis\viddo404
python viddo_client.py          # 打 getUuid + 生成签名样例
python points_client.py         # 打 3DES 积分接口
python gateway/server.py        # http://127.0.0.1:8971
python stress\stress_r1.py --conc 16 --n 200
```

---

## 5. 阻断点（R1 结论）

提交链路全部打通，**执行链路被服务端「共用表」配置挡住**：

1. `v3/texttovideonew` 提交任意内容都**受理**并返回 task key（RSA/签名/表单格式证明正确）。
2. 轮询立刻返回：
   - 无 `consumeType` → `1404 积分系统用户不存在`
   - 有 `consumeType` → `1405 积分系统功能不存在`
3. 已穷举排除的假设（全部实测）：
   - App 自身积分表里 **70 个** `texttovideonew` consumeType（含 0 点免费档）
   - 数字空间 `1..160`、全部 `consumeId`（459~2592）
   - `functionTag` / `type` / `uuId` / `check` 附加字段
   - `function_configs` / `isVip` / `point_id` 组合参数（`PointsApi.g()` 的真实入参）
   - `platFormId` **二维扫描**：`{tencent, volcengine}` × 70 个 consumeType = 140 次，全 `1405`
4. `platFormId` 语义已定案：它是**平台名字符串**（不是数字 id）。Dart 里硬编码出现 `"tencent"`
   （`ui/page/template/template_create_logic.dart`）。实测：
   - `tencent` / `volcengine` → 服务端能解析（不抛异常，错误落到 `1405`）
   - 其他（`vidu/comfyui/pixverse/pika/minimax/seedance/kling/nano/sora/veo/wan/grok/self/custom/1x`）
     → `500 Cannot invoke "com.magicut.transfer.entity.ApiPlatform.getId()" because "apiPlatform" is null`
   - 纯数字（`1`,`2`,`10`,`92`）→ 同上 NPE，说明按 id 主轴查不到记录
5. 结论：`consumeType` 与 `platFormId` 都只是**入参维度**，真正的闸门是服务端
   `appId=YZ080` 的「共用表」里没有 `texttovideonew` 的功能行。该表由运营后台写入，
   客户端只做透传，**无法离线枚举**。

### 后续唯一有效路线

| 路线 | 做法 | 成本 | 判断 |
|------|------|------|------|
| A 真机/模拟器抓包 | 装原版 APK，UI 里真实跑一次文生视频，mitmproxy 抓 `content`+`decrypt` 拿到真实 `(consumeType, platFormId)` | 中（需过 NSC + CA 装系统区） | **唯一能定案** |
| B 配置接口 | `api.videoshowapp.com/videoshow/api/v2/config` 恒 500（11 种参数名 × GET/POST 全试过）；`camera.magicutapp.com` 的 `themePackage` 对 `type=TextToVideo` 恒返回空集 | 低 | **已判定无效** |
| C 放弃 | 若 UI 里该功能本身也报错，则该 App 的 AI 能力整体不可用 | 0 | 抓包后再说 |
