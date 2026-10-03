# Detective Camera / 侦探相机

《侦探相机》是一台由 AI 驱动的互动创作相机。

用户按下快门后，它会拍下眼前场景，识别照片中的物件与细节，并以这些真实线索为基础，虚构一桩有逻辑、有趣味的微型案件。相机通过屏幕表情、侦探式语音和热敏打印机完成“观察—思考—推理—出案卷”的完整体验，让一张普通照片变成一份可带走的侦探报告。

它不试图判断现实中的真相，而是把日常生活中被忽略的物件，转化为一场轻盈、可信、充满想象力的推理游戏。

侦探相机想讨论的是：当 AI 成为创作搭档后，技术门槛不再只意味着限制；每个人都可以把一个看似天马行空的想法，做成能拍照、会思考、能说话，也能吐出纸质案卷的真实物件。

## 目录

- `firmware/`：ESP32-S3 设备端，包含相机、导演台通信、MY-628 打印、ES8311 音频和屏幕界面。
- `backend/`：Python 后端与网页导演台，负责设备队列、AI 分析和票据渲染。
- `voice_pack_12/`：12 条分阶段语音与出报告语音，不包含整盘镜像。
- `demo/`：独立的网页交互演示，含上方屏幕、思考语音和案卷出纸动画；不连接实机。

## 隐私与配置

仓库不包含 Wi-Fi、服务器地址、设备令牌、管理员密码、API Key、实拍照片或运行状态。复制 `backend/.env.example` 为 `backend/.env` 后填写自己的配置。设备首次启动时进入配网页面，由使用者填写 Wi-Fi、后端地址和设备令牌；配置保存在 ESP32 NVS 中。

## 启动后端

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
cd backend
python3 server.py
```

浏览器打开 `http://127.0.0.1:8787/director`。管理员用户名为 `admin`，密码来自 `DASHAN_ADMIN_TOKEN`。

## 设备端

使用 Arduino ESP32 Core 3.3.7，目标为 ESP32-S3、16 MB Flash、8 MB OPI PSRAM。打开 `firmware/PoetryCameraDirector/PoetryCameraDirector.ino`。详细接线和配网方法见 `firmware/README.md`。

## 测试

```sh
cd backend
python3 -m unittest -v test_server.py test_detective.py test_detective_renderer.py test_case_voice.py
```

## 安全说明

AI Key 只保存在后端。设备接口使用 `X-Dashan-Token`，导演台使用独立管理员密码。部署到公网时应在前端增加 HTTPS、访问控制和请求大小限制。
