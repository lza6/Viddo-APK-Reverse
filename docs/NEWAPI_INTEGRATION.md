# Viddo → new-api 接入方案（R1 评估版）

> 当前状态：**不具备入渠道条件**。本文写的是"打通后怎么接"和"为什么现在还不能接"，
> 避免把"提交受理"误当成"能出片"。

---

## 1. 为什么现在还不能入渠道

new-api 的一个 channel 必须能对用户请求产出**真实结果**。Viddo 目前：

| 环节 | 结果 |
|---|---|
| 建号 / 签名 / 提交任务 | ✅ 上游受理并返回 task key |
| 任务执行 | ❌ 轮询立刻 `1405 积分系统功能不存在` |
| 出片 | ❌ 无 |

即：能"下单"不能"取货"。此时建渠道只会在日志里刷 1405，属于伪实现，不放行。

## 2. 打通后的形态（预案）

### 2.1 能力映射

上游只有一个真正可用的视频入口 `v3/texttovideonew`（含文生视频/图生视频/续写）和一个 `v3/videoextend`。
对应 new-api 的 **task 类视频渠道**（与 AIVM / AI Cartoon Pet 同类，参考已有 `type=72` 的做法）：

| new-api 请求 | 上游动作 |
|---|---|
| `POST /v1/video/generations`（model=viddo-t2v-*，prompt，aspect_ratio） | `v3/texttovideonew` 提交 → 拿 key |
| 任务轮询（`/v1/video/generations/{id}`） | `v4/downLoad/{key}` → `process` / `data` |
| `POST /v1/video/generations`（model=viddo-i2v-*，image） | 走 `v4/getUuid(functionTag)` 取 S3 凭证 → PUT 图片 → `v3/texttovideonew`（带 `imagefile` + `imageFileName`） |

模型名建议映射到 `consumeType`（一旦 R2 拿到真实映射表就填死）：

```
viddo-t2v-tencent    -> consumeType 92 / 93
viddo-t2v-comfyui    -> 205 / 206 / 207
viddo-t2v-vidu       -> 208 / 209
viddo-t2v-nano-pix   -> 215 / 216 / 217
viddo-t2v-seedance   -> 628 / 632 / 633
viddo-extend         -> v3/videoextend
```

### 2.2 渠道所需配置项

| 配置 | 说明 |
|---|---|
| `appId` | `YZ080`（固定） |
| `pkgName` | `saver.ins.fb.twitter.storydownloader`（固定） |
| `channel/version` | `GOOGLEPLAY` / `4.0.4.1` / `35` |
| `android_id` 池 或 单设备 | 每个 android_id 自动换一个 `uId` 与 `pointId` |
| `pointId` | 每设备独立；靠积分任务补点（单设备首日 ≈57 点） |
| `consumeType` | **R2 待定**（真实映射表） |
| `platFormId` | **R2 待定**（`ApiPlatform` 主键） |

### 2.3 计费换算建议

| 档位 | 上游点数 | 建议 new-api 计费 |
|---|---|---|
| 0 点免费档（Vidu/VEO/AceSora/Minimax/pixverse/seeddance） | 0 | 按次数计极低价或免费，做引流档 |
| 30 点档（腾讯/ComfyUI/nano+*） | 30 | 按 1 点 ≈ 固定额度换算 |
| 40~50 点档 | 40/50 | 中档 |
| 60~140 点档（seedance 5s/10s/15s） | 60/100/140 | 按时长分档 |

注意：上游按「**点数**」计价而不是 token/秒，且点数有有效期（`pointExpiresDay` 1~2 天），
换算时必须把过期损耗算进去，否则余额会虚高。

### 2.4 稳定性与合规注意

- 上游无速率限制，但**积分服务按 IP 限流建号**（实测 6/100），需要多出口代理池配合。
- 任务 key 轮询无鉴权，会泄露他人任务状态 → 网关侧必须做 key↔用户映射，不能把 key 直接暴露给终端用户。
- S3 临时凭证签发行为属于上游设计缺陷，**本方案不复用它做超出上传的用途**（不列举、不遍历 bucket）。
- 该 App 属第三方商业产品，渠道名/定价上线前需业务侧确认可用性与合规边界。

---

## 3. R2 待办清单（按优先级）

1. **抓真实生成请求**：模拟器 + mitmproxy，UI 跑一次文生视频，拿到 `content`/`decrypt` 里的
   `consumeType` 与 `platFormId`，以及真实 `prompt` 结构（是否含 `model`/`duration`/`style`）。
2. 用真实参数复跑 `v3/texttovideonew`，确认 `process` 递增且 `data` 出视频 URL。
3. 验证 `v4/downLoad/{key}` 出片 URL 的可下载性与有效期。
4. 决定图片上传是否必需（纯文生视频档是否可跳过 `imagefile`）。
5. 之后再写 new-api 渠道代码（task 类），并用真实出片做端到端验收。
