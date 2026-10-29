# Viddo v4.0.4.1 — 逆向与压测报告（R1）

生成时间：2026-10-30 · 目标：`Viddo v4.0.4.1 (Pro).apk`
结论：**协议 100% 还原、提交链路全通；生成执行被服务端配置闸门阻断（不可入渠道，R2 需抓包定案）**

---

## 1. 静态测绘

### 1.1 壳体

| 项 | 值 |
|---|---|
| 包名 | `saver.ins.fb.twitter.storydownloader`（沿用下载器壳，实际功能是 AI 视频） |
| 版本 | 4.0.4.1 (35) |
| 体积 | 129 MB（`libapp.so` 12.9 MB + 19 个 so） |
| 框架 | Flutter / Dart 3.4.3 AOT（`flags: product … compressed-pointers`） |
| 加固 | 无 DexProtector / 无 VM、无完整性校验自毁，**纯静态可读完** |
| Dex | 6 个 dex，`classes2~6` 业务占大头 |
| 原生库 | tensorflowlite(+gpu)、face_detector、x265、aveditor、MobileFXV2、skia-app、aqskia、mmkv、sndtouch、stub |

### 1.2 代码分层

```
Dart (libapp.so)  com.energysh.quickart.*  → UI / 业务编排 / 参数拼装
    ├ http/encrypt_http.dart          3DES 信封 HTTP（仅埋点用）
    ├ plugins/ai_worker_plugin.dart   MethodChannel → Java AI Worker
    └ ui/page/texttovideo/*           文生视频/图生视频/续写界面
Java/Kotlin
    ├ com.energysh.aiservice.*        ★ AI 服务 SDK（RSA+签名+multipart+轮询）
    ├ com.energysh.points.*           积分/支付（3DES 信封）
    ├ com.energysh.net.*              Retrofit 客户端 / 重试拦截器
    ├ com.energysh.quickart.*         Flutter 插件层 / Worker / 任务持久化
    ├ com.xvideostudio.enjoystatisticssdk  埋点 SDK（★ 内置 3DES 密钥）
    └ 第三方：Firebase/AppsFlyer/AdMob/MLKit/Facebook/TikTok SDK
```

关键：**业务密钥与加密常量全部落在 Java/Kotlin 明文常量里**，无需 Frida、无需真机，`jadx + blutter` 静态即可完整还原。

### 1.3 反编译产物

```
viddo404/
├ apktool_out/     资源 + smali（6 dex）
├ jadx_out/        Java 反编译（14 个方法失败，用 --show-bad-code 补）
├ jadx_bad/        针对性补反编译
├ blutter_out/     Dart AOT → asm/{quickart,...}（3.4.3，一次成功）
└ libapp_strings.txt
```

---

## 2. 安全发现（对上游方的风险，本方向只做记录）

| # | 级别 | 发现 | 证据 |
|---|------|------|------|
| S1 | 高 | `v4/getUuid` **零鉴权**，任意 `android_id` 无限造号 | 200 并发 200/200 成功（§4） |
| S2 | 高 | 同端点带 `functionTag` 即**匿名签发 AWS S3 临时凭证**（bucket `ai-files-ehe`, region `us-east-2`, dir `ai-app-test_dir`），未校验调用方是否有该功能权限 | 实测返回 `accessKey/secretKey`（已脱敏，见 §5） |
| S3 | 中 | 任务提交只校验 RSA+md5 签名，签名密钥为客户端常量，**任何人不装 App 也能构造合法请求** | 静态确认 `j2.g` / `j2.h` + 实测受理 |
| S4 | 中 | 积分任务 `doAddTaskPoint` 无任何回执校验：每日登录/通知/评分/分享/激励广告均可**直接空领** | 实测 6 个 taskId 全成功，累计 57 点 |
| S5 | 中 | 积分用户注册按 IP 限流（`device limit`），但 AI 服务造号完全不限 | 实测 §4 |
| S6 | 低 | 3DES 密钥 `"532311sdf"` 硬编码在埋点 SDK 静态字段 | `NetExecutor.CURRENT_PUBLIC_KEY` |
| S7 | 低 | 错误信息直接抛服务端堆栈类名（`com.magicut.transfer.entity.ApiPlatform`） | 实测 500 响应 |

> 本报告不利用 S2 的 S3 凭证做任何写入操作，仅记录签发行为存在。

---

## 3. 协议还原（详见 `docs/PROTOCOL.md`）

三层加密/签名，全部还原并**用真实请求验证**：

