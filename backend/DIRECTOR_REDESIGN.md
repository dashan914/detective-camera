# 侦探相机导演台候选版

项目主入口为侦探拍摄，手动导演用于编写虚构案件。诗歌和插画保留为附属创作。现有设备认证、相机设置、诗票渲染和打印协议保持兼容。

## 手动案件接口

复用 `POST /api/admin/jobs`（原管理员认证）。

- `mode: "manual"`，`output_mode: "detective"`
- `detective_result` 使用现有侦探 JSON 契约：案件名、3–4 条观察线索、关键证据、推测。
- `preview_only: true` 只生成预览，不加入队列、不调用 AI。
- 提交时生成 `raster_print`，复用现有 ESP32 位图打印流程。
- `print_image` 默认关闭；开启需同时设 `use_latest_photo: true`，服务端把最近照片处理并嵌入任务，避免后续拍照替换已排队图片。
- `show_key_evidence` 默认开启；`time`、`location` 可填写。

## 验收边界

使用隔离本机数据验证，不调用真实 AI、不触发真实设备打印。
接口测试覆盖手动预览、队列、字段校验、认证、照片快照及原诗歌流程。
生产部署须使用已核实的服务器访问方式；不得覆盖 `.env`、运行状态或照片。
