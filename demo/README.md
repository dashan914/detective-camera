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
音频由项目使用者提供，不包含其他语音包、私密照片或运行状态。
