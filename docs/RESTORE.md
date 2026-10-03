# 恢复与隔离部署

## 取回与核验

通过拥有权限的 GitHub 账号克隆私有仓库，记录提交号。运行 `python3 tools/privacy_check.py --history` 和 `python3 tools/backup_manifest.py`；清单只记录仓库相对路径、字节数和 SHA-256，不含密钥。不要将生产 `.env` 或设备镜像加入仓库。

## 后端

创建独立虚拟环境，安装根目录 `requirements.txt`，复制 `backend/.env.example` 为 `backend/.env`；用不同随机值配置设备令牌和管理员密码，设置模型地址/ID/API Key。案件配音为可选功能，另外填写自己的音色 ID。禁止复用别的项目密钥。

后端默认新状态保留历史兼容模式，首次登录后选择侦探模式并保存。重新配网设备，填写自己的后端地址及相同设备令牌。备份版不硬编码旧服务器地址、不自动迁移现有设备。

```sh
cd backend
python3 -m unittest -v test_server.py test_detective.py test_detective_renderer.py test_case_voice.py
DASHAN_HOST=127.0.0.1 python3 server.py
```

测试使用合成图片及假响应，不发送私人照片或请求真实 AI/TTS。先验证管理员鉴权、设备心跳，再单独授权实拍测试。

## 与服务器其他项目隔离

部署到新的目录、专用服务用户、独立虚拟环境、独立 systemd 服务名、独立数据目录和空闲端口。示例服务在 `../deploy/detective-camera.service.example`，仅为模板，不会自动安装或启动。确认 8788 未占用后再使用；不要修改现有服务或其端口。

生产密钥由本机权限 0600 的环境文件提供；数据目录包括带 Key 的状态 JSON、照片和动态音频，不对外公开。HTTPS 反向代理只映射预期的 API/导演台，限制请求大小；静态网页只能发布 `demo/` 发布清单，绝不能公开项目根目录或 backend。

切换前备份现有目录/链接，校验新服务健康，再只切换侦探相机自己的入口；不停止其他项目。回滚只恢复自己的旧入口，不删除共享目录、不覆盖整个站点。

## 静态网页

在 `demo/` 执行 `npm ci`、`node build.mjs`。发布 `index.html`、`detective.css`、`detective.js`、`DASHAN_V33.glb`、`camera-preview.jpg`、字体及许可、`screen-frames/`、`draco/` 和四个使用中的 `audio/` 文件。源码脚本不必发布；资源路径可用于 `/dashan/detective-camera/` 子路径。`legacy-preview-redirect.html` 是可选旧入口跳转模板。

## 设备和外壳

按 `firmware/README.md` 安装匹配的 Arduino Core/库并编译。不要盲目擦除整盘或改分区，否则会丢失 NVS/语音文件。语音文件使用 `voice_pack_12/filesystem/voice/`，目前固件读取 FFat，复制到 SD 卡不会自动生效。刷写前确认设备实际分区表；本仓库不保存含私密数据的整盘镜像。

Blender 源在 `hardware/cad/`，打印件在 `hardware/stl/`；每件尺寸、支撑和硬件试装需重新检查。网页 GLB 只展示，不用于切片。
