# 隐私与公开版本边界

本项目按可参赛、可复现的开源结构整理，目前 GitHub 仓库仍保持私有，不启用 Pages、不自动发布、不改变线上站点。许可方案见 `../NOTICE.md`。

保留：源代码、提示词与字段结构、合成测试、静态展示、脱敏 CAD、27 个 STL、第三方声明与复现文档。私有归档还保留历史试验语音，但它们不属于公开版本的授权素材。

排除：`.env`、Wi-Fi 配置、服务器私钥/IP、令牌/密码/API Key、私人音色 ID、聊天记录、原始实拍照片、导演台历史、动态案件音频、源配音/调试录音、设备 Flash/NVS/FFat 镜像和构建缓存。

密钥与生产状态仍在原环境中，整理不删除使用者原资料。恢复需重新填写配置；GitHub 不能替代密钥管理器或设备数据备份。

## 真实照片如何流转

真实设备会把 JPEG 上传至所配置的后端，再发送到配置的模型服务。后端保留最近照片、预览、任务状态与可选语音；不是「全部在设备本地计算」。只有经授权的照片才能用于 API 测试、演示视频或提交比赛。不得因去掉文件名/EXIF 就认为人像、住址和屏幕内容已经匿名。

## 检查工具

`tools/privacy_check.py` 可检查当前文件、Git 历史和本地已知密钥，只输出文件名及分类，不输出匹配内容。自动扫描不能代替照片、声音和权利的人工确认。

```sh
python3 tools/privacy_check.py --history
python3 tools/privacy_check.py --history --secret-env /path/to/private/.env
python3 tools/backup_manifest.py
```

## 私有仓库不等于公开包

历史提交已经包含试验 MP3。以后不得通过直接把本仓库可见性改为 public 来发布。应使用 `tools/public_release_check.py` 核对排除清单、素材授权和未完成事项，再从核验后的文件导出一个**不带 `.git` 历史**的版本。现在不会执行公开发布，详见 `RELEASE_CHECKLIST.md`。
