# 科研动态自动摘要工具说明

本项目是一个本地运行的科研动态监控工具。它会按配置中的研究关键词自动查询论文、会议、新闻和指定网页，去重后调用大模型生成摘要，并输出 Markdown 文件，同时发送邮件。

当前项目已经针对气体探测器方向配置好，关注领域包括：

- gas detector
- gas photodetector
- RPC
- Resistive Plate Chamber
- Low pressure gas detector
- MPGD
- Micromegas
- Gaseous detector
- Gaseous photodetector

当前已配置：

- 摘要模型：小米 MiMo Token Plan，模型 `mimo-v2.5-pro`
- 收件邮箱：通过 `config.toml` 或 `SMTP_TO` 配置
- 默认查询范围：最近 30 天
- 每次最多保留：100 条结果
- 定时任务：每周一 09:00 自动运行
- 输出文件：英文版和中文版各一份
- 邮件发送：英文摘要和中文摘要各一封

## 文件结构

主要文件和目录：

```text
C:\AI\codex\plug_skill
├── config.toml                    # 当前实际使用的配置
├── config.example.toml            # 配置模板
├── README.md                      # 英文说明
├── README.zh.md                   # 中文说明
├── research_digest\               # 工具源码
├── scripts\install_windows_task.ps1 # Windows 定时任务安装脚本
├── tests\                         # 单元测试
└── output\                        # 摘要输出目录
```

常用输出文件：

```text
output\latest_digest.md       # 最新英文摘要
output\latest_digest.zh.md    # 最新中文摘要
```

## 数据源

当前支持并已配置的数据源包括：

- arXiv
- Crossref
- Semantic Scholar
- PubMed
- Google News RSS
- Google 官方 Custom Search JSON API
- Conference Alerts
- WikiCFP
- 手动监控的会议或程序页面
- 自定义 RSS/Atom 订阅源

arXiv 当前限定在这些分类中搜索：

```toml
categories = ["physics.ins-det", "hep-ex", "nucl-ex", "physics.acc-ph"]
```

这能减少无关计算机科学、工业气体报警器、市场报告等结果。

## 重点会议监控

通用会议聚合站经常漏掉粒子探测器方向的专业会议，所以本项目额外加入了“重点页面监控”。

当前已手动监控：

- RPC 2026 - XVIII Conference on Resistive Plate Chambers and Related Detectors
- RPC 2026 timetable
- RPC 2026 scientific program
- MPGD2026 - 9th International Conference on Micro-Pattern Gaseous Detectors
- MPGD2026 timetable
- MPGD2026 scientific program

这些配置在 [config.toml](C:/AI/codex/plug_skill/config.toml) 的 `[sources.watched_pages]` 中。

监控页面会根据网页内容生成哈希值。如果网页程序、日程、会议说明发生变化，后续运行时可以再次进入摘要。

## 手动运行

进入项目目录：

```powershell
cd C:\AI\codex\plug_skill
```

正式运行并发送邮件：

```powershell
python -m research_digest run --config config.toml
```

运行后会：

1. 查询配置的数据源
2. 去除重复结果
3. 调用 MiMo 生成英文摘要
4. 调用 MiMo 生成中文摘要
5. 写入 `output\latest_digest.md`
6. 写入 `output\latest_digest.zh.md`
7. 发送英文摘要邮件
8. 发送中文摘要邮件

## 预览运行

如果只想查看结果，不发送邮件：

```powershell
python -m research_digest run --config config.toml --dry-run --ignore-state
```

说明：

- `--dry-run`：只预览和写文件，不发送邮件
- `--ignore-state`：忽略历史发送记录，方便重复测试同一时间范围

## 临时指定查询天数

默认查询最近 30 天：

```toml
[run]
lookback_days = 30
```

临时查询最近 100 天并发送邮件：

```powershell
python -m research_digest run --config config.toml --since-days 100 --ignore-state
```

临时查询最近 1 年并发送邮件：

```powershell
python -m research_digest run --config config.toml --since-days 365 --ignore-state
```

只预览最近 100 天，不发送邮件：

```powershell
python -m research_digest run --config config.toml --since-days 100 --dry-run --ignore-state
```

说明：

- 不加 `--dry-run` 就会发送邮件
- 加 `--ignore-state` 会忽略历史记录，强制按指定天数重新生成摘要
- 不加 `--ignore-state` 时，只会发送状态库中未见过的新条目

## 去重和历史记录

工具会把已发送条目的指纹记录在：

```text
.research_digest_state.sqlite
```

正式运行时，如果某篇论文或某个网页已经发送过，下次默认不会重复发送。

如果想临时重新查看旧内容，使用：

```powershell
--ignore-state
```

如果想彻底重置历史记录，可以删除：

```text
C:\AI\codex\plug_skill\.research_digest_state.sqlite
```

## 测试邮件

测试 SMTP 是否可用：

```powershell
python -m research_digest send-test --config config.toml
```

成功时会输出：

```text
Sent test email
```

当前邮件配置使用 USTC 邮箱：

```toml
[delivery.email]
enabled = true
smtp_host_env = "SMTP_HOST"
smtp_port_env = "SMTP_PORT"
username_env = "SMTP_USERNAME"
password_env = "SMTP_PASSWORD"
from_env = "SMTP_FROM"
to = ["your-email@example.com"]
chinese_enabled = true
```

SMTP 密码没有写入配置文件，而是保存在本机用户环境变量 `SMTP_PASSWORD` 中。

