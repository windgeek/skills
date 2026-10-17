# 各生态的缓存与产物

每项写：在哪、能不能删、删了的代价、要留什么。路径以 macOS 为主，Linux / Windows 的对应位置在括号里。

## Xcode / Apple 平台

| 位置 | 判断 |
|---|---|
| `~/Library/Developer/Xcode/DerivedData` | 编译缓存，可整体删。首次编译变慢；先关掉 Xcode |
| `~/Library/Developer/Xcode/Archives` | 每次 Archive 一个 `.xcarchive`，带 dSYM。**保留实际提交 / 发布的版本**，同版本号下没提交的构建和被替换的旧 build 可删。版本号读 `Info.plist` 的 `ApplicationProperties:CFBundleShortVersionString` 和 `CFBundleVersion` |
| Archive 的两个坑 | 文件夹名在 AM/PM 前是窄不换行空格，路径用通配符或 Tab 补全，不要手打。`.xcarchive` 里带着正式 bundle ID 的 app，放进废纸篓后还可能被 LaunchServices 登记，造成同名 app 冲突（见 ship-macos-apps），所以 Archive 是“优先进废纸篓”的例外：确认后直接删，或进废纸篓后马上清空 |
| `~/Library/Developer/Xcode/iOS DeviceSupport`（及 watchOS、macOS） | 连真机时从设备拷来的符号。可删，下次连接时重新拷，要几分钟；已不再用的系统版本优先删 |
| `~/Library/Developer/CoreSimulator/Devices` | 模拟器，**复用环境，默认保留**。只删不再用的机型；`xcrun simctl delete unavailable` 清掉运行时已卸载的设备 |
| 模拟器运行时（`xcrun simctl runtime list`） | 每个几 GB。不再测试的旧系统版本可以 `xcrun simctl runtime delete <id>`，先问用户 |
| `~/Library/Caches/com.apple.dt.Xcode` | 可删 |
| 项目里的 `*.pkg`、导出的 `.app`、截图和海报旧版本 | 被取代就可删；先确认当前版本的产物齐全、当前脚本不引用 |

## Node / 前端

| 位置 | 判断 |
|---|---|
| 项目 `node_modules` | 可删，`npm ci` / `pnpm install` 重建。长期不碰的项目最值得删 |
| `dist/`、`build/`、`.next/`、`.nuxt/`、`.turbo/`、`.parcel-cache/`、`.vite/` | 构建产物，可删 |
| `~/.npm/_cacache`、`~/Library/pnpm/store`（`~/.local/share/pnpm/store`）、`~/Library/Caches/Yarn` | 全局下载缓存，可用 `npm cache clean --force`、`pnpm store prune`、`yarn cache clean` |

## Python

| 位置 | 判断 |
|---|---|
| `__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/` | 可删 |
| `.venv/`、`venv/` | 可重建，但要确认有 `requirements.txt` / `pyproject.toml` / lock 文件能还原 |
| `~/Library/Caches/pip`（`~/.cache/pip`）、`~/.cache/uv` | `pip cache purge`、`uv cache clean` |
| `~/.cache/huggingface`、模型权重目录 | 往往几十 GB，**重新下载代价大**，列给用户决定 |

## Rust / Go / JVM / Android

| 位置 | 判断 |
|---|---|
| Rust 项目 `target/` | 可删，`cargo clean` |
| `~/.cargo/registry` | 可清，重新下载依赖 |
| Go `~/Library/Caches/go-build`（`~/.cache/go-build`） | `go clean -cache` |
| `~/.gradle/caches`、项目 `build/`、`.gradle/` | 可删，重建慢 |
| `~/.android/avd` | 安卓模拟器，同 iOS 模拟器：复用环境，只删不再用的 |

## Docker

`docker system df` 先看占用。`docker system prune` 删停止的容器、悬空镜像和构建缓存；加 `-a` 会删所有没在用的镜像，加 `--volumes` 会删数据卷（**可能是数据库数据**），这两个都要单独问用户。

## 零碎垃圾

- `.DS_Store`、`Thumbs.db`：可删（`find . -name .DS_Store -not -path './.git/*' -delete`）。
- 根目录名字奇怪的文件（`:-`、`-`、`=`、`nohup.out`）：多是命令行重定向写错生成的，先看内容再删。
- 日志、临时导出、`*.tmp`、`*.orig`、`*.rej`：确认不是正在用的再删。
