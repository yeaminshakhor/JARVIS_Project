from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from PIL import Image

from .config import ConfigManager
from .utils import env_get, load_env_map


ENV = load_env_map(".env")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Data" / "generated_images"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = PROJECT_ROOT / "Frontend" / "Files"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_GENERATION_DATA_FILE = FRONTEND_DIR / "ImageGeneration.data"

HUGGINGFACE_API_KEY = env_get("HUGGINGFACE_API_KEY", "HUGGINGFACEAPIKEY", "HF_API_KEY", "HF_TOKEN", env_map=ENV)
REPLICATE_API_KEY = env_get("REPLICATE_API_KEY", default="", env_map=ENV)
DEEPAI_API_KEY = env_get("DEEPAI_API_KEY", default="", env_map=ENV)
LOCAL_SD_URL = env_get("LOCAL_SD_URL", default="http://127.0.0.1:7860", env_map=ENV)

STYLES = {
    "realistic": "photo realistic, 4k, detailed",
    "anime": "anime style, manga, cel shaded",
    "oil painting": "oil painting, artistic, canvas",
    "sketch": "pencil sketch, black and white",
}


@dataclass
class GeneratedImage:
    path: str
    provider: str
    prompt: str


class BaseImageProvider:
    name = "provider"

    async def generate(self, prompt: str, count: int = 1) -> List[bytes]:
        raise NotImplementedError