## MiMo API 配置

当前使用小米 MiMo Token Plan：

```toml
[summarization]
mode = "openai"
language = "English"
max_highlights = 8

[summarization.openai]
api_key_env = "MIMO_API_KEY"
base_url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
model = "mimo-v2.5-pro"
timeout_seconds = 120
max_completion_tokens = 1400
disable_thinking = true
```

MiMo API key 没有写入配置文件，而是保存在本机用户环境变量 `MIMO_API_KEY` 中。

如果 MiMo 调用失败，工具会自动回退到本地规则摘要，保证邮件任务不中断。

## 查看环境变量

查看某个环境变量是否已设置：

```powershell
$key = [Environment]::GetEnvironmentVariable("MIMO_API_KEY", "User")
if ($key) { "MIMO_API_KEY 已设置，长度：$($key.Length)" } else { "MIMO_API_KEY 未设置" }
```

查看 SMTP 密码是否已设置：

```powershell
$pwd = [Environment]::GetEnvironmentVariable("SMTP_PASSWORD", "User")
if ($pwd) { "SMTP_PASSWORD 已设置，长度：$($pwd.Length)" } else { "SMTP_PASSWORD 未设置" }
```

不要直接打印 `MIMO_API_KEY` 或 `SMTP_PASSWORD` 的完整内容。

## 定时任务

当前 Windows 计划任务名称是：

```text
Research Digest
```

当前计划：

```text
每周一 09:00 自动运行
```

查看任务：

```powershell
schtasks /Query /TN "Research Digest" /FO LIST /V
```

重新创建为每周一 09:00：

```powershell
schtasks /Create /F /SC WEEKLY /D MON /TN "Research Digest" /TR "cmd.exe /c cd /d C:\AI\codex\plug_skill && python -m research_digest run --config C:\AI\codex\plug_skill\config.toml" /ST 09:00
```

如果想改成每天 08:30，可以运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1 -ConfigPath C:\AI\codex\plug_skill\config.toml -At 08:30
```

## 修改关键词

编辑 [config.toml](C:/AI/codex/plug_skill/config.toml)：

```toml
[profile]
keywords = [
  "gas detector",
  "gas photodetector",
  "RPC",
  "Resistive Plate Chamber",
  "Low pressure gas detector",
  "MPGD",
  "Micromegas"
]
```

如果遇到无关结果，可以加入排除词：

```toml
exclude_keywords = [
  "market analysis",
  "industrial safety",
  "remote procedure call"
]
```

## 添加重点会议页面

如果发现某个会议没有被 Conference Alerts 或 WikiCFP 收录，可以手动加入：

```toml
[[sources.watched_pages.pages]]
title = "会议名称"
url = "https://example.org/conference"
kind = "conference"
source = "Official Site"
venue = "地点"
date = "2026-09-14"
summary = "这个会议为什么重要，以及程序页、注册页等说明。"
```

建议优先添加 Indico、官方 program、timetable、scientific program 页面。

## 添加 RSS 源

如果某个期刊、实验室、会议或机构提供 RSS/Atom，可以打开 RSS：

```toml
[sources.rss]
enabled = true

[[sources.rss.feeds]]
name = "Example Journal"
url = "https://example.com/rss"
kind = "paper"
max_results = 8
```

## 添加 Google 官方搜索

项目支持 Google 官方 Custom Search JSON API。它不是直接爬 Google 搜索页面，而是使用官方 JSON API。

需要两个本机用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("GOOGLE_SEARCH_API_KEY", "你的 Google API key", "User")
[Environment]::SetEnvironmentVariable("GOOGLE_SEARCH_CX", "你的 Programmable Search Engine ID", "User")
```

配置位置：

```toml
[sources.google_search]
enabled = true
api_key_env = "GOOGLE_SEARCH_API_KEY"
cx_env = "GOOGLE_SEARCH_CX"
max_results = 20
results_per_query = 5
kind = "feed"
queries = [
  "\"MPGD\" Micromegas detector",
  "\"Resistive Plate Chamber\" detector",
  "\"gaseous detector\" \"JINST\"",
  "\"Micromegas\" \"Nuclear Instruments and Methods\""
]
```

如果运行时报 `This project does not have the access to Custom Search JSON API`，需要在 Google Cloud Console 中启用 `Custom Search API`，并确认 API key 没有限制错 API。

## 常用命令速查

正式运行并发送邮件：

```powershell
python -m research_digest run --config config.toml
```

预览最近 30 天，不发邮件：

```powershell
python -m research_digest run --config config.toml --dry-run --ignore-state
```

发送最近 100 天：

```powershell
python -m research_digest run --config config.toml --since-days 100 --ignore-state
```

发送最近 1 年：

```powershell
python -m research_digest run --config config.toml --since-days 365 --ignore-state
```

测试邮箱：

```powershell
python -m research_digest send-test --config config.toml
```

运行单元测试：

```powershell
python -m unittest discover -s tests -v
```

## 注意事项

- API key 和邮箱客户端专用密码不要写进 `config.toml`。
- 如果换了 PowerShell 窗口后环境变量未生效，重新打开 PowerShell。
- 通用会议源可能漏掉专业会议，重要会议建议加入 `watched_pages`。
- Google News 对“gas detector”容易搜到工业安全和市场报告，可通过 `exclude_keywords` 降噪。
- MiMo Token Plan 偶尔响应较慢，当前已设置 `timeout_seconds = 120`。
