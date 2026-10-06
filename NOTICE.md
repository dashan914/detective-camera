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
| `firmware/PoetryCameraDirector/es8311.cpp`、`.h` | 来源与许可记录待确认 | 随工程保留，但不作为已核实的自有 MIT 文件；复用前确认来源、补足声明或使用可验证的替代实现 |
| 当前及 Git 历史中的 `demo/audio/*.mp3`、`voice_pack_12/filesystem/voice/*.mp3` | 历史试验素材，公开分发权未确认 | 不属于 MIT / CC BY 4.0，也不授予声音、角色或人格相关权利；复用、再分发或商用前须另行确认授权，建议替换为原创/明确许可声音 |
| `backend/poem_library.json` | 文学摘录与翻译的来源/权利记录待补 | 不属于项目自有内容授权；使用者需自行核对作品、翻译与来源，或配置有明确许可的文学素材 |
| 商标、名字、声音人格、模型生成结果 | 不因源码许可自动获得权利 | 参赛展示单独核对素材和比赛规则 |

屏幕形象由固件绘图函数生成，不导入角色截图。最终视觉的原创性与素材来源仍待复核；「参考某种侦探气质」不等于拥有角色权利。

## 公开仓库与素材授权

本仓库公开用于展示项目源码、结构与实现过程，包含历史试验素材及 Git 历史。上述待核实项不会因仓库公开而自动获得授权，也不会因添加说明而变成已获许可素材。项目不将其纳入自有开源许可，不承诺其可自由复制、再分发或商用；完整的权利核验仍是未完成事项。

## 核对入口（2026-10-04）

- [MIT 模板](https://choosealicense.com/licenses/mit/)
- [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- [Arduino ESP32 Core 3.3.7 原许可](https://github.com/espressif/arduino-esp32/blob/3.3.7/LICENSE.md)
- [ESP32-audioI2S 3.4.7 原许可](https://github.com/schreibfaul1/ESP32-audioI2S/blob/3.4.7/LICENSE)
- [Waveshare 主板资料](https://docs.waveshare.net/ESP32-S3-CAM-OVxxxx/)

这是工程来源与许可边界说明，不代替特定法域/比赛的法律审查。隐私扫描不等于授权确认；素材授权和第三方合规检查仍需继续完成。
