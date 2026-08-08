#!/gpfs/gibbs/project/mane/dz288/nodejs/bin/python3
import os
import requests
import base64
import json
from PIL import Image, ImageDraw, ImageFont

# 微信公众号漫画处理器 - 仅中文版
def draw_multi_line_bubble(draw, text, position, font, padding=20):
    # Split text by explicit newlines or just wrap it
    lines = text.split('\n')
    
    # Calculate total height and max width
    total_h = 0
    max_w = 0
    line_metrics = []
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        line_metrics.append((tw, th))
        max_w = max(max_w, tw)
        total_h += th + 10 # line spacing
    
    total_h -= 10 # remove last spacing
    
    x, y_start = position
    # Center the bubble horizontally at the position
    bubble_w = max_w + 2 * padding
    bubble_h = total_h + 2 * padding
    
    bubble_x = x - (bubble_w // 2)
    bubble_y = y_start - (bubble_h // 2)
    
    rect_bbox = [bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h]
    
    # Draw bubble background
    draw.rounded_rectangle(rect_bbox, radius=20, fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    
    # Draw text
    curr_y = bubble_y + padding
    for i, line in enumerate(lines):
        tw, th = line_metrics[i]
        line_x = x - (tw // 2)
        draw.text((line_x, curr_y), line, font=font, fill=(0, 0, 0))
        curr_y += th + 10

def generate_image_nvidia(prompt, output_path, width=1024, height=1024):
    api_key = os.environ.get("NVIDIA_IMAGE_API_KEY")
    if not api_key:
        raise ValueError("Error: NVIDIA_IMAGE_API_KEY not found.")

    url = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height
    }

    print(f"Generating image via NVIDIA NIM ({width}x{height}) for prompt: {prompt[:50]}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"NVIDIA Error: {response.status_code} - {response.text}")

    data = response.json()
    base64_data = data["artifacts"][0]["base64"]
    
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(base64_data))
    print(f"Image saved to {output_path} (via NVIDIA)")

def check_ollama(model="x/flux2-klein:latest"):
    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        # Quick check if Ollama is running and has the model
        response = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            for m in models:
                if m.get("name") == model:
                    return True
    except:
        pass
    return False

def generate_image_ollama(prompt, output_path, width=1024, height=1024, model="x/flux2-klein:latest"):
    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    url = f"{ollama_host}/v1/images/generations"
    
    payload = {
        "prompt": prompt,
        "model": model,
        "size": f"{width}x{height}"
    }

    print(f"Generating image via Ollama ({width}x{height}) for prompt: {prompt[:50]}...")
    # Image generation can take a while, especially on local hardware
    response = requests.post(url, json=payload, timeout=600)
    
    if response.status_code != 200:
        raise Exception(f"Ollama Error: {response.status_code} - {response.text}")

    data = response.json()
    # OpenAI compatible response usually has data[0].b64_json
    img_entry = data.get("data", [{}])[0]
    base64_data = img_entry.get("b64_json")
    
    if not base64_data:
        # Try to extract from data URI in url field if b64_json is missing
        img_url = img_entry.get("url")
        if img_url and img_url.startswith("data:image"):
            base64_data = img_url.split(",")[1]
    
    if not base64_data:
        raise Exception(f"No image data found in Ollama response: {data}")
        
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(base64_data))
    print(f"Image saved to {output_path} (via Ollama)")

def generate_image(prompt, output_path, width=1024, height=1024):
    # Try Ollama first if it's available and has the model
    try:
        if check_ollama():
            generate_image_ollama(prompt, output_path, width, height)
            return
    except Exception as e:
        print(f"Ollama generation attempt failed: {e}")
        print("Falling back to NVIDIA NIM...")

    # Fallback to NVIDIA NIM
    generate_image_nvidia(prompt, output_path, width, height)

def run_workflow(project_name, pages_data, intro_text, tags, save_drafts=True, storyboard=None, character_anchors=None):
    project_dir = os.path.join(os.getcwd(), project_name)
    base_dir = os.path.join(project_dir, "base")
    final_dir = os.path.join(project_dir, "final")
    drafts_dir = os.path.join(project_dir, "drafts")
    
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)
    
    if save_drafts:
        os.makedirs(drafts_dir, exist_ok=True)
    
    # 尝试多个可能的中文字体路径以适应不同系统
    font_paths = [
        "/gpfs/gibbs/project/mane/dz288/nodejs/share/fonts/noto/NotoSansSC-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/google-droid-sans-fonts/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Bold.otf",
        "/usr/share/fonts/google-droid/DroidSansFallback.ttf",
    ]
    
    font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 40)
                print(f"Using font: {path}")
                break
            except:
                continue
    
    if font is None:
        print("Warning: No CJK font found, falling back to default.")
        font = ImageFont.load_default()
    
    for i, page in enumerate(pages_data):
        page_label = page.get("label", f"Page {i}")
        base_path = os.path.join(base_dir, f"page_{i}.png")
        final_path = os.path.join(final_dir, f"page_{i}.webp")
        
        # Generate image
        width = page.get("width", 1024)
        height = page.get("height", 1024)
        generate_image(page["prompt"], base_path, width, height)
        
        # Add text
        img = Image.open(base_path)
        draw = ImageDraw.Draw(img)
        
        text = page.get("text", "")
        if text:
            # Position text at the bottom-ish
            text_pos = (width // 2, int(height * 0.85))
            draw_multi_line_bubble(draw, text, text_pos, font)
            
        img.save(final_path, "WEBP")
        print(f"Final image saved to {final_path}")

    # Write POST_INFO.md
    with open(os.path.join(project_dir, "POST_INFO.md"), "w", encoding='utf-8') as f:
        f.write(f"# Post Information\n\n## Introduction\n{intro_text}\n\n## Tags\n{' '.join(tags)}")

    if save_drafts:
        # Save prompts.json — every page's prompt, dimensions, text, and label
        prompts_out = []
        for i, page in enumerate(pages_data):
            prompts_out.append({
                "page": i,
                "label": page.get("label", f"Page {i}"),
                "prompt": page.get("prompt", ""),
                "width": page.get("width", 1024),
                "height": page.get("height", 1024),
                "text": page.get("text", ""),
                "base_file": f"base/page_{i}.png",
                "final_file": f"final/page_{i}.webp",
            })
        with open(os.path.join(drafts_dir, "prompts.json"), "w", encoding='utf-8') as f:
            json.dump(prompts_out, f, ensure_ascii=False, indent=2)
        print(f"Drafts saved: prompts.json")

        # Save storyboard.md — story concept, storyline, shot-by-shot breakdown
        if storyboard:
            with open(os.path.join(drafts_dir, "storyboard.md"), "w", encoding='utf-8') as f:
                f.write(storyboard)
            print(f"Drafts saved: storyboard.md")

        # Save character_anchors.md — character design reference
        if character_anchors:
            with open(os.path.join(drafts_dir, "character_anchors.md"), "w", encoding='utf-8') as f:
                f.write(character_anchors)
            print(f"Drafts saved: character_anchors.md")
    
    print(f"Workflow completed for {project_name}")
