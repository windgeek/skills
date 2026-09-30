# skills

Open-source Agent Skills (`SKILL.md` format) for any AI coding agent. / 开源的 Agent Skills（`SKILL.md` 格式），适用于各类 AI 编程智能体。

Each skill is a self-contained folder under [`skills/`](skills/). Any agent that supports the Agent Skills format can use them; Claude Code users can also install via the plugin marketplace.
每个 skill 都是 `skills/` 下自包含的文件夹，支持 Agent Skills 格式的智能体都能用；Claude Code 用户还可以走插件市场安装。

| Skill | What it does |
|---|---|
| [`voice-clone`](skills/voice-clone/) | Clone your own voice locally on a Mac (Apple Silicon) with CosyVoice3 and generate Chinese / mixed Chinese-English narration. / 在 Mac 本地复刻你自己的声音，生成中文（及中英混合）配音。 |

## voice-clone

**English.** A skill that walks the agent through the whole local voice-cloning workflow: installing the environment, coaching you through recording a 10–20 s sample, checking and registering the sample, generating narration sentence by sentence, picking between takes, fixing mispronounced characters, and reminding you about AI-content disclosure. Everything runs on your machine; no audio leaves it. `references/troubleshooting.md` records real pitfalls hit on Apple Silicon.

**中文。** 让智能体带你走完本地声音复刻的全流程：装环境、指导录音、体检并登记样本、按句生成配音、多版本挑选、多音字纠音、AI 生成内容声明提醒。全部在本机运行，音频不上传。`references/troubleshooting.md` 里记录了在 Apple 芯片上真实踩过的坑。

### Install / 安装
Claude Code — plugin marketplace / 插件市场:
```
/plugin marketplace add windgeek/skills
/plugin install voice-clone@windgeek-skills
```
Any agent — copy the folder into your agent's skills directory (e.g. `~/.claude/skills/` for Claude Code; check your agent's docs for its path) / 其他智能体：把文件夹复制到该智能体的 skills 目录（路径见各自文档）:
```bash
git clone https://github.com/windgeek/skills.git
cp -R skills/skills/voice-clone ~/.claude/skills/
```
Then tell your agent: "用我的声音配音" / "clone my voice". The agent will explain what needs downloading and ask before installing.

### What gets downloaded / 会下载什么
Nothing is bundled here. On first run `scripts/setup.sh` (after your consent) fetches:
- [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) code (Apache-2.0) from GitHub
- Fun-CosyVoice3-0.5B model (~7.4 GB) from ModelScope — check its license before commercial use
- Python dependencies (~2–3 GB) into an isolated conda env, from conda-forge/PyPI

### Responsible use / 负责任地使用
Only clone **your own voice**, or a voice whose owner has given you explicit permission. Do not imitate celebrities or other people. Label published content as AI-generated as required by your platform and local regulations (e.g. China's 《人工智能生成合成内容标识办法》, in force since Sept 2025).
只复刻本人或已获明确授权的声音，不要模仿名人或他人；发布时按平台和当地法规标注“AI 生成内容”。

### Requirements / 环境
macOS on Apple Silicon, conda (miniconda), git, ~15 GB free disk.

## License
MIT — see [LICENSE](LICENSE). Third-party components keep their own licenses.
