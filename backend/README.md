# DASHAN 诗歌相机后端与导演台

这个目录包含一个仅使用 Python 标准库的本地后端。AI 配置、任务队列、设备心跳和历史保存在本地 JSON 状态文件中，API Key 不会返回给网页或 ESP32。

## 启动

先复制 .env.example 为 .env，设置 CAMERA_SHARED_TOKEN 和 DASHAN_ADMIN_TOKEN。然后运行：

    python3 server.py

打开 http://127.0.0.1:8787/director。Basic Auth 用户名固定为 admin，密码为 DASHAN_ADMIN_TOKEN。

状态文件默认是 director_state.json，可用 DASHAN_DATA_FILE 指向其他位置。不要把服务端口公开到互联网。

## 导演台功能

- 手动导演：输入 title / author / body / source / original / translation / date
- 拍照模式：将 photo_capture 请求加入 ESP32 轮询队列
- 固定票面契约：template_id / title / author / body / source / original / translation / date
- 结构化票面预览 HTML；预览与任务使用同一份 ticket
- 多套 OpenAI、DeepSeek 或自定义 OpenAI Chat Completions 兼容配置
- 接口地址、模型名、Key 可编辑；模型名不写死
- 测试连接、启用配置；网页只显示 Key 是否已保存
- 设备在线状态、任务状态和最近任务历史

## 管理接口

所有 /api/admin/* 需要 Basic Auth 或 X-Dashan-Admin。

- GET /api/admin/state
- GET /api/admin/providers
- GET /api/admin/history
- POST /api/admin/providers：{id,name,base_url,model,api_key}
- POST /api/admin/providers/activate：{id}
- POST /api/admin/providers/test：测试当前表单配置
- POST /api/admin/jobs：手动任务或 {mode:"photo"}，preview_only:true 只预览

## ESP32 接口

所有设备接口需要 X-Dashan-Token。

- POST /api/camera：原始 JPEG，返回 {ticket, preview_html}
- GET /api/device/jobs/next：返回 204，或 {job_id,type,ticket}
- GET /api/device/jobs/{job_id}/print-data：返回按 MY-628 官方 `GS v 0` 封装的 384 点光栅数据
- POST /api/device/jobs/{job_id}/complete：{status:"completed|failed|cancelled|awaiting_raster",detail}
- POST /api/device/heartbeat：接受 device_id / ip / rssi / firmware / printer / camera / mode

服务器使用朱雀仿宋和 Courier Prime 将 ticket 渲染成 384 点黑白位图，再按 MY-628 官方 `GS v 0` 命令发给设备。ESP32 不需要内置中文字库。

## 验证

    python3 -m unittest -v test_server.py

测试覆盖 Basic 鉴权、Key 脱敏、手动队列领取与完成、拍照任务预览、XSS 逃逸和设备心跳。
