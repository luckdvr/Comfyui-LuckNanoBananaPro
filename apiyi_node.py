#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luck Nano Banana Pro ComfyUI 节点 - 使用 apiyi.com API
支持文生图和图生图（编辑图片）
支持 1K/2K/4K 分辨率输出
"""

import base64
import time
import requests
from io import BytesIO

from PIL import Image
import numpy as np
import torch


#################################################################
#                   图像转换工具函数
#################################################################

def tensor_to_base64(tensor):
    """ComfyUI IMAGE tensor → base64 字符串"""
    if tensor is None:
        raise ValueError("输入 tensor 为 None")

    arr = (tensor[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def base64_to_tensor(b64_str):
    """base64 字符串 → ComfyUI tensor (1,H,W,3)"""
    img_bytes = base64.b64decode(b64_str)
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0).float()


def emit_runtime_status(
    node_id,
    status,
    message="",
    elapsed_seconds=0.0,
    attempt=0,
    retry_times=0,
    timeout_seconds=0,
):
    """向 ComfyUI 前端发送节点运行状态事件。"""
    if node_id in (None, ""):
        return
    try:
        from server import PromptServer

        if PromptServer.instance is None:
            return

        PromptServer.instance.send_sync(
            "lucknanobanana_status",
            {
                "node_id": str(node_id),
                "status": status,
                "message": message,
                "elapsed_seconds": float(elapsed_seconds),
                "attempt": int(attempt),
                "retry_times": int(retry_times),
                "timeout_seconds": int(timeout_seconds),
                "timestamp": time.time(),
            }
        )
    except Exception:
        # 前端状态栏异常不影响主流程
        pass


#################################################################
#                   Luck Nano Banana Pro 节点
#################################################################

class LuckNanoBananaProNode:
    """
    Luck Nano Banana Pro 图像生成/编辑节点
    使用 apiyi.com 的 Gemini API
    """

    # API 端点模板
    API_URL_TEMPLATE = "https://api.apiyi.com/v1beta/models/{model}:generateContent"

    # 模型列表
    MODELS = [
        "gemini-3.1-flash-image-preview",
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key (API密钥)": ("STRING", {"default": "", "multiline": False}),
                "prompt (提示词)": ("STRING", {"default": "", "multiline": True}),
                "model (模型)": (cls.MODELS, {"default": "gemini-3.1-flash-image-preview"}),
                "image_size (分辨率)": (["1K", "2K", "4K"], {"default": "1K"}),
                "aspect_ratio (宽高比)": (
                    [
                        "AUTO",
                        "1:4", "4:1", "1:8", "8:1",
                        "1:1", "2:3", "3:2", "3:4", "4:3",
                        "4:5", "5:4", "9:16", "16:9", "21:9"
                    ],
                    {"default": "AUTO"}
                ),
                # ComfyUI 原生种子控制（固定/随机/递增/递减）
                "seed (种子)": ("INT", {"default": 0, "min": 0, "max": 2147483647, "control_after_generate": True}),
                "temperature (温度)": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "timeout_seconds (超时秒数)": ("INT", {"default": 60, "min": 10, "max": 600}),
                "retry_times (重试次数)": ("INT", {"default": 6, "min": 1, "max": 20}),
            },
            "optional": {
                **{f"image_{i:02d}": ("IMAGE",) for i in range(1, 15)}
            },
            "hidden": {
                "unique_id": "UNIQUE_ID"
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    FUNCTION = "generate"
    CATEGORY = "LuckNanoBananaPro"

    def generate(
        self,
        **kwargs
    ):
        # 获取参数（带中文名）
        api_key = kwargs.get("api_key (API密钥)", "")
        prompt = kwargs.get("prompt (提示词)", "")
        model = kwargs.get("model (模型)", "gemini-3.1-flash-image-preview")
        image_size = kwargs.get("image_size (分辨率)", "1K")
        aspect_ratio = kwargs.get("aspect_ratio (宽高比)", "AUTO")
        seed = kwargs.get("seed (种子)", 0)
        temperature = kwargs.get("temperature (温度)", 1.0)
        timeout_seconds = kwargs.get("timeout_seconds (超时秒数)", 60)
        retry_times = kwargs.get("retry_times (重试次数)", 6)
        unique_id = kwargs.get("unique_id")
        start_ts = time.time()

        if not api_key.strip():
            emit_runtime_status(unique_id, "error", "API Key 为空", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("❌ API Key 不能为空")

        print(f"[LuckNanoBananaPro] 使用 seed: {seed}")
        emit_runtime_status(unique_id, "running", "开始生成", 0.0, 0, retry_times, timeout_seconds)

        # 构建 API URL
        api_url = self.API_URL_TEMPLATE.format(model=model)

        # 构建请求内容
        parts = []

        # 添加输入图片（用于图生图/编辑）
        for i in range(1, 15):
            tensor = kwargs.get(f"image_{i:02d}")
            if tensor is not None:
                img_base64 = tensor_to_base64(tensor)
                parts.append({
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": img_base64
                    }
                })

        # 添加文本提示词
        if prompt.strip():
            parts.append({"text": prompt.strip()})

        if not parts:
            raise ValueError("❌ 必须提供 prompt 或输入图像")

        # 构建 imageConfig
        image_config = {"imageSize": image_size}
        if aspect_ratio != "AUTO":
            image_config["aspectRatio"] = aspect_ratio

        # 构建请求体
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "maxOutputTokens": 2048,
                "temperature": temperature,
                "seed": seed,
                "imageConfig": image_config
            }
        }

        # 请求头
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }

        # 重试逻辑
        last_error = None
        for attempt in range(retry_times):
            try:
                print(f"[LuckNanoBananaPro] 请求中... (尝试 {attempt + 1}/{retry_times})")
                emit_runtime_status(
                    unique_id,
                    "running",
                    f"请求中 ({attempt + 1}/{retry_times})",
                    time.time() - start_ts,
                    attempt + 1,
                    retry_times,
                    timeout_seconds,
                )

                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout_seconds
                )

                if response.status_code != 200:
                    error_msg = response.text
                    # 503 过载错误，等待后重试
                    if response.status_code == 503 or "overload" in error_msg.lower():
                        print(f"[LuckNanoBananaPro] 服务过载，等待重试...")
                        time.sleep(1.5)
                        last_error = f"API 错误 {response.status_code}: {error_msg}"
                        emit_runtime_status(
                            unique_id,
                            "running",
                            f"服务过载，重试中 ({attempt + 1}/{retry_times})",
                            time.time() - start_ts,
                            attempt + 1,
                            retry_times,
                            timeout_seconds,
                        )
                        continue
                    raise RuntimeError(f"API 错误 {response.status_code}: {error_msg}")

                data = response.json()

                # 解析响应
                image_tensor, text_output = self._parse_response(data)

                if image_tensor is not None:
                    print(f"[LuckNanoBananaPro] ✅ 生成成功!")
                    emit_runtime_status(
                        unique_id,
                        "success",
                        f"生成成功 (耗时 {time.time() - start_ts:.1f}s)",
                        time.time() - start_ts,
                        attempt + 1,
                        retry_times,
                        timeout_seconds,
                    )
                    return (image_tensor, text_output)

            except requests.exceptions.Timeout:
                last_error = f"⏰ 超过 {timeout_seconds}s 已强制终止"
                print(f"[LuckNanoBananaPro] {last_error}")
                emit_runtime_status(
                    unique_id,
                    "running",
                    f"超时，重试中 ({attempt + 1}/{retry_times})",
                    time.time() - start_ts,
                    attempt + 1,
                    retry_times,
                    timeout_seconds,
                )
                continue
            except requests.exceptions.ConnectionError as e:
                last_error = f"网络连接错误: {e}"
                print(f"[LuckNanoBananaPro] {last_error}")
                time.sleep(1.5)
                emit_runtime_status(
                    unique_id,
                    "running",
                    f"网络异常，重试中 ({attempt + 1}/{retry_times})",
                    time.time() - start_ts,
                    attempt + 1,
                    retry_times,
                    timeout_seconds,
                )
                continue
            except RuntimeError as e:
                emit_runtime_status(
                    unique_id,
                    "error",
                    str(e),
                    time.time() - start_ts,
                    attempt + 1,
                    retry_times,
                    timeout_seconds,
                )
                raise
            except Exception as e:
                last_error = str(e)
                if "503" in last_error or "overload" in last_error.lower():
                    time.sleep(1.5)
                    emit_runtime_status(
                        unique_id,
                        "running",
                        f"服务繁忙，重试中 ({attempt + 1}/{retry_times})",
                        time.time() - start_ts,
                        attempt + 1,
                        retry_times,
                        timeout_seconds,
                    )
                    continue
                emit_runtime_status(
                    unique_id,
                    "error",
                    last_error,
                    time.time() - start_ts,
                    attempt + 1,
                    retry_times,
                    timeout_seconds,
                )
                raise

        emit_runtime_status(
            unique_id,
            "error",
            f"连续 {retry_times} 次失败",
            time.time() - start_ts,
            retry_times,
            retry_times,
            timeout_seconds,
        )
        raise RuntimeError(f"🔥 连续 {retry_times} 次失败\n最后错误：{last_error}")

    def _parse_response(self, data):
        """解析 API 响应，提取图片和文本"""
        image_tensor = None
        text_output = ""

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"❌ API 未返回有效数据: {data}")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                # 提取图片数据（支持驼峰和下划线两种格式）
                inline_data = part.get("inlineData") or part.get("inline_data")
                if inline_data and "data" in inline_data:
                    image_tensor = base64_to_tensor(inline_data["data"])

                # 提取文本
                if "text" in part:
                    text_output += part["text"] + "\n"

        except KeyError as e:
            raise RuntimeError(f"响应格式错误: {e}, 响应: {data}")

        if image_tensor is None:
            raise RuntimeError(f"❌ Gemini 返回文本，但没有生成图像")

        return image_tensor, text_output.strip()


#################################################################
#                       节点注册
#################################################################

NODE_CLASS_MAPPINGS = {
    "LuckNanoBananaProNode": LuckNanoBananaProNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LuckNanoBananaProNode": "Luck Nano Banana Pro"
}
