# xke-ai-routing

## 最新实施进度（2026-10-11）

macOS Shadowrocket 已经实测：远程模块更新、规则命中、模块内 `AI-PROXY` 解析、两个订阅节点分别作为路由出口、国内直连，以及更新主配置后的规则保留。**真实连通性、广告规则全量兼容和策略组界面切换仍需持续验证。**

### 已部署的自动化

- 远程模块固定路径：`modules/phase2-group-test.module`（**不要重新添加 URL，只需更新现有模块**）。
- `sources/approved.rules`：经过人工批准、允许发布的 AI 域名规则。
- `sources/blocked.rules`：明确的拒绝例外，生成时排在 AI 规则之前；目前只列出已知的 `r.openai.com`，**不是对主配置 5 万多条规则的完整冲突审计**。
- `scripts/build_module.py`：格式检查、去重、共享后缀拒绝、例外优先级、生成模块及 `reports/build.json`。
- `scripts/fetch_sources.py`：每日从两个社区源收集候选域名到 `sources/candidates.txt`，并生成 `reports/upstream.json`；**候选域名不会自动进入模块**。
- `.github/workflows/update.yml`：每天 UTC 03:17 定时运行，支持手动运行；仅在生成文件变化时提交。上游全部不可用时停止候选刷新，不覆盖旧模块。
- 不存储代理订阅 Token、UUID 或 REALITY 私钥。

### 新域名如何发布

先审阅 `sources/candidates.txt`，确认域名确属 AI 服务、不会影响普通 Google 流量或广告拦截，然后手动添加到 `sources/approved.rules`。GitHub Actions 会重新生成**原来的模块文件**，Shadowrocket 只需点击更新。

**限制：** 目前实现的是「每日自动发现候选 + 已批准规则自动生成和发布」，不是「未经审核的 AI 域名自动放行」。此保守设计是为了防止错误规则覆盖现有广告拦截。GitHub 发布并不意味着 Shadowrocket 已自动刷新。

---


> 面向 macOS Shadowrocket 的 AI 专属代理分流规则维护项目。**保留现有主配置、国内外分流和广告拦截**，让 ChatGPT、OpenAI API、Google Gemini、AI Studio、Antigravity 等 AI 服务优先使用个人代理线路。

**项目状态：核心兼容性已验证，首版自动化已部署。** 本仓库 README 描述目标架构和实施计划，不代表模块已验证可在 macOS Shadowrocket 中新增策略组，也不代表自动发现全部 AI 域名。

## 1. 目标

- 不修改上游维护的 Shadowrocket 主配置；主配置更新后，AI 规则仍可独立维护。
- 不破坏国内直连、国外代理和广告拦截逻辑。
- 将 AI 请求限定在个人订阅的两条线路：`Tencent-US-Direct`（VLESS + REALITY）和 `Tencent-US`（VLESS + WebSocket / Cloudflare Tunnel）。
- 优先使用稳定的单一出口；允许手动切换备用线路，避免频繁变更 AI 服务的出口 IP。
- GitHub Actions 定期拉取、校验、去重和发布 AI 域名规则；对高风险共享域名实行人工审核。
- 提供可追溯的变更记录、配置验证和回滚能力。

## 2. 当前环境与约束

| 项目 | 当前情况 |
| --- | --- |
| 客户端 | Shadowrocket for macOS |
| 主配置 | `sr_cnip_ad-copy.conf`（本地副本，非本仓库维护） |
| 主配置结构 | `[General]`、`[Rule]`、`[URL Rewrite]` 等；未发现 `[Proxy Group]` |
| 主配置兜底 | `GEOIP,CN,DIRECT`、`FINAL,PROXY` |
| 广告过滤 | 原配置包含大量 `REJECT` 规则 |
| AI 主线路 | `Tencent-US-Direct` |
| AI 备用线路 | `Tencent-US` |
| 节点来源 | 现有 RocketGo 订阅；本项目不复制订阅 Token 或节点凭据 |

