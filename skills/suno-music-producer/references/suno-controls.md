# Suno 控制参考

产品能力、套餐与界面会变化。重要制作或商业发布前，以当前账户 UI 和 Suno 官方说明为准。

## 字段边界

- `Styles` 写全曲稳定身份与发展：音乐坐标、脉冲、前景动作、人声行为、空间和动态弧线。
- `Lyrics` 写唱词、结构地图和少量局部变化。结构标签以外的方向都是概率性提示。
- `Exclude Styles` 保持短而具体，不把否定句塞进 Lyrics。
- 纯音乐使用 Instrumental；不要用歌词区的描述散文代替它。

## 参数起点

Creative Sliders 没有通用最优值。按本曲的风险选择一个起点：

- 干净、顺耳、服从当前 Styles：Weirdness 28%，Style Influence 75%。
- 平衡探索：Weirdness 40%，Style Influence 80%。
- 更开放的草图可提高 Weirdness 或降低 Style Influence，但每轮只动一个主变量。
- 已有 demo、旋律或本人 Voice：先保护最不可替换的资产，再逐步调整 Audio Influence。

## 资产与编辑

- Audio Upload 可承载哼唱、清唱、和弦、律动或完整自有作品。
- Voice 用于本人歌声身份；Persona 保存单曲特征；Custom Model 用于有足够自有曲目的长期声音世界。以账户当前可用功能为准。
- 错词或局部旋律优先 Replace Section/Alternate；段落顺序和长度用 Song Editor/Studio；结构与表演锁定后才考虑 Remaster。
- 需要复现时，在回复中列出最终 Styles、Lyrics、参数、模型与生成日期。

只使用自己有权使用的歌词、录音、声音、采样和训练材料。商业使用条件与著作权资格不是同一件事。
