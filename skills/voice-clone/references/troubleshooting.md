# 安装与运行排障（Apple 芯片 macOS 上真实遇到过的问题）

| 现象 | 原因 | 处理 |
|---|---|---|
| `CondaToSNonInteractiveError: Terms of Service have not been accepted` | Anaconda 默认频道要求接受服务条款 | 用 `--override-channels -c conda-forge` 建环境（setup.sh 已这样做）。不要替用户执行 `conda tos accept` |
| 新建的环境里没有 `pip` | conda-forge 的最小 Python 不带 pip | `$PY -m ensurepip` |
| `openai-whisper` 构建失败，报 `No module named 'pkg_resources'` | 新版 setuptools 删除了 pkg_resources | 先装 `setuptools<70`，再 `--no-build-isolation` 安装 whisper |
| 运行时 `No module named 'pkg_resources'` | 安装 requirements 时 setuptools 被升级了 | 重新执行 `pip install "setuptools<70"` |
| `No module named 'gdown'` 或 `'pyworld'` | 这两个包会被 `cosyvoice.flow` / `dataset.processor` 间接 import，裁剪依赖时不能删 | 补装 `gdown==5.1.0 pyworld==0.3.4` |
| HuggingFace 连接超时，返回 000 | 国内网络 | 改用 ModelScope 下载（fetch_model.py 默认就是） |
| `SSL_ERROR_SYSCALL` 或 `Connection reset`，下载中断 | 网络抖动 | 重跑 fetch_model.py，支持断点续传和大小校验 |
| 加载时 `wetext/revisions` 反复报重试警告 | 文本规整组件每次联网检查更新 | 只是警告，有缓存时不影响使用；首次使用必须能联网 |
| `Cannot convert a MPS Tensor to float64` | 声码器的 F0 预测用 float64，MPS 不支持 | clone_tts.py 已把声码器留在 CPU，只把 LLM 和 flow 放到 MPS。**不要**把 F0 预测器强转成 float32，官方注释说它对精度敏感 |
| 启动即崩：`dlopen(... scipy/.../_spropack...so) ... __thread_bss has a zero-fill section type, but offset field is not zero` | macOS 27 的加载器更严格，拒绝 scipy 1.15.3 wheel 里 8 个 Fortran 扩展（optimize/_cobyla、integrate/_vode _dop _lsoda、sparse/linalg/_propack 四个）；Python 3.10 已没有更新的 scipy wheel | 征得用户同意后：先备份这几个 .so（例如到 `~/voice-clone/backup-scipy/`），把这些文件中 zero-fill 类节（`__thread_bss` 等）的 offset 字段清零，再 `codesign -f -s -` 重签；验证 svds(propack)/COBYLA/odeint 结果正确。改的是已安装库的二进制，**须先征得用户同意**；还原就把备份拷回去 |
| 生成很慢 | 这是正常速度：M5 上约为音频时长的 2.5 倍 | 整期放后台跑；只重做有问题的段（`--only`） |
| 后台 shell 长时间挂着“still working” | 用户的 `ls` 被别名成 `eza`，在非交互 shell 里可能卡住 | 命令里不要用 `ls`，改用 `find` 或 `/bin/ls` |

## 自检命令
```bash
~/miniconda3/envs/cosyvoice/bin/python -c "import torch, pkg_resources, gdown, pyworld, whisper; print(torch.__version__, torch.backends.mps.is_available())"
python3 scripts/fetch_model.py        # 模型不完整时会补齐，已完整时秒完
```
