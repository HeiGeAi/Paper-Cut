# QA evidence

- Project validation：valid，1 scene，8 assets。
- HyperFrames lint：0 errors，0 warnings。
- HyperFrames check：`ok: true`。
- Runtime：0 errors。
- Layout：0 issues。
- Motion sidecar：0 errors，300 samples。
- Contrast：26/26 passed。
- Animation map：48 个有效动画段；箭头和圆片各有 6 段独立轨迹。
- Encoded MP4：H.264，1920×1080，30fps，600 frames，20.000s，video-only。
- MP4 SHA-256：`192cc9812c2a5d4a3aa53febed5257f1bef4468e5d6979dd22c65306bb80a769`。
- Black-frame detection：没有检测到黑帧区间。
- Freeze detection：没有检测到持续 2 秒及以上的冻结区间。
- Visual evidence：`contact-sheet-1.jpg`、`contact-sheet-2.jpg`。

这是 Gate 3 draft preview。五个运动层全部从获批 hero frame 本地派生，运动由 HTML、CSS、GSAP 和 HyperFrames 确定性生成。
