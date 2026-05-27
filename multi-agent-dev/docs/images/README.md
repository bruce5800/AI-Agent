# Demo GIFs / Screenshots

README.md 里引用的图片资源放这里。每张 GIF 的录制建议：

| 文件名 | 应展示的内容 | 时长建议 |
|--------|------------|--------|
| `hero-demo.gif` | 顶部 banner —— 从输入需求到项目生成的完整流程（PM → Architect → Programmer → Reviewer → 气球）。**整体感**最重要，可以加速 2-4 倍。 | 10-15s |
| `feature-bus-escalation.gif` | Reviewer 升级到 PM 的非线性边。**屏幕一半**展示 chat 流，**另一半**展示 audit log 里出现 `Reviewer → PM (escalation)` 这条边。 | 8s |
| `feature-worktree.gif` | fix-loop 中 worktree 的生命周期：`🌿 进入 fix 模式` → 在 worktree 内 commit → `✅ 合并 fix worktree` 或 `🗑️ 丢弃`。可以同时开终端跑 `git log --oneline --all --graph` 展示分支可视化。 | 12s |
| `feature-todos.gif` | sidebar 进度面板。Programmer 写 3-5 个文件，每个文件开始时对应 todo 变 🔄，结束时变 ✅。**焦点是 sidebar 而不是 chat**。 | 10s |
| `feature-edit-approval.gif` | 审批门：展开 expander → 在 text_area 改一行 → 点击「✏️ 修改后通过」→ 看到 `📝 用户编辑了 design.md` 提示 → workspace 里 design.md 真的被改了。 | 8s |
| `feature-streaming.gif` | token 级流式 + tool call 展开。可以 split 屏：左边 Programmer 流式输出，右边一个 200KB 的 read_file 结果点开 expander。 | 10s |

## 录制建议

**工具**：
- macOS：[Kap](https://getkap.co/)（免费）或 [CleanShot X](https://cleanshot.com/)
- 全平台：[OBS Studio](https://obsproject.com/) + ffmpeg 转 GIF

**参数**：
- 分辨率：1280×800 或 1280×720（README 默认渲染宽度约 800px，再大没用）
- 帧率：15-20fps（GIF 不要太大，要在 GitHub 上跑得动）
- 文件大小：每个 < 5MB（GitHub 显示阈值）
- 颜色：256 色调色板（GIF 标准）

**ffmpeg 转 GIF 参考命令**：

```bash
# 用 palette 让色彩更准
ffmpeg -i input.mov -vf "fps=15,scale=1280:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i input.mov -i palette.png -filter_complex \
  "fps=15,scale=1280:-1:flags=lanczos[x];[x][1:v]paletteuse" output.gif
```
