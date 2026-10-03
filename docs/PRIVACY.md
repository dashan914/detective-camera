# 私有备份边界

本仓库仅用于私有归档，不公开仓库、不发布 GitHub Pages、不授予项目自有内容开源许可。

保留：源代码、提示词与结构定义、合成测试、最终语音素材、网页静态资产、可编辑脱敏 CAD、27 个 STL、第三方许可与恢复说明。

排除：`.env`、Wi-Fi 配置、服务器私钥/IP、令牌/密码/API Key、私人音色 ID、聊天记录、原始实拍照片、导演台历史、动态案件音频、源配音/调试录音、设备 Flash/NVS/FFat 镜像、构建缓存及旧重复版本。

密钥与生产状态仍在原环境中，本次只清理上传副本，不删除使用者原资料。恢复项目需重新填写配置；GitHub 不能替代密钥管理器或设备数据备份。

`tools/privacy_check.py` 检查文件名、常见凭据格式、个人路径、邮箱与已知私密值，可选择扫描全部 Git 历史。输出只含文件名和分类，不显示匹配内容。自动扫描不是绝对保证；上传新照片、音频或 CAD 前仍需人工确认内容和授权。

```sh
python3 tools/privacy_check.py --history
# 在本地检查已有密钥是否误入仓库；不保存或输出密钥：
python3 tools/privacy_check.py --history --secret-env /path/to/private/.env
python3 tools/backup_manifest.py
```

最终 MP3 属于项目使用者提供/已配置音色生成的素材；第三方音色的使用与传播许可不由本仓库保证。保持私有，不重新发布这些素材。
