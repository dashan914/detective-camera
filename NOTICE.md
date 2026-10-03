# 许可范围与来源说明

项目自有代码采用根目录 `LICENSE`（MIT）；外壳设计及原创文档采用 `LICENSE-CONTENT.md`（CC BY 4.0）。第三方文件保留各自许可，不改署名、不统一重新许可。

## 文件与组件边界

| 内容 | 许可/状态 | 处理方式 |
| --- | --- | --- |
| 自有后端、设备协调/显示逻辑、网页交互与工具代码 | MIT | 保留项目版权与 MIT 文本 |
| 自有 CAD / STL / 模型渲染 / 原创说明 | CC BY 4.0 | 署名并注明修改；不包含厂家商标授权 |
| Courier Prime / 朱雀仿宋字体 | SIL OFL 1.1 | 使用各 `assets/` / `demo/` 中原许可证 |
| Three.js 0.170.0 与构建产物内其代码 | MIT（Three.js 作者） | 保留 `demo/draco/THREE-LICENSE.txt` 和 bundle 的声明 |
| Draco 解码器 | Apache-2.0 等，上游分项声明 | 保留 `demo/draco/LICENSE` 全文 |
| esbuild 0.24.0 | MIT，上游构建工具 | 依赖由 lockfile 安装，保留其声明 |
| Pillow | HPND / 上游许可证 | 依赖安装，不把项目许可套用于 Pillow |
| Arduino ESP32 Core 3.3.7 | LGPL-2.1，上游另含依赖 | 不随本仓库拷贝工具链；遵守完整工具链声明 |
| ESP32-audioI2S 3.4.7 | GPL-3.0 | 编译/分发包含该库的固件时审查 GPL 对组合作品及对应源码的要求，不能只贴 MIT 就声称固件整体是 MIT |
| `firmware/PoetryCameraDirector/es8311.cpp`、`.h` | 来源与许可记录待确认 | 暂不作为已核实的自有 MIT 文件；公开前确认来源、补足声明或提供可验证的替代实现 |
| 当前 `demo/audio/*.mp3`、`voice_pack_12/filesystem/voice/*.mp3` | 私有历史试验素材，公开分发权未确认 | 从公开包中排除，替换为原创/明确许可声音；不以真人或既有角色音色作为开放素材 |
| `backend/poem_library.json` | 文学摘录与翻译的来源/权利记录待补 | 公开包不携带当前库，保留附属功能代码，使用者自行配置合规文学素材 |
| 商标、名字、声音人格、模型生成结果 | 不因源码许可自动获得权利 | 参赛展示单独核对素材和比赛规则 |

屏幕形象由固件绘图函数生成，不导入角色截图。公开前仍需确认最终视觉没有使用未经授权的既有角色设计；「参考某种侦探气质」不等于拥有角色权利。

## 核对入口（2026-10-04）

- [MIT 模板](https://choosealicense.com/licenses/mit/)
- [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- [Arduino ESP32 Core 3.3.7 原许可](https://github.com/espressif/arduino-esp32/blob/3.3.7/LICENSE.md)
- [ESP32-audioI2S 3.4.7 原许可](https://github.com/schreibfaul1/ESP32-audioI2S/blob/3.4.7/LICENSE)
- [Waveshare 主板资料](https://docs.waveshare.net/ESP32-S3-CAM-OVxxxx/)

这是工程来源与发布边界说明，不代替特定法域/比赛的法律审查。公开前不能仅检查隐私，还必须完成授权和第三方合规检查。
