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

def generate_image(prompt, output_path, width=1024, height=1024):
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

    print(f"Generating image ({width}x{height}) for prompt: {prompt[:50]}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.text}")

    data = response.json()
    base64_data = data["artifacts"][0]["base64"]
    
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(base64_data))
    print(f"Image saved to {output_path}")

def run_workflow(project_name, pages_data, intro_text, tags):
    project_dir = os.path.join(os.getcwd(), project_name)
    base_dir = os.path.join(project_dir, "base")
    final_dir = os.path.join(project_dir, "final")
    
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)
    
    # 尝试多个可能的中文字体路径以适应不同系统
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/google-droid-sans-fonts/DroidSansFallbackFull.ttf", # 适配 login2.bouchet
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Bold.otf",
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
    
    print(f"Workflow completed for {project_name}")
