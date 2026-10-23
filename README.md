# 🍌 Luck Nano Banana Pro for ComfyUI

**Luck Nano Banana Pro** 是一个 ComfyUI 自定义节点，通过 **apiyi.com** 的 Gemini 原生接口调用 Nano Banana 系列模型，支持文生图和图像编辑。新建节点默认使用 **Nano Banana 2.1**（`gemini-nano-banana-2.1`）。

---

## ✨ 功能特性

- 🎨 **文生图**：输入文字描述，生成高质量图片
- 🖼 **图像编辑**：上传图片 + 文字描述，对图片进行编辑修改
- 📐 **多种分辨率**：支持 1K / 2K / 4K 输出
- 📏 **多种宽高比**：AUTO + 14 种比例（含 1:4、4:1、1:8、8:1）
- 🤖 **多模型切换**：支持 `gemini-nano-banana-2.1`（Nano Banana 2.1）、`gemini-3.1-flash-image-preview`（Nano Banana 2）、`gemini-3-pro-image-preview` 和 `gemini-2.5-flash-image`
- 🎲 **ComfyUI 种子四模式**：固定 / 随机 / 递增 / 递减
- ⏱ **节点实时进度栏**：运行中显示状态/百分比/计时，结束后显示成功/失败
- 🔄 **自动重试**：NB2.1 对限流、过载及连接建立超时退避重试，读取超时后停止自动重发
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
| model | 默认 `gemini-nano-banana-2.1`，保留旧模型选项 |
| image_size | 输出分辨率：1K / 2K / 4K |
| aspect_ratio | 宽高比：AUTO、1:1、1:4、4:1、1:8、8:1、16:9、9:16 等 |
| seed | 随机种子（支持 ComfyUI 四种生成后控制模式） |
| timeout_seconds | 超时时间（10-600秒，新建节点默认360）；NB2.1 实际至少等待360秒，状态栏使用实际值；旧模型使用保存的设置 |
| retry_times | 总尝试次数（含首次请求，1-20次，默认6） |
| image_01 ~ image_14 | 可选图片输入（用于图像编辑） |

---

## 📝 注意事项

- 使用前需要从 api.apiyi.com 获取 API Key
- NB2.1 支持 1K / 2K / 4K，不支持 512。选择 AUTO 时不发送宽高比，由模型自行决定；需要固定构图时请选择具体比例。
- NB2.1 使用服务端默认输出上限和默认思考档位（medium），避免旧版 2048 tokens 上限限制 4K 输出。
- NB2.1 实际超时为 `max(timeout_seconds, 360)`，4K 或多图编辑可设置为600秒。其他模型沿用原请求行为和已保存的超时设置。
- NB2.1 的 HTTP 429、503 和连接建立超时按5、15、45秒退避，后续间隔保持45秒，总尝试次数由 `retry_times` 控制。参数、权限、内容拦截及无图片响应直接报告错误。
- 图片接口为同步调用。NB2.1 读取超时或连接中断时，服务端可能仍在生成并计费，因此节点停止自动重发；请先核对 API易调用日志，再决定是否重新运行。
- 旧工作流仍保留原模型、参数和连接；需要使用 NB2.1 时，在原节点的模型下拉框中选择 `gemini-nano-banana-2.1` 即可。Google 官方 API Key 节点不受此次更新影响。
- 接口说明：[NB2.1 文档](https://docs.apiyi.com/api-capabilities/gemini-nano-banana-2.1/overview)。
- 不支持的内容：去水印、换脸、NSFW

---

## 开发验证

使用已安装 ComfyUI 依赖的 Python 运行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_no_api_keys.py
```

测试使用模拟 HTTP 响应，不发送真实生图请求。

---

## 📜 License

MIT License
