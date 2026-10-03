# 本地开发指南

只想体验项目，可直接访问 [在线交互演示](https://ai3dclass.cn/dashan/detective-camera/)，不需要安装软件。

下面的命令用于在自己的电脑上启动项目。`127.0.0.1` 表示当前这台电脑，不是供其他人访问的在线地址；必须先运行相应服务，再在同一台电脑的浏览器打开。

## 网页演示

在仓库根目录执行：

```sh
cd demo
npm ci
node build.mjs
python3 -m http.server 8894 --bind 127.0.0.1
```

保持终端服务运行，在这台电脑上打开 `http://127.0.0.1:8894/`。网页使用固定案例，不连接设备，不调用模型 API。资源结构与测试方式见 [演示开发说明](../demo/README.md)。

## 导演台

在仓库根目录创建独立虚拟环境：

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
```

在 `.env` 中填写独立的设备令牌、管理员密码和模型配置，再运行：

```sh
cd backend
DASHAN_HOST=127.0.0.1 python3 server.py
```

在同一台电脑上打开 `http://127.0.0.1:8787/director`。用户名为 `admin`，密码由 `DASHAN_ADMIN_TOKEN` 设置。首次使用请选择侦探模式。

上述回环地址用于本机开发，ESP32 无法通过它连接这台电脑。连接实机时，需要按 [部署说明](RESTORE.md) 配置设备能够访问的后端地址、鉴权与网络访问范围；不要把管理员密码或模型密钥写入网页。

真实照片处理需要支持当前请求格式的模型服务和使用者自己的凭据。案件配音为可选功能，外部服务的费用、延迟与可用性取决于服务提供方。

## 设备编译

设备使用 Arduino ESP32 Core 3.3.7 / ESP32-audioI2S 3.4.7，16 MB Flash、8 MB OPI PSRAM。接线与编译见 [硬件说明](HARDWARE.md) 和 [固件说明](../firmware/README.md)。工程名 `PoetryCameraDirector` 保留，以满足 Arduino 工程命名要求。

## 测试

在仓库根目录执行：

```sh
cd backend
python3 -m unittest -v test_server.py test_detective.py test_detective_renderer.py test_case_voice.py
```

测试使用合成图片与模拟服务，不上传私人照片、不调用真实 AI/TTS。验证记录见 [归档核验](BACKUP_2026-10-04.md)。完整实机复现及最终固定件、触摸操作仍需实物验收；打印完成事件表示数据发送完成，不代表纸张传感器确认。

## 维护与发布

密钥、设备状态、实拍照片与聊天记录不应提交。素材和依赖按各自许可使用，具体见 [许可声明](../NOTICE.md)、[隐私说明](PRIVACY.md) 和 [发布检查清单](RELEASE_CHECKLIST.md)。
