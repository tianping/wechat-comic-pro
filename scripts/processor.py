#!/gpfs/gibbs/project/mane/dz288/nodejs/bin/python3
import os
import shutil
import subprocess
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

def _find_publish_script():
    """Locate aws-wechat-article-publish/scripts/publish.py relative to this skill dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "aws-wechat-article-publish", "scripts", "publish.py"),
        os.path.join(os.getcwd(), "skills", "aws-wechat-article-publish", "scripts", "publish.py"),
    ]
    for p in candidates:
        normalised = os.path.normpath(p)
        if os.path.isfile(normalised):
            return normalised
    return None


def publish_to_wechat(project_dir, pages_data, title, author, digest, publish_account=None):
    """Adapt comic output to aws-wechat-article-publish format and call publish.py full.

    Creates article.yaml, article.html, imgs/, cover.* inside project_dir,
    then invokes publish.py full to push to WeChat draft box.

    Returns the subprocess exit code (0 = success).
    """
    publish_script = _find_publish_script()
    if not publish_script:
        print("[WARN] aws-wechat-article-publish skill not found — skipping WeChat publish.")
        print("       Install it with: clawhub install aws-wechat-article-publish")
        return 1

    project_dir = os.path.abspath(project_dir)
    final_dir = os.path.join(project_dir, "final")
    imgs_dir = os.path.join(project_dir, "imgs")
    os.makedirs(imgs_dir, exist_ok=True)

    # Page 0 is the cover; pages 1..N are body images
    cover_src = os.path.join(final_dir, "page_0.webp")
    cover_dst = os.path.join(project_dir, "cover.webp")
    if os.path.isfile(cover_src):
        shutil.copy2(cover_src, cover_dst)
        print(f"Cover copied: {cover_dst}")
    else:
        print("[WARN] No page_0.webp found for cover — publish.py will need a cover image.")

    # Copy body pages (1..N) to imgs/
    body_imgs = []
    for i, page in enumerate(pages_data):
        if i == 0:
            continue  # page 0 = cover
        src = os.path.join(final_dir, f"page_{i}.webp")
        dst = os.path.join(imgs_dir, f"page_{i}.webp")
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            body_imgs.append(f"page_{i}.webp")
            print(f"Body image copied: {dst}")

    # Build article.html — simple sequential image gallery
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset=\"utf-8\"></head><body>",
        "<section style=\"max-width:640px;margin:0 auto;\">",
    ]
    for img_name in body_imgs:
        html_parts.append(
            f'  <p style="text-align:center;margin:0;padding:0;">'
            f'<img src="imgs/{img_name}" style="width:100%;" /></p>'
        )
    html_parts.append("</section>")
    html_parts.append("</body></html>")
    html_content = "\n".join(html_parts)

    article_html_path = os.path.join(project_dir, "article.html")
    with open(article_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"article.html generated ({len(body_imgs)} body images)")

    # Prepend fixed prefix to title and enforce ≤64 chars (WeChat API limit)
    TITLE_PREFIX = "漫画 | "
    full_title = TITLE_PREFIX + title
    if len(full_title) > 64:
        # Truncate the user title to fit prefix within 64 chars
        max_title_len = 64 - len(TITLE_PREFIX)
        print(f"[WARN] Title with prefix is {len(full_title)} chars, truncating to 64 (WeChat API limit)")
        title = title[:max_title_len]
        full_title = TITLE_PREFIX + title

    # Build article.yaml — digest must be ≤120 chars (WeChat API limit)
    raw_digest = digest or intro_text_from_post_info(project_dir)
    if len(raw_digest) > 120:
        print(f"[WARN] digest is {len(raw_digest)} chars, truncating to 120 (WeChat API limit)")
        raw_digest = raw_digest[:120]
    article_yaml = {
        "title": full_title,
        "author": author or "",
        "digest": raw_digest,
        "content_source": "article.html",
        "publish_completed": False,
    }
    import yaml  # lazy import
    article_yaml_path = os.path.join(project_dir, "article.yaml")
    with open(article_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(article_yaml, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"article.yaml generated")

    # Call publish.py full
    cmd = ["python3", publish_script, "full", project_dir]
    if publish_account:
        cmd.extend(["--account", str(publish_account)])
    # publish.py reads aws.env + .aws-article/config.yaml from cwd (repo root)
    print(f"Calling publish.py: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.getcwd())
    if result.returncode == 0:
        print("[OK] WeChat publish completed (check draft box).")
    else:
        print(f"[ERROR] publish.py exited with code {result.returncode}")
    return result.returncode


def intro_text_from_post_info(project_dir):
    """Extract the introduction text from POST_INFO.md if it exists."""
    path = os.path.join(project_dir, "POST_INFO.md")
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Parse the Introduction section
    if "## Introduction" in content:
        part = content.split("## Introduction", 1)[1]
        part = part.split("## Tags", 1)[0]
        return part.strip()
    return ""


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
