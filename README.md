# 🍌 Luck Nano Banana Pro for ComfyUI

**Luck Nano Banana Pro** 是一个 ComfyUI 自定义节点，使用 **apiyi.com** 的 Gemini 3 Pro Image Preview API，支持文生图和图像编辑功能。

---

## ✨ 功能特性

- 🎨 **文生图**：输入文字描述，生成高质量图片
- 🖼 **图像编辑**：上传图片 + 文字描述，对图片进行编辑修改
- 📐 **多种分辨率**：支持 1K / 2K / 4K 输出
- 📏 **多种宽高比**：AUTO + 14 种比例（含 1:4、4:1、1:8、8:1）
- 🤖 **多模型切换**：支持 `gemini-3.1-flash-image-preview`（Nano Banana 2）等模型
- 🎲 **ComfyUI 种子四模式**：固定 / 随机 / 递增 / 递减
- ⏱ **节点实时进度栏**：运行中显示状态/百分比/计时，结束后显示成功/失败
- 🔄 **自动重试**：支持自定义超时时间和重试次数
- 🖼 **多图输入**：最多支持 14 张图片同时输入

---

## 📦 安装方法

1. 将 `Comfyui-LuckNanoBananaPro` 文件夹放入 ComfyUI 的 `custom_nodes` 目录

2. 安装依赖：
   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. 重启 ComfyUI，在节点列表搜索 **Luck Nano Banana Pro**

> 如果你是手动把目录复制进 `custom_nodes`，新版 ComfyUI-Manager 可能不一定把它标成“已安装”。
> 但只要 ComfyUI 启动日志没有导入报错，且节点列表里能搜到 **Luck Nano Banana Pro**，就说明节点已经正常加载。
> 仓库示例工作流不包含真实 API Key，CI 也会阻止把真实 key 提交到仓库。

---

## 🚀 使用方法

### 文生图
1. 添加 **Luck Nano Banana Pro** 节点
2. 填入 API Key（从 api.apiyi.com 获取）
3. 输入 prompt 描述你想要的图片
4. 选择分辨率和宽高比
5. 设置 seed 控制模式（固定 / 随机 / 递增 / 递减）
6. 运行即可生成图片

### 图像编辑
1. 添加 **Luck Nano Banana Pro** 节点
2. 填入 API Key
3. 连接图片到 `image_01` ~ `image_14` 任意输入口
4. 输入 prompt 描述你想要的修改
5. 运行即可编辑图片

---

## ⚙️ 节点参数说明

| 参数 | 说明 |
|------|------|
| api_key | API 密钥，从 api.apiyi.com 获取 |
| prompt | 图片描述或编辑指令 |
| model | 模型选择（含 `gemini-3.1-flash-image-preview`） |
| image_size | 输出分辨率：1K / 2K / 4K |
| aspect_ratio | 宽高比：AUTO、1:1、1:4、4:1、1:8、8:1、16:9、9:16 等 |
| seed | 随机种子（支持 ComfyUI 四种生成后控制模式） |
| timeout_seconds | 超时时间（10-600秒，默认60） |
| retry_times | 重试次数（1-20次，默认6） |
| image_01 ~ image_14 | 可选图片输入（用于图像编辑） |

---

## 📝 注意事项

- 使用前需要从 api.apiyi.com 获取 API Key
- 分辨率越高，生成时间越长，建议超时时间设置：
  - 1K: 6 分钟
  - 2K: 10 分钟
  - 4K: 20 分钟
- 不支持的内容：去水印、换脸、NSFW

---

## 📜 License

MIT License