class StabilityAIProvider(BaseImageProvider):
    name = "huggingface-stability"
    api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

    async def generate(self, prompt: str, count: int = 1) -> List[bytes]:
        if not HUGGINGFACE_API_KEY:
            return []

        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}

        def _call_once() -> Optional[bytes]:
            response = requests.post(self.api_url, headers=headers, json={"inputs": prompt}, timeout=90)
            if response.status_code != 200:
                return None
            ctype = (response.headers.get("content-type") or "").lower()
            if "image" not in ctype:
                return None
            return response.content

        tasks = [asyncio.to_thread(_call_once) for _ in range(max(1, count))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = []
        for item in results:
            if isinstance(item, (bytes, bytearray)) and len(item) > 100:
                out.append(bytes(item))
        return out


class ReplicateProvider(BaseImageProvider):
    name = "replicate"

    async def generate(self, prompt: str, count: int = 1) -> List[bytes]:
        if not REPLICATE_API_KEY:
            return []

        def _call_once() -> Optional[bytes]:
            try:
                response = requests.post(
                    "https://api.replicate.com/v1/predictions",
                    headers={
                        "Authorization": f"Token {REPLICATE_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "version": "ac732df83cea7fff1fecf3eb77213323c7801593f1ee5e58c94ff5fa94f1f9d1",
                        "input": {"prompt": prompt},
                    },
                    timeout=40,
                )
                if response.status_code not in {200, 201}:
                    return None
                data = response.json()
                get_url = str(data.get("urls", {}).get("get") or "").strip()
                if not get_url:
                    return None
                for _ in range(25):
                    poll = requests.get(get_url, headers={"Authorization": f"Token {REPLICATE_API_KEY}"}, timeout=20)
                    if poll.status_code != 200:
                        return None
                    payload = poll.json()
                    status = str(payload.get("status") or "")
                    if status == "succeeded":
                        output = payload.get("output")
                        if isinstance(output, list) and output:
                            img_url = str(output[0])
                        else:
                            img_url = str(output or "")
                        if not img_url:
                            return None
                        img = requests.get(img_url, timeout=30)
                        if img.status_code == 200 and len(img.content) > 100:
                            return img.content
                        return None
                    if status in {"failed", "canceled"}:
                        return None
                    time.sleep(2.0)
                return None
            except Exception:
                return None

        tasks = [asyncio.to_thread(_call_once) for _ in range(max(1, count))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [bytes(item) for item in results if isinstance(item, (bytes, bytearray)) and len(item) > 100]


class DeepAIIProvider(BaseImageProvider):
    name = "deepai"

    async def generate(self, prompt: str, count: int = 1) -> List[bytes]:
        if not DEEPAI_API_KEY:
            return []

        def _call_once() -> Optional[bytes]:
            try:
                response = requests.post(
                    "https://api.deepai.org/api/text2img",
                    headers={"api-key": DEEPAI_API_KEY},
                    data={"text": prompt},
                    timeout=60,
                )
                if response.status_code != 200:
                    return None
                payload = response.json()
                url = str(payload.get("output_url") or "").strip()
                if not url:
                    return None
                img = requests.get(url, timeout=30)
                if img.status_code == 200 and len(img.content) > 100:
                    return img.content
            except Exception:
                return None
            return None

        tasks = [asyncio.to_thread(_call_once) for _ in range(max(1, count))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [bytes(item) for item in results if isinstance(item, (bytes, bytearray)) and len(item) > 100]


class LocalSDProvider(BaseImageProvider):
    name = "local-stable-diffusion"

    async def generate(self, prompt: str, count: int = 1) -> List[bytes]:
        endpoint = f"{LOCAL_SD_URL.rstrip('/')}/sdapi/v1/txt2img"

        def _call() -> List[bytes]:
            try:
                response = requests.post(
                    endpoint,
                    json={
                        "prompt": prompt,
                        "batch_size": max(1, count),
                        "n_iter": 1,
                        "width": 768,
                        "height": 768,
                    },
                    timeout=120,
                )
                if response.status_code != 200:
                    return []
                data = response.json()
                out = []
                for encoded in data.get("images", [])[:count]:
                    encoded = str(encoded or "")
                    if not encoded:
                        continue
                    raw = base64.b64decode(encoded.split(",", 1)[1] if "," in encoded else encoded)
                    if len(raw) > 100:
                        out.append(raw)
                return out
            except Exception:
                return []

        return await asyncio.to_thread(_call)


class EnhancedImageGenerator:
    def __init__(self):
        self.providers = [
            StabilityAIProvider(),
            ReplicateProvider(),
            DeepAIIProvider(),
            LocalSDProvider(),
        ]

    def _sanitize(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (text or "").strip())
        return cleaned[:80] or "image"

    def _save_images(self, prompt: str, provider: str, payloads: List[bytes]) -> List[GeneratedImage]:
        slug = self._sanitize(prompt)
        saved: List[GeneratedImage] = []
        for idx, blob in enumerate(payloads, 1):
            try:
                image = Image.open(io.BytesIO(blob))
                image.verify()
                image = Image.open(io.BytesIO(blob))
                path = DATA_DIR / f"{slug}_{provider}_{idx}.png"
                image.save(path)
                saved.append(GeneratedImage(path=str(path), provider=provider, prompt=prompt))
            except Exception:
                continue
        return saved

    async def generate(self, prompt: str, count: int = 4, style: str = "realistic") -> Dict[str, object]:
        base_prompt = (prompt or "").strip()
        if not base_prompt:
            return {"ok": False, "message": "Empty prompt", "images": [], "provider": ""}

        style_suffix = STYLES.get(style, STYLES["realistic"])
        styled_prompt = f"{base_prompt}, {style_suffix}" if style_suffix else base_prompt

        provider_errors = []
        for provider in self.providers:
            try:
                payloads = await provider.generate(styled_prompt, count=max(1, int(count)))
                if not payloads:
                    provider_errors.append(f"{provider.name}: no result")
                    continue
                saved = self._save_images(base_prompt, provider.name, payloads)
                if not saved:
                    provider_errors.append(f"{provider.name}: invalid image payload")
                    continue
                return {
                    "ok": True,
                    "message": f"Generated {len(saved)} image(s)",
                    "provider": provider.name,
                    "images": [
                        {
                            "path": item.path,
                            "url": Path(item.path).as_uri(),
                            "provider": item.provider,
                            "prompt": item.prompt,
                        }
                        for item in saved
                    ],
                    "progress": 100,
                }
            except Exception as exc:
                provider_errors.append(f"{provider.name}: {exc}")
                continue

        return {
            "ok": False,
            "message": "All image providers failed",
            "provider": "",
            "images": [],
            "progress": 100,
            "errors": provider_errors,
        }


async def batch_generate(prompts: List[str], style: str = "realistic") -> List[Dict[str, object]]:
    generator = EnhancedImageGenerator()
    tasks = [generator.generate(prompt, count=1, style=style) for prompt in prompts]
    return await asyncio.gather(*tasks, return_exceptions=False)


def generate_images_with_progress(prompt: str, count: int = 4, style: str = "realistic") -> Dict[str, object]:
    generator = EnhancedImageGenerator()
    return asyncio.run(generator.generate(prompt=prompt, count=count, style=style))


def EnhancedGenerateImages(prompt: str):
    result = generate_images_with_progress(prompt=prompt, count=4, style="realistic")
    return result


def generate_images_fast(prompt: str):
    return EnhancedGenerateImages(prompt)


def initialize_files():
    if not IMAGE_GENERATION_DATA_FILE.exists():
        IMAGE_GENERATION_DATA_FILE.write_text("None,False", encoding="utf-8")


def check_environment():
    return True


if __name__ == "__main__":
    initialize_files()
    while True:
        try:
            raw = IMAGE_GENERATION_DATA_FILE.read_text(encoding="utf-8").strip()
            if raw and raw != "None,False":
                prompt, flag = raw.split(",", 1)
                if flag.strip().lower() == "true":
                    result = EnhancedGenerateImages(prompt.strip())
                    IMAGE_GENERATION_DATA_FILE.write_text(f"{prompt.strip()},False", encoding="utf-8")
                    print(json.dumps(result, indent=2))
            time.sleep(1.0)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(1.0)
