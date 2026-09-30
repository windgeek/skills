# Adding a skill / 新增 skill

1. 放进 `skills/<name>/`（必须有 `SKILL.md`，frontmatter 的 `name` 与文件夹同名）。
2. 在 `skills.json` 写中英各一句话。
3. 在 `README.md` 加一个 `## <name>` 小节（保持简短）。
4. 提交。pre-commit 钩子会运行 `python3 scripts/sync.py`：自动重新生成 README 的 skill 表和 `.claude-plugin/marketplace.json`，并扫描本机路径、邮箱、密钥等私人信息；缺任何一步都会拦住提交。

克隆后启用钩子：`git config core.hooksPath .githooks`。可选：在本地建一个 git 忽略的 `.privacy-terms`，每行一个不能公开的词（自己的名字、歌名等），扫描会一并检查。

`.claude-plugin/marketplace.json` 供支持 Claude Code 插件市场的用户使用，属于可选项，由脚本自动维护。