**注意：** 目前尚未验证 macOS Shadowrocket 模块是否能直接引用订阅节点名称，以及能否通过模块创建 `[Proxy Group]`。因此，策略组配置属于待验证设计，不应直接视为可用成品。

## 3. 预期流量路径

```text
                  Shadowrocket for macOS
                           │
            ┌──────────────┴──────────────┐
            │                             │
      原有主配置（定期更新）        xke AI 模块（独立更新）
            │                             │
   国内直连 / 国外代理 / 拦截       OpenAI / Google AI 域名
            │                             │
            │                         AI-PROXY
            │                             │
            │                   ┌─────────┴─────────┐
            │                   │                   │
            │             Tencent-US-Direct     Tencent-US
            │                 （首选）            （备用）
            └───────────────────────────────────────────
```

**重要原则：** 先匹配的规则可能改变现有拦截行为。AI 规则不得无条件覆盖主配置中的广告/追踪域名拦截；应先进行冲突检测并确定规则优先级。

## 4. 实现方案

### 方案 A：Shadowrocket 原生模块（优先验证）

- 主配置仍由原有来源更新。
- AI 域名规则由远程 `.module` 独立维护。
- 优先验证模块能否将规则路由至订阅节点，以及能否创建/引用固定策略组 `AI-PROXY`。
- 若可行，则模块与主配置独立更新，无须改写原配置文件。

以下是**规则语义示例**，不是已经验证可导入的完整模块：

```ini
#!name=xke AI Routing
#!desc=Dedicated routing for OpenAI and Google AI

[Rule]
DOMAIN-SUFFIX,chatgpt.com,AI-PROXY
DOMAIN-SUFFIX,openai.com,AI-PROXY
DOMAIN-SUFFIX,oaistatic.com,AI-PROXY
DOMAIN-SUFFIX,oaiusercontent.com,AI-PROXY
DOMAIN,gemini.google.com,AI-PROXY
DOMAIN,aistudio.google.com,AI-PROXY
DOMAIN,ai.google.dev,AI-PROXY
DOMAIN,generativelanguage.googleapis.com,AI-PROXY
```

> `AI-PROXY` 必须实际存在且可被客户端解析。以上示例不会自动创建策略组；不要在验证之前直接作为生产模块使用。

期望的策略组行为：`AI-PROXY` 提供 `Tencent-US-Direct` 和 `Tencent-US` 两个可选出口，默认选择直连。是否能够在模块中定义该策略组，以客户端实测为准。

### 方案 B：生成合并后的完整配置（兼容性回退）

若原生模块无法创建策略组或引用订阅节点，则通过构建脚本：

1. 获取上游主配置及经过审核的 AI 域名规则。
2. 解析配置段落，保留原有 `[General]`、广告规则、URL Rewrite 等内容。
3. 注入可被客户端识别的代理/策略组定义与 AI 规则。
4. 将 AI 规则放在适当位置，并检测与 `REJECT`、`GEOIP`、`FINAL` 的冲突。
5. 运行格式与语义校验，生成完整配置供 Shadowrocket 导入。

**安全要求：** 不将私人订阅链接、Token、UUID、REALITY 密钥或生成的私人节点内容提交至公开仓库。若使用 GitHub Actions 处理私人订阅，应评估凭据存储与构建产物泄露风险；更安全的替代方案是在本机或私人服务器合并。

## 5. 域名维护策略

### 首批覆盖范围

| 服务 | 范围 | 策略 |
| --- | --- | --- |
| ChatGPT | Web、桌面端及必要的静态资源域名 | 精准域名匹配 |
| OpenAI API | API 相关域名 | 精准域名匹配 |
| Google Gemini | Gemini Web | 精准域名匹配 |
| Google AI Studio | AI Studio、Gemini API | 精准域名匹配 |
| Google Antigravity | IDE、模型 API 及已确认的辅助域名 | 实际连接日志辅助核实 |

### 数据源

可评估社区规则项目，例如：

