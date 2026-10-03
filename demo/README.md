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
`DASHAN_V1_2_2.glb`、`CourierPrime-Regular.ttf`、`CourierPrime-LICENSE.txt`、
`camera-preview.jpg` 与 `audio/`。三维模型为已有外观示意，上方屏幕为演示层，
不代表可直接打印的机械结构。

`index.template.html` 为页面源文件；`viewer.js` 与 `ritual.js` 为三维交互源码。
`detective.js` 保存项目介绍和示例案卷；`build.mjs` 输出内嵌三维脚本的页面。
音频由项目使用者提供，不包含其他语音包、私密照片或运行状态。
