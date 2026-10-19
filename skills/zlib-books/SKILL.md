---
name: zlib-books
description: 用 zlib 命令行在 Z-Library 搜书、下载电子书，并推送到 Kindle。凡是用户说“找本书 / 下载这本书 / 搜一下某某的书 / 帮我弄到 Kindle 上 / 推送到 Kindle / 看看今天下载额度 / 下载记录”，或给出书名、作者想读电子书，都应使用本 skill，即使没提 zlib 或 Z-Library。
---

# zlib-books：搜书、下载、推 Kindle

依赖本机已安装并登录的 `zlib` 命令行（`brew install heartleo/tap/zlib`，登录由用户自己在终端完成）。

## 铁律

- **不输入密码**：登录、Kindle 的 SMTP 密码都让用户自己在终端做，不要写进对话或文件。不要用 `--password`。
- **下载前先确认**：搜索后列出候选，用户选定再下载。每个账号每天只有约 10 次下载额度，不要试探性下载。
- 只用于用户有权获取的书。cookie、`~/.config/zlib/` 下的内容都是凭证，不展示、不提交。

## 流程

### 1. 先检查状态（每次会话第一次用时）

```bash
zlib profile --json
```

- 报未登录或会话过期：请用户在终端运行 `zlib login --domain https://z-lib.gl`，然后停下等待。
- 额度为 0：告诉用户今天用完了，不再下载。

### 2. 搜索

```bash
zlib search "书名 作者" --ext epub --language chinese --order popular --json > 结果.json
```

- 输出先存成文件再解析，直接管道给 Python 偶尔会解析失败。
- 默认只搜 epub（Kindle 现在不再接收 MOBI）。用户要 pdf 再加 `--ext pdf`。
- 可用参数：`--language`（chinese / english 等）、`--from-year`、`--to-year`、`--exact`（精确匹配）、`-n` 每页条数、`-p` 页码。
- `--order` 可选 `popular`（按热度）、`bestmatch`（默认相关度）、`date`、`year`、`filesize`。**找经典书时优先 `popular`，再按相关度对照一遍**，两边都靠前的更可靠。
- zlib 没有分级分类榜单，能用来判断“精品”的只有 JSON 里的 `rating`（评分）、`quality`（文件质量分），再加上 `--order popular` 的热度排序。

### 挑“精品”的规则

按优先级排：
1. **单本优先**：书名里带“套装、系列、三部曲、合集、全集、N册”的是合集，除非用户要合集，否则剔除。合集体积大、目录乱，Kindle 上不好读。
2. **`quality` 和 `rating` 高的靠前**；评分为 0 或空表示没人评，不代表差，但排在有高分的后面。
3. **正规出版社版本优先**：`publisher` 有出版社、有年份、有译者的，好过无出版信息的。书名里塞满宣传语的多半是商家整理版，次选。
4. **体积要合理**：纯文字小说 epub 一般几百 KB 到几 MB。几十 KB 可能是节选或样章，几十 MB 多半带大图或是合集。
5. 同一本书有多种格式时选 epub。

从 JSON 里取 `id`（形如 `11735659:7659fb`）、`name`、`authors`、`publisher`、`year`、`language`、`extension`、`size`、`rating`、`quality`。
挑最多 5 条，用表格给用户：序号、书名、作者、出版社、年份、格式、大小、评分/质量，并标出你推荐的那一条和理由。
- 没结果时换关键词重试一次（去掉副标题、只留作者姓名、换中英文书名），再没有就如实告诉用户。

### 3. 下载

```bash
zlib download "<id:hash>" --dir "${ZLIB_DOWNLOAD_DIR:-$HOME/Books}"
```

- 默认目录取环境变量 `ZLIB_DOWNLOAD_DIR`，没设就用 `$HOME/Books`，不存在先创建。用户指定了目录就用用户的。
- id 必须是完整的 `id:hash`。
- 下载完用 `ls -lh` 确认文件存在，告诉用户路径和大小。
- 一次只下载用户明确选中的书。

### 4. 推送 Kindle

先确认已配置：`~/.config/zlib/` 下有 Kindle 配置，且环境变量 `ZLIB_SMTP_PWD` 已设置。没配置就让用户在终端运行 `zlib kindle config` 并自行设置 SMTP 密码，同时提醒要在亚马逊“内容和设备 → 偏好设置 → 个人文档设置”里把发件邮箱加入认可列表。

- **推送一律用本 skill 自带脚本，不用 zlib 自带的发信**（`--send-to-kindle`、`kindle send` 在 0.0.9 上报 “network request failed”，某台机器上 Python 直连 SMTP 正常而 zlib 失败，问题出在 zlib 自身）：
  先 `zlib download` 下载，再
  `python3 -I <本 skill 目录>/scripts/send_kindle.py "<文件路径>"`
- 脚本读 `kindle.json` 和 `.env` 里的授权码，不打印密码；附件名自动转 ASCII，避免被亚马逊拒收；认证失败、格式不支持等都会给出明确提示。
- Kindle 支持 EPUB、PDF、TXT、DOC、DOCX、RTF、HTML。MOBI 和 AZW3 不在列表里（zlib 自己也拒绝 .mobi），别推。
- 推送成功只代表邮件发出，Kindle 上同步通常要几分钟，如实说明。

### 5. 其他

- 下载记录：`zlib history --json`；重新下载：`zlib history --download "<id:hash>" --dir ...`
- 额度：`zlib profile --json`

## 故障排查

| 现象 | 处理 |
|---|---|
| 连不上、超时、返回 challenge 页面 | `zlib doctor --eapi` 看哪个镜像可用，让用户把 `ZLIB_DOMAIN` 改成可用域名；国内网络再设 `ZLIB_PROXY` |
| 搜索突然报登录失败 | 会话过期，让用户重新 `zlib login` |
| 改了域名仍连旧镜像 | `echo "$ZLIB_DOMAIN"` 检查环境变量或工作目录 `.env` 里有没有残留旧值 |
| 脚本报 SMTP 认证失败 | 授权码错或失效，让用户在邮箱网页重新生成，自己写入 `~/.config/zlib/.env` |
| 脚本发送成功但 Kindle 没收到 | 查发件邮箱是否在亚马逊“已认可的发件人”列表里；再等几分钟；仍没有就看亚马逊的垃圾邮件或拒收通知。不要重新下载，额度有限 |
| 下载中断 | 工具会自动重试，仍失败就换一个版本，不要反复重下浪费额度 |

当前已知可用镜像（2026-10 实测）：`z-lib.gl`、`zlib.bz`。镜像经常变，以 `zlib doctor --eapi` 为准。

## 汇报格式

完成后用一两句话说：书名、格式、保存路径、是否已推送 Kindle、今天剩余额度。
