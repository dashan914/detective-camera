# 侦探相机网页演示

静态、可独立部署的演示，不连接设备，不采集或上传观众照片，不调用 AI。
示例案件用于展示真实产品的交互顺序：快门、观察语音、屏幕思考表情、形成推测、打印案卷。
点击机身快门或按钮均可开始；提供声音开关、字幕、跳过等待、阅读案卷和减少动态效果支持。

```sh
npm ci
node build.mjs
python3 -m http.server 8894 --bind 127.0.0.1
```

浏览器打开 `http://127.0.0.1:8894`。

发布文件：`index.html`、`style.css`、`detective.css`、`detective.js`、
`DASHAN_V33.glb`、`CourierPrime-Regular.ttf`、`CourierPrime-LICENSE.txt`、
`screen-frames/`、`draco/` 与 `audio/`。三维模型由现有 V33 装配导出，屏幕嵌在实际顶部开口，
未额外添加屏幕支架。网页 GLB 用于可视化，不作为打印文件。

屏幕动画由 `generate_screen_frames.py` 直接编译固件 `DetectiveDisplay.cpp` 绘图函数生成，
保留原有侦探造型、眨眼、嘴型、观察/思考/打印状态。待命展示固件取景框，
不嵌入私人相机实时照片；减少动态效果时使用静态帧。

`index.template.html` 为页面源文件；`viewer.js` 与 `ritual.js` 为三维交互源码。
`detective.js` 保存项目介绍和示例案卷；`build.mjs` 输出内嵌三维脚本的页面。
快门与等待语音由使用者提供；`audio/clothes-case-clean.mp3` 是通过项目已有朗读 API
生成的已确认三句推理，约 8.93 秒。已去除中间非对白人声，保留自然停顿。
出纸进度跟随音频，字幕与纸条使用同一份推理文字；API Key 和音色 ID 不进入网页。

只发布四个使用中的音频（`01_shutter.mp3`、`05_wait.mp3`、`report.mp3`、
`clothes-case-clean.mp3`）。不要发布整个仓库，尤其不要把后端目录映射为静态站点。
部署在子路径时保留相对资源路径，详见 `../docs/RESTORE.md`。

## 可选再生成

`generate_case_narration.py` 从 `--backend-dir` 指定的本地 `.env` 读取已有密钥与音色配置，
只生成已确认的整段或单句，不创建音色。运行会调用外部服务；备份、构建和测试不会自动调用。
`export_assembly.py` 从仓库内脱敏装配导出网页 GLB，需 Blender 并关闭自动执行脚本。
`generate_screen_frames.py` 从固件绘图函数生成 288 帧，需 Python、Pillow 与 clang++。

## 浏览器测试

安装 Playwright 后，启动本地静态服务器，再运行 `node verify.cjs`。
支持 `PLAYWRIGHT_MODULE`、`CHROME_PATH`、`DEMO_URL` 环境变量。
测试覆盖顶部实际屏幕、27 件模型、完整朗读与出纸同步、字幕边界、移动端和减少动态效果。
