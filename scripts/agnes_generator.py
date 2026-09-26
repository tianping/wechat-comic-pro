#!/usr/bin/env python3
"""Agnes 生图生成器（wechat-comic-pro 专用，import 模块）。

协议与 wechat-english/scripts/agnes_image.py 一致：
- endpoint: https://apihub.agnes-ai.com/v1/images/generations
- 降级链: agnes-image-2.5-flash → 2.1 → 2.0（最新优先，免费）
- key: ~/.openclaw/openclaw.json → models.providers.custom-agnes.apiKey
       或 AGNES_API_KEY 环境变量（与 agnes-3.0-flash 文本模型共用同一把）

宽高比映射（Agnes 支持 1:1 / 3:4 / 4:3 / 16:9 / 9:16 / 2:3 / 3:2 / 21:9）：
- 漫画封面 2.35:1  → 21:9
- 正文页  1:1      → 1:1
- 其他（接近 16:9）→ 16:9
"""
import base64
import json
import urllib.request
from pathlib import Path

API_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
MODEL_FALLBACK = ["agnes-image-2.5-flash", "agnes-image-2.1-flash", "agnes-image-2.0-flash"]
# 宽/高 → 支持的 ratio
_RATIO_ORDER = [
    ("1:1",   1.0),
    ("4:3",   4/3),
    ("16:9",  16/9),
    ("3:2",   1.5),
    ("21:9",  21/9),
    ("2:3",   2/3),
    ("3:4",   0.75),
    ("9:16",  9/16),
]


def _ratio_for(width: int, height: int) -> str:
    """挑与目标宽高的比例最接近的支持档位。"""
    target = width / height if height else 1.0
    best, best_diff = "1:1", 1e9
    for name, ratio in _RATIO_ORDER:
        d = abs(target - ratio)
        if d < best_diff:
            best, best_diff = name, d
    return best


def load_key() -> str:
    import os
    env = os.environ.get("AGNES_API_KEY", "").strip()
    if env:
        return env
    cfg = Path.home() / ".openclaw" / "openclaw.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        key = data.get("models", {}).get("providers", {}).get("custom-agnes", {}).get("apiKey", "")
        if key:
            return key
    except Exception:
        pass
    raise ValueError("找不到 Agnes API key（openclaw.json 的 custom-agnes.apiKey 或 AGNES_API_KEY）")


def _call_once(key: str, model: str, prompt: str, ratio: str) -> bytes:
    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1K",
        "ratio": ratio,
        "return_base64": True,
    }
    req = urllib.request.Request(
        API_ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    item = data["data"][0]
    b64 = item.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = item.get("url")
    if url:
        with urllib.request.urlopen(url, timeout=120) as r2:
            return r2.read()
    raise RuntimeError(f"响应中无图片数据: {json.dumps(data)[:200]}")


def generate_image(prompt, output_path, width=1024, height=1024):
    """与 processor.generate_image 同签名：Ollama→NVIDIA 链路替换为 Agnes 降级链。

    成功后把图写到 output_path（任意扩展名，PNG 字节），并回显尺寸。
    """
    from PIL import Image
    key = load_key()
    ratio = _ratio_for(width, height)
    last_err = None
    for model in MODEL_FALLBACK:
        try:
            print(f"Generating image via Agnes {model} ({width}x{height} → {ratio}) for prompt: {prompt[:50]}...")
            blob = _call_once(key, model, prompt, ratio)
            with open(output_path, "wb") as f:
                f.write(blob)
            im = Image.open(output_path)
            print(f"Image saved to {output_path} (via Agnes {model}, {im.size[0]}x{im.size[1]}, {len(blob)} bytes)")
            return
        except Exception as e:
            last_err = e
            print(f"[FAIL] {model}: {e}")
    raise RuntimeError(f"Agnes 所有模型均失败，最后错误: {last_err}")
