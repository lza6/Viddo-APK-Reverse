# R2 · 真机/模拟器抓包报告（A 路线）

目标：在真实客户端里跑一次生成，拿到 `(consumeType, platFormId)` 与真实 `content` 结构。
结论：**未取到参数——客户端在发出任何网络请求之前就本地拒绝了**（附完整证据链）。

环境：`emulator-5556`（Android 11 / x86_64 / userdebug / root / 带 GMS + libndk_translation 可跑 arm64 APK）
工具：frida-server 16.5.9 (x86_64) + `frida/spawn` 断点、`adb` UI 自动化

---

## 1. 环境可用性（已验证）

| 项 | 结果 |
|---|---|
| 安装 APK | ✅ Success（arm64-only 在 x86_64 AVD 上经 libndk_translation 运行） |
| 启动 | ✅ pid 存在，无 native 崩溃 |
| 应用界面 | ✅ 完整可交互（Home / TEXT / SKETCH / GALLERY） |
| Frida 附加 | ✅ 需 `adb forward tcp:27042`，且 `dev.attach(pid)`（`get_process(name)` 在该远程设备上失效） |
| 页面文案 | ⚠️ 标题/占位符等文案**不在 `libapp.so` 明文中**（Dart AOT 字符串表压缩），不能靠字符串 grep 判定归属 |

## 2. 抓到的真实流量（spawn 起来就开始抓，完整）

启动即打（全部走 L1 3DES 信封，`apis.videoshowapp.com/zone/1.0.1`）：

```
POST point/user/getNewUserPointInfo.htm?osType=1
POST point/user/getPointBalanceInfo.htm?osType=1
POST point/consume/getConsumePointConfig.htm?osType=1
POST point/task/getTaskUserPointConfig.htm?osType=1
POST googlePay/getProductList.html?osType=1
POST materialOperationClient/getHomeTopAdvert.htm
```

**一次 `aicup-v2.magicutapp.com`（L2 AI 服务）请求都没有发生。**

## 3. 点 Create 的实测结果

| 观测 | 结果 |
|---|---|
| UI 反馈 | 弹窗 `Error` / `Token Error. Please contact support!` |
| OkHttp 请求（全局 `Request.Builder.build` 钩子） | **0 条** |
| 设备 TCP 连接快照（250ms 采样 20s） | 只有 Firebase(5228)，**无新增外连** |
| `AI-Service` SharedPreferences（存 uId 的地方） | **文件不存在** → `v4/getUuid` 从未成功 |
| `AIServiceSdk.a()`（App.onCreate 触发） | ✅ 被调用 |
| `AIServiceLib.h(appId=YZ080, baseUrl=aicup-v2…)` | ✅ 被调用 |
| `ServiceApis.o()`（updateServiceUUID / 取 uId） | ❌ **从未被调用** |

`AIServiceLib$init$1 / init$2` 只做本地模型初始化（`AIServiceLib.a(String,int)`），并不取 token —— token 是在真正提交任务时才懒加载。因此：

> 「Token Error」= 提交前的前置校验失败（拿不到 uId/token），
> 客户端**直接短路**，根本没走到 L2 服务。

## 4. 判定

该 build（LiteApks 的 "Pro" 修改版）的 AI 生成链路在客户端被掐断，无法通过它取得 `(consumeType, platFormId)`。两种可能：

1. 修改版去付费补丁破坏了 token 获取/登录态（最可能）；
2. 该 App 的 AI 能力需要真实登录/订阅态才下发 token。

两者都意味着：**普通用户在这台设备上也无法生成**，这与我们在 L2 侧测到的「共用表里没有该 appId 的功能行（1405）」互相印证。

## 5. 若要继续（R3 候选，需用户决定）

| 方案 | 说明 | 成本 |
|---|---|---|
| 换原版 APK（未修改） | 从 apkmirror/apkpure 取 4.0.4.1 原包，重复本流程；若原包能生成 → 参数必现 | 中（需下载原包 + 重新过一遍） |
| 用真机 + 真实 Google 账号登录 | 排除登录态因素 | 高（需真机与账号） |
| 放弃该 App | 现有证据已足以判定"当前不可作渠道" | 0 |

---

## 6. 复现命令

```powershell
# 1. frida-server
adb -s emulator-5556 push frida/frida-server /data/local/tmp/frida-server
adb -s emulator-5556 shell "chmod 755 /data/local/tmp/frida-server; nohup /data/local/tmp/frida-server -l 0.0.0.0:27042 &"
adb -s emulator-5556 forward tcp:27042 tcp:27042

# 2. 装包
adb -s emulator-5556 install -r "Viddo v4.0.4.1 (Pro).apk"

# 3. spawn 抓流量（不要用 attach，会错过初始化）
python frida/driver_spawn.py        # 用 hook3.js：确认 SDK 初始化 + 全量 OkHttp
python frida/driver.py <pid>        # 用 hook2.js：抓 AI 参数（d.b / multipart）

# 4. UI 自动化
adb -s emulator-5556 shell input tap <x> <y>   # TEXT 页 → 输入 prompt → Create
```
