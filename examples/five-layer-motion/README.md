# Five-layer motion reference

这是 Paper Cut 的 20 秒可编辑参考工程，用于证明画面不是只做整图缩放，而是由五个原图派生纸片层完成组装、炸开、碰撞、重新落版和视差运动。

## 运行

```bash
npm install
npm run preview
```

## 验证与渲染

```bash
npm run check
npm run render
```

关键文件：

- `index.html`：可编辑 HyperFrames / GSAP 时间线。
- `assets/originals/scene-01-hero.png`：获批 hero frame。
- `assets/processed/`：从 hero frame 本地派生的纸片层。
- `storyboard.md`：20 秒运动设计。
- `assets-manifest.json`：素材来源、哈希和处理记录。
- `qa/QA.md`：项目、运动和编码验收结果。
- `renders/paper-cut-layer-demo-20s-motion-v2.mp4`：20 秒无声参考成片。

本示例没有调用视频模型、GIF 生成模型或任何静默 provider 切换。README GIF 由这条 MP4 使用 FFmpeg 本地转码产生。

注意：`scripts/make_demo_assets.py` 中的几何掩码坐标（ellipse、polygon 等）与随附的 `assets/originals/scene-01-hero.png` 尺寸和构图硬绑定，仅用于从这张 hero frame 复现派生层；换成自己的图片前必须先按新图调整掩码坐标，否则会静默错位。