- `SukkaW/Surge`：分流规则参考。
- `imetn/SurgeToolkit`：AI 域名规则参考。
- `Yixuling/surge-rulekit`：AI 专项规则参考。
- `hainingshen/shadowrocket-policy-module`：自动生成模块的架构参考。

这些属于**候选上游**；接入前需核实规则格式、维护状态、许可证与误判情况。

### 合并规则

- 优先 `DOMAIN` 精确匹配，其次使用经过审核的 `DOMAIN-SUFFIX`。
- 不直接把 `google.com`、`googleapis.com` 等共享根域名全部划入 AI 专线。
- 不把 AI 域名 DNS 解析得到的 CDN IP 自动永久加入代理规则。
- 对新增域名记录来源、首次发现时间和变更差异。
- 对登录、认证、遥测、共享 CDN 等域名设置人工审核门槛。
- 与原有 `REJECT` 规则发生冲突时，不自动放行。

## 6. 计划中的仓库结构

```text
xke-ai-routing/
├── README.md
├── sources/
│   ├── openai.txt
│   ├── google-ai.txt
│   ├── antigravity.txt
│   └── custom.txt
├── scripts/
│   ├── fetch_sources.py
│   ├── normalize.py
│   ├── validate.py
│   └── build_module.py
├── modules/
│   └── ai-routing.module
├── reports/
│   ├── changes.md
│   └── conflicts.json
└── .github/
    └── workflows/
        └── update.yml
```

上述文件为**规划结构**，尚未实现。

## 7. 自动更新流程（规划）

```text
GitHub Actions（每日检查）
    ↓
拉取候选 AI 规则源
    ↓
解析 / 规范化 / 去重
    ↓
与现有规则和拦截清单比较
    ↓
可信新增规则自动合并；不确定项待审核
    ↓
生成 .module 与差异报告
    ↓
校验通过后发布
    ↓
Shadowrocket 客户端按自身设置更新远程模块
```

GitHub 发布更新不等于客户端已自动下载并应用；需分别验证客户端更新频率和生效机制。

## 8. 验收标准

- [ ] 模块可以导入 macOS Shadowrocket 且不破坏原配置。
- [ ] AI 规则能够优先于普通兜底规则匹配。
- [ ] 能从规则稳定选择 `Tencent-US-Direct` 或 `Tencent-US`。
- [ ] 验证是否支持模块新增 `AI-PROXY`；不支持则切换方案 B。
- [ ] ChatGPT、Gemini、AI Studio、Antigravity 的关键请求命中预期线路。
- [ ] 普通国内网站、非 AI 国外网站仍遵循原配置。
- [ ] 已有广告拦截不因 AI 规则失效。
- [ ] 更新原主配置后 AI 分流仍有效。
- [ ] 更新 AI 模块后规则按预期生效。
- [ ] 自动更新遇到上游异常或冲突时不发布有问题的规则。
- [ ] 支持回滚至上一个验证通过的版本。

## 9. 实施阶段

**阶段 1 — 兼容性验证：** 在 macOS Shadowrocket 中测试最小模块、节点引用、策略组创建与规则优先级。

**阶段 2 — 规则生成：** 完成候选规则源拉取、去重、冲突审查和模块生成。

**阶段 3 — 自动化：** 配置 GitHub Actions、变更报告、自动发布和回滚。

**阶段 4 — 真实流量完善：** 依据 ChatGPT、Gemini、Antigravity 实际连接记录，补齐缺失域名并持续降低误判。

## 10. 非目标

- 不替换或重写现有广告过滤体系。
- 不管理 RocketGo 服务端 Xray 配置及私人订阅凭据。
- 不承诺自动发现所有 AI 域名或按进程强制捕获所有网络请求。
- 不保证代理节点故障时 AI 会话能够无感迁移。

---

**当前下一步：** 完成 macOS Shadowrocket 的最小模块验证，再决定采用原生模块还是完整配置合并。项目 README 可以先行提交，但不应将规划中的功能标记为已完成。
