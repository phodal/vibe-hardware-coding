
```
我买了个 Arduino 开发板：https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C/ ，帮我结合他们的 SKILL，帮我搭建完整的自动化开发环境吧：

[arduino/arduino-cli](https://github.com/arduino/arduino-cli)

然后创建 skill 等，确保应用能在硬件上跑起来（已经在 Arduino IDE 可以连接上串口了

## 验证

最后你可以使用 claude 来测试这个 SKILL， 是不是能把代码正确烧录进去
```


## Goal

```
我正在实现这个开发板，你帮我实现这些功能吧：

实现这些功能吧：

| 方向                          |                             可以做什么 | 优先级 | 备注                                                                                                 |
| --------------------------- | --------------------------------: | --: | -------------------------------------------------------------------------------------------------- |
| **1. 跑通官方 Demo**            |            显示、触摸、电源、IMU、音频录放、LVGL |  P0 | 先确认板子、驱动、工具链没问题                                                                                    |
| **2. 小智 AI 语音助手**           |                刷固件，做语音对话、IoT 控制入口 |  P0 | 官方文档给了无开发环境烧录和源码编译两条路线。([[Waveshare Docs](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C/XiaoZhi_AI?utm_source=chatgpt.com)][1])                                                       |
| **3. 自研云端 AI 终端**           | 麦克风采集 → 云端 ASR/LLM/TTS → 屏幕/扬声器输出 |  P0 | 最适合这块板；本地主要做交互、缓存、状态管理                                                                             |
| **4. 离线语音控制**               |                   唤醒词、关键词命令、本地状态机 |  P1 | ESP-SR 的 WakeNet / MultiNet 可用于低功耗嵌入式语音识别。([[Espressif Systems](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/wake_word_engine/README.html?utm_source=chatgpt.com)][2])                                 |
| **5. 触摸 UI / 可视化 Agent**    |             LVGL 仪表盘、聊天气泡、设置页、卡片流 |  P1 | 官方 Arduino 示例包含 LVGL Widgets、IMU 曲线、电源数据等。([[Waveshare Docs](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C/Development-Environment-Setup-Arduino?utm_source=chatgpt.com)][3])                                    |
| **6. IMU 交互**               |                 抬腕唤醒、摇晃切换、姿态菜单、计步 |  P1 | 板载 QMI8658 六轴 IMU。([[Waveshare Docs](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C/?utm_source=chatgpt.com)][4])                                                            |
| **7. 电池与低功耗**               |               电量显示、睡眠唤醒、续航评估、充电状态 |  P1 | 板载 AXP2101 电源管理和 3.7V 锂电池接口。([[Waveshare Docs](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C/?utm_source=chatgpt.com)][4])                                                  |
| **8. 桌面 AI 挂件**             |     状态灯牌、番茄钟、GitHub/CI/日程提醒、AI 摘要 |  P1 | Wi‑Fi + 屏幕 + 扬声器，很适合常驻设备                                                                           |
| **9. IoT 控制面板**             |  Home Assistant / MQTT / HTTP 控制器 |  P1 | 触摸屏适合做小型家居控制面板                                                                                     |
| **10. ESP-Claw / OpenClaw** |       设备 Agent、MCP、IM 聊天控制、Lua 规则 |  P2 | ESP-Claw 文档描述了“感知→推理→决策→执行”的边缘 AI 框架，并支持 ESP32-S3；要求至少 8MB Flash + 8MB PSRAM。([[Waveshare Docs](https://docs.waveshare.net/ESPClaw?utm_source=chatgpt.com)][5]) |
| **11. TinyML / ESP-DL**     |                  传感器分类、姿态识别、小模型推理 |  P2 | 适合小模型，不适合本地跑完整 LLM。ESP-DL 提供神经网络推理、图像处理、数学运算 API。([[ESP Component Registry](https://components.espressif.com/components/espressif/esp-dl?utm_source=chatgpt.com)][6])                     |
| **12. 音频前端实验**              |              AEC、NS、VAD、双麦波束/降噪评估 |  P2 | ESP-SR AFE 支持 AEC、噪声抑制、VAD、WakeNet 等。([[Espressif Systems](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/audio_front_end/README.html?utm_source=chatgpt.com)][7])                                      |


## 验证

你应该验证每个功能，比如通过摄像头等

## 迭代

你应该尽可能开发一些额外的工具，来确保所有的硬件功能都能被你验证。
```
