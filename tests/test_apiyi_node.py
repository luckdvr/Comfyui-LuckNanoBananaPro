import base64
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import requests
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("luck_apiyi_node_under_test", ROOT / "apiyi_node.py")
node_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(node_module)
Node = node_module.LuckNanoBananaProNode
emit_runtime_status = node_module.emit_runtime_status


def image_part(color=(255, 0, 0), image_format="PNG", snake_case=False):
    buffer = io.BytesIO()
    Image.new("RGB", (3, 2), color).save(buffer, format=image_format)
    mime = "image/png" if image_format == "PNG" else "image/jpeg"
    key, mime_key = ("inline_data", "mime_type") if snake_case else ("inlineData", "mimeType")
    return {key: {mime_key: mime, "data": base64.b64encode(buffer.getvalue()).decode("ascii")}}


def response_data(parts=None, finish_reason="STOP"):
    return {"candidates": [{
        "finishReason": finish_reason,
        "content": {"parts": [image_part()] if parts is None else parts},
    }]}


def http_response(status=200, data=None):
    return Mock(
        status_code=status,
        text="DO_NOT_LOG_RESPONSE_BODY",
        json=Mock(return_value=response_data() if data is None else data),
    )


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.node = Node()
        self.params = {
            "api_key (API密钥)": "test-key",
            "prompt (提示词)": "画一只橘猫",
            "unique_id": "42",
        }
        self.post = self.enterContext(patch.object(node_module.requests, "post", return_value=http_response()))
        self.sleep = self.enterContext(patch.object(node_module.time, "sleep"))
        self.status = self.enterContext(patch.object(node_module, "emit_runtime_status"))
        self.enterContext(patch("sys.stdout", new_callable=io.StringIO))

    def generate(self, **overrides):
        return self.node.generate(**dict(self.params, **overrides))

    def test_defaults_and_public_node_interface(self):
        schema = Node.INPUT_TYPES()
        self.assertEqual(list(schema["required"]), [
            "api_key (API密钥)", "prompt (提示词)", "model (模型)",
            "image_size (分辨率)", "aspect_ratio (宽高比)", "seed (种子)",
            "temperature (温度)", "timeout_seconds (超时秒数)", "retry_times (重试次数)",
        ])
        self.assertEqual(schema["required"]["model (模型)"][1]["default"], Node.NB21_MODEL)
        self.assertEqual(schema["required"]["timeout_seconds (超时秒数)"][1]["default"], 360)
        self.assertEqual(list(schema["optional"]), [f"image_{i:02d}" for i in range(1, 15)])
        self.assertEqual(schema["hidden"], {"unique_id": "UNIQUE_ID"})
        self.assertEqual(Node.RETURN_TYPES, ("IMAGE", "STRING"))
        self.assertEqual(Node.FUNCTION, "generate")
        self.assertIs(node_module.NODE_CLASS_MAPPINGS["LuckNanoBananaProNode"], Node)
        self.assertEqual(node_module.NODE_DISPLAY_NAME_MAPPINGS["LuckNanoBananaProNode"], "Luck Nano Banana Pro")

    def test_text_to_image_default_request_and_status(self):
        tensor, text = self.generate()
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], "https://api.apiyi.com/v1beta/models/gemini-nano-banana-2.1:generateContent")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["timeout"], 360)
        self.assertEqual(kwargs["json"]["contents"], [{"parts": [{"text": "画一只橘猫"}]}])
        config = kwargs["json"]["generationConfig"]
        self.assertEqual(config["imageConfig"], {"imageSize": "1K"})
        self.assertEqual(config["responseModalities"], ["IMAGE", "TEXT"])
        self.assertNotIn("maxOutputTokens", config)
        self.assertNotIn("thinkingConfig", config)
        self.assertNotIn("tools", kwargs["json"])
        self.assertEqual(tuple(tensor.shape), (1, 2, 3, 3))
        self.assertEqual(text, "")
        self.assertEqual(self.status.call_args.args[1], "success")
        self.assertTrue(all(call.args[6] == 360 for call in self.status.call_args_list))

    def test_all_resolutions_and_fixed_ratios(self):
        ratios = Node.INPUT_TYPES()["required"]["aspect_ratio (宽高比)"][0]
        self.assertEqual(len(ratios), 15)
        for size in ("1K", "2K", "4K"):
            for ratio in ratios:
                with self.subTest(size=size, ratio=ratio):
                    self.generate(**{"image_size (分辨率)": size, "aspect_ratio (宽高比)": ratio})
                    config = self.post.call_args.kwargs["json"]["generationConfig"]
                    expected = {"imageSize": size}
                    if ratio != "AUTO":
                        expected["aspectRatio"] = ratio
                    self.assertEqual(config["imageConfig"], expected)
                    self.assertNotIn("maxOutputTokens", config)

    def test_seed_and_temperature_are_forwarded(self):
        self.generate(**{"seed (种子)": 123, "temperature (温度)": 0.7})
        config = self.post.call_args.kwargs["json"]["generationConfig"]
        self.assertEqual(config["seed"], 123)
        self.assertEqual(config["temperature"], 0.7)

    def test_reference_images_are_separate_png_parts_in_port_order(self):
        for count in (1, 14):
            with self.subTest(count=count):
                images = {f"image_{i:02d}": torch.full((1, 2, 3, 3), i / 15) for i in range(1, count + 1)}
                self.generate(**images)
                parts = self.post.call_args.kwargs["json"]["contents"][0]["parts"]
                self.assertEqual(len(parts), count + 1)
                self.assertEqual(parts[-1], {"text": "画一只橘猫"})
                for i, part in enumerate(parts[:-1], 1):
                    self.assertEqual(set(part), {"inlineData"})
                    self.assertEqual(part["inlineData"]["mimeType"], "image/png")
                    image = Image.open(io.BytesIO(base64.b64decode(part["inlineData"]["data"])))
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.mode, "RGB")
                    self.assertEqual(image.getpixel((0, 0)), (int(i / 15 * 255),) * 3)

    def test_sparse_image_ports_remain_supported(self):
        image = torch.zeros((1, 2, 3, 3))
        self.generate(image_04=image, image_14=image)
        parts = self.post.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(len(parts), 3)

    def test_nb21_timeout_floor_and_larger_setting(self):
        for configured, expected in ((10, 360), (60, 360), (360, 360), (600, 600)):
            with self.subTest(configured=configured):
                self.status.reset_mock()
                self.generate(**{"timeout_seconds (超时秒数)": configured})
                self.assertEqual(self.post.call_args.kwargs["timeout"], expected)
                self.assertTrue(all(call.args[6] == expected for call in self.status.call_args_list))

    def test_512_is_rejected_before_request(self):
        with self.assertRaisesRegex(ValueError, "不支持 512"):
            self.generate(**{"image_size (分辨率)": "512"})
        self.post.assert_not_called()
        self.assertEqual(self.status.call_args.args[1], "error")

    def test_empty_key_is_rejected_before_request(self):
        with self.assertRaises(ValueError):
            self.generate(**{"api_key (API密钥)": "  "})
        self.post.assert_not_called()
        self.assertEqual(self.status.call_args.args[1], "error")

    def test_retryable_failures_use_bounded_backoff_then_succeed(self):
        self.post.side_effect = [
            http_response(429), http_response(503), requests.exceptions.ConnectTimeout(),
            http_response(503), http_response(),
        ]
        self.generate()
        self.assertEqual(self.post.call_count, 5)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [5, 15, 45, 45])
        self.assertEqual(self.status.call_args.args[1], "success")
        self.assertEqual(self.status.call_args.args[4], 5)

    def test_exhausted_retries_do_not_sleep_after_last_attempt(self):
        self.post.return_value = http_response(503)
        with self.assertRaisesRegex(RuntimeError, "连续 3 次失败"):
            self.generate(**{"retry_times (重试次数)": 3})
        self.assertEqual(self.post.call_count, 3)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [5, 15])
        self.assertEqual(self.status.call_args.args[1], "error")

    def test_single_attempt_does_not_backoff(self):
        self.post.side_effect = requests.exceptions.ConnectTimeout()
        with self.assertRaisesRegex(RuntimeError, "连接建立超时"):
            self.generate(**{"retry_times (重试次数)": 1})
        self.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_ambiguous_disconnect_or_timeout_is_never_retried(self):
        for error in (
            requests.exceptions.ReadTimeout(), requests.exceptions.Timeout(),
            requests.exceptions.ConnectionError(), requests.exceptions.ChunkedEncodingError(),
        ):
            with self.subTest(error=type(error).__name__):
                self.post.reset_mock()
                self.post.side_effect = error
                with self.assertRaisesRegex(RuntimeError, "服务端可能仍在生成并计费"):
                    self.generate()
                self.post.assert_called_once()
                self.sleep.assert_not_called()
                self.assertEqual(self.status.call_args.args[1], "error")
                self.assertIn("停止自动重发", self.status.call_args.args[2])

    def test_terminal_http_errors_do_not_log_response_or_retry(self):
        for code in (400, 401, 403, 404, 500):
            with self.subTest(code=code):
                self.post.reset_mock()
                response = http_response(code)
                response.text = "DO_NOT_LOG_RESPONSE_BODY overload " + "A" * 10000
                self.post.return_value = response
                with self.assertRaisesRegex(RuntimeError, str(code)) as caught:
                    self.generate()
                self.assertNotIn("DO_NOT_LOG", str(caught.exception))
                self.post.assert_called_once()
                self.sleep.assert_not_called()
                self.assertEqual(self.status.call_args.args[1], "error")

    def test_invalid_json_does_not_retry(self):
        self.post.return_value.json.side_effect = ValueError("DO_NOT_LOG_RESPONSE_BODY")
        with self.assertRaisesRegex(RuntimeError, "有效 JSON") as caught:
            self.generate()
        self.assertNotIn("DO_NOT_LOG", str(caught.exception))
        self.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_safety_block_is_reported_without_retry(self):
        self.post.return_value = http_response(data=response_data([], "IMAGE_SAFETY"))
        with self.assertRaisesRegex(RuntimeError, "IMAGE_SAFETY"):
            self.generate()
        self.post.assert_called_once()
        self.sleep.assert_not_called()
        self.assertEqual(self.status.call_args.args[1], "error")

    def test_all_legacy_models_keep_output_limit_and_saved_timeout(self):
        for model in ("gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"):
            with self.subTest(model=model):
                self.assertIn(model, Node.MODELS)
                self.generate(**{"model (模型)": model, "timeout_seconds (超时秒数)": 60})
                args, kwargs = self.post.call_args
                self.assertIn(model + ":generateContent", args[0])
                self.assertEqual(kwargs["timeout"], 60)
                self.assertEqual(kwargs["json"]["generationConfig"]["maxOutputTokens"], 2048)

    def test_saved_widget_values_keep_their_original_positions(self):
        saved = ["test-key", "旧工作流", "gemini-3-pro-image-preview", "4K", "AUTO", 42, 0.6, 120, 6]
        params = dict(zip(Node.INPUT_TYPES()["required"], saved))
        self.node.generate(**params)
        config = self.post.call_args.kwargs["json"]["generationConfig"]
        self.assertIn("gemini-3-pro-image-preview", self.post.call_args.args[0])
        self.assertEqual(config["seed"], 42)
        self.assertEqual(config["temperature"], 0.6)
        self.assertEqual(config["imageConfig"], {"imageSize": "4K"})
        self.assertEqual(self.post.call_args.kwargs["timeout"], 120)

    def test_legacy_timeout_still_retries(self):
        self.post.side_effect = [requests.exceptions.ReadTimeout(), http_response()]
        self.generate(**{"model (模型)": "gemini-3-pro-image-preview", "timeout_seconds (超时秒数)": 60})
        self.assertEqual(self.post.call_count, 2)
        self.assertEqual(self.status.call_args.args[1], "success")

    def test_legacy_connection_error_and_overload_still_retry(self):
        self.post.side_effect = [requests.exceptions.ConnectionError(), http_response(503), http_response()]
        self.generate(**{"model (模型)": "gemini-3.1-flash-image-preview"})
        self.assertEqual(self.post.call_count, 3)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [1.5, 1.5])


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.node = Node()

    def test_mixed_parts_use_last_image_and_preserve_text_order(self):
        parts = [{"text": "第一段"}, image_part(), {"text": "第二段"}, image_part((0, 255, 0))]
        tensor, text = self.node._parse_response(response_data(parts))
        torch.testing.assert_close(tensor[0, 0, 0], torch.tensor([0.0, 1.0, 0.0]))
        self.assertEqual(text, "第一段\n第二段")

    def test_invalid_intermediate_image_does_not_hide_valid_final_image(self):
        parts = [{"inlineData": {"data": "invalid-intermediate"}}, image_part()]
        tensor, _ = self.node._parse_response(response_data(parts))
        torch.testing.assert_close(tensor[0, 0, 0], torch.tensor([1.0, 0.0, 0.0]))

    def test_jpeg_and_snake_case_are_supported(self):
        tensor, _ = self.node._parse_response(response_data([image_part((0, 0, 255), "JPEG", True)]))
        self.assertEqual(tuple(tensor.shape), (1, 2, 3, 3))
        torch.testing.assert_close(tensor[0, 0, 0], torch.tensor([0.0, 0.0, 1.0]), atol=0.01, rtol=0)

    def test_legacy_response_without_mime_or_finish_reason(self):
        data = response_data()
        del data["candidates"][0]["finishReason"]
        del data["candidates"][0]["content"]["parts"][0]["inlineData"]["mimeType"]
        self.node._parse_response(data)

    def test_non_image_inline_data_is_not_selected(self):
        part = {"inlineData": {"mimeType": "application/octet-stream", "data": "DO_NOT_LOG"}}
        with self.assertRaisesRegex(RuntimeError, "没有生成图像"):
            self.node._parse_response(response_data([part]))

    def test_empty_candidates_content_parts_and_text_only_results(self):
        cases = [{}, {"candidates": []}, {"candidates": None},
                 {"candidates": [{"content": None}]}, response_data([]),
                 response_data([{"text": "只返回了文本"}])]
        for data in cases:
            with self.subTest(data=data), self.assertRaisesRegex(RuntimeError, "没有生成图像"):
                self.node._parse_response(data)

    def test_prompt_block_and_zero_token_diagnostics(self):
        data = {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": {"candidatesTokenCount": 0}}
        with self.assertRaisesRegex(RuntimeError, "candidatesTokenCount=0.*blockReason=SAFETY"):
            self.node._parse_response(data)

    def test_abnormal_finish_reason_rejects_partial_output(self):
        with self.assertRaisesRegex(RuntimeError, "MAX_TOKENS"):
            self.node._parse_response(response_data(finish_reason="MAX_TOKENS"))

    def test_malformed_response_shapes_have_bounded_errors(self):
        cases = [None, [], {"candidates": {}}, {"candidates": [None]},
                 {"candidates": [{"content": "wrong"}]},
                 {"candidates": [{"content": {"parts": "wrong"}}]},
                 response_data([None])]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(RuntimeError) as caught:
                self.node._parse_response(data)
            self.assertLess(len(str(caught.exception)), 200)

    def test_corrupt_final_image_reports_decode_error_without_data(self):
        private_data = "private-image-data-" * 50
        parts = [image_part(), {"inlineData": {"mimeType": "image/png", "data": private_data}}]
        with self.assertRaisesRegex(RuntimeError, "图片解码失败") as caught:
            self.node._parse_response(response_data(parts))
        self.assertNotIn(private_data, str(caught.exception))


class IntegrationContractTests(unittest.TestCase):
    def test_status_event_keeps_existing_frontend_contract(self):
        send = Mock()
        server = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(send_sync=send)))
        with patch.dict("sys.modules", {"server": server}):
            emit_runtime_status(42, "running", "请求中", 2.0, 1, 6, 360)
        event, data = send.call_args.args
        self.assertEqual(event, "lucknanobanana_status")
        self.assertEqual(data["node_id"], "42")
        self.assertEqual(data["timeout_seconds"], 360)
        self.assertEqual(data["status"], "running")

    def test_absent_comfyui_server_does_not_break_status_reporting(self):
        with patch.dict("sys.modules", {"server": None}):
            emit_runtime_status("42", "success")
        emit_runtime_status(None, "running")

    def test_example_workflow_uses_new_defaults_and_empty_key(self):
        workflow = json.loads((ROOT / "example_workflow.json").read_text())
        node = next(n for n in workflow["nodes"] if n["type"] == "LuckNanoBananaProNode")
        values = dict(zip(Node.INPUT_TYPES()["required"], node["widgets_values"]))
        self.assertEqual(len(values), 9)
        self.assertEqual(values["api_key (API密钥)"], "")
        self.assertEqual(values["model (模型)"], Node.NB21_MODEL)
        self.assertEqual(values["timeout_seconds (超时秒数)"], 360)


if __name__ == "__main__":
    unittest.main()
