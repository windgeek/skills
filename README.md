# skills

Open-source [Claude Code](https://claude.com/claude-code) skills. / 开源的 Claude Code 技能。

| Skill | What it does |
|---|---|
| [`voice-clone`](skills/voice-clone/) | Clone your own voice locally on a Mac (Apple Silicon) with CosyVoice3 and generate Chinese / mixed Chinese-English narration. / 在 Mac 本地复刻你自己的声音，生成中文（及中英混合）配音。 |

## voice-clone

**English.** A skill that walks Claude through the whole local voice-cloning workflow: installing the environment, coaching you through recording a 10–20 s sample, checking and registering the sample, generating narration sentence by sentence, picking between takes, fixing mispronounced characters, and reminding you about AI-content disclosure. Everything runs on your machine; no audio leaves it. `references/troubleshooting.md` records real pitfalls hit on Apple Silicon.

**中文。** 让 Claude 带你走完本地声音复刻的全流程：装环境、指导录音、体检并登记样本、按句生成配音、多版本挑选、多音字纠音、AI 生成内容声明提醒。全部在本机运行，音频不上传。`references/troubleshooting.md` 里记录了在 Apple 芯片上真实踩过的坑。

### Install / 安装
As a plugin marketplace (recommended) / 通过插件市场安装（推荐）:
```
/plugin marketplace add windgeek/skills
/plugin install voice-clone@windgeek-skills
```
Or copy manually / 或手动复制:
```bash
git clone https://github.com/windgeek/skills.git
cp -R skills/skills/voice-clone ~/.claude/skills/
```
Then tell Claude: "用我的声音配音" / "clone my voice". Claude will explain what needs downloading and ask before installing.

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