1. **L1 信封**：`DESede/ECB/PKCS5`，key = `base64("532311sdf")` 补齐 24 字节。
2. **L2 参数加密**：`RSA/ECB/PKCS1Padding`（2048bit，117 字节分块）+ 自定义 Base64 去换行。
3. **L2 签名**：`md5(pkgName + uId + appTime)`。

验证方式：上游对「格式正确的请求」一律返回受理 key，对格式错误的返回空 key/400；因此拿到 key 即证明加密与签名链路正确。

---

## 4. 第一轮压测（`stress/stress_round1.json`）

环境：Windows 本机直连（绕开本地坏代理），跨洋到 `us-east-2` AWS，因此绝对延迟偏高；关注**成功率与限流行为**，不要当作上游容量上限。

| 链路 | 并发 | 请求数 | 成功率 | RPS | p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| `v4/getUuid` | 16 | 200 | **100%** | 6.39 | 2242 ms | 3286 ms | 4149 ms |
| `v3/texttovideonew` 提交 | 8 | 50 | **100% 受理** | 3.70 | 2125 ms | 2605 ms | 2635 ms |
| `v4/downLoad/{key}` 轮询 | 16 | 200 | 0%（全 1405） | 6.78 | 2382 ms | 2774 ms | 2974 ms |
| 积分 `getNewUserPointInfo` | 8 | 100 | **6%**（`device limit`） | 7.56 | 1043 ms | 1142 ms | 1213 ms |

要点：

- **AI 服务无速率限制、无设备上限**：200 次建号零失败，16 并发下稳定。
- **积分服务有 IP 级风控**：同一出口 IP 短时间只放出 ~6 个新用户，之后固定 `{"retCode":0,"retMsg":"device limit"}`（失败也是 200，需看 body）。
- 提交受理不消耗点数（扣点发生在执行阶段），因此可以低成本高频探测。
- 轮询无鉴权，知道 key 即可查任意任务状态（信息泄露面）。

---

## 4.5 R2 抓包（A 路线）结果

在 Android 11 x86_64 AVD（root + GMS + libndk_translation）上安装该 APK，
Frida spawn 全程挂钩后复跑：App 能启动、UI 完全可用（Home / TEXT / SKETCH / GALLERY），
但点 `Create` 立刻弹 `Token Error. Please contact support!`，**全程零网络请求**：

- 全局 OkHttp `Request.Builder.build` 钩子：0 条
- 设备 TCP 采样 20s：仅 Firebase 5228，无新增外连
- `AI-Service`（存 uId 的 SP）不存在 → `v4/getUuid` 从未成功
- `AIServiceSdk.a()` / `AIServiceLib.h(appId=YZ080)` 均被调用，但 `ServiceApis.o()`（取 uId）从未被调用

结论：该 build（LiteApks "Pro" 修改版）的生成链路在客户端被 token 预检掐断，
与 L2 侧「共用表无功能行（1405）」互相印证。细节与复现命令见 `docs/R2_CAPTURE.md`。

## 5. 脱敏说明

文档/代码中涉及上游凭证处一律脱敏：

- S3 `accessKey` → `AKIA****************`
- S3 `secretKey` → `****（不落盘、不入库、不进文档）`
- 仅保留 bucket / region / dir 结构性信息用于说明问题。

---

## 6. R1 判定

| 能力 | 状态 |
|---|---|
| 设备身份 / 会话 | ✅ 已验证 |
| S3 凭证签发 | ✅ 已验证（仅记录） |
| 积分用户 / 余额 / 配置 / 领点 | ✅ 已验证 |
| 任务提交（RSA+签名+multipart） | ✅ 已验证（受理） |
| 任务执行 / 出片 | ❌ 阻断：`1404/1405` 共用表 |
| 轮询 | ✅ 已验证（返回服务端判定） |
| 可用于 new-api 渠道 | ❌ 暂时不能（无生成能力） |

阻断根因与后续路线见 `docs/PROTOCOL.md` §5。R1 补测还确认了两件事：

- `platFormId` 是**平台名字符串**而非数字 id（Dart 里硬编码出现 `"tencent"`）。
  实测 `tencent` / `volcengine` 服务端可解析；其余平台名与全部纯数字一律触发
  `500 ApiPlatform.getId() ... apiPlatform is null`。
- 配置侧已判定无效：`api.videoshowapp.com/videoshow/api/v2/config` 在 11 种参数名 ×
  GET/POST 下恒 500；`camera.magicutapp.com` 的 `themePackage` 对 `type=TextToVideo`
  恒返回 `{"data":{"totalSize":0,"size":0}}`（3 个 pkgName × 5 个 type 全试）。
  因此 `(consumeType, platFormId)` 只能靠真机抓包取得。
