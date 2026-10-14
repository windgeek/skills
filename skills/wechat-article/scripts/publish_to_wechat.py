#!/usr/bin/env python3
"""Publish a WeChat article draft from wechat-typeset HTML.

This script intentionally does not format Markdown into WeChat HTML. The
article body must come from the wechat-typeset skill as a clean, validated
<section>...</section> fragment.

Usage:
  python3 publish_to_wechat.py article.md --content-html article-gzh-排版.html
  python3 publish_to_wechat.py article.md --preview --content-html article-gzh-排版.html
  python3 publish_to_wechat.py article.md --cover cover.jpg --cover-no-title
  python3 publish_to_wechat.py --publish-status <publish_id>
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import textwrap
import uuid
import zlib
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen


SKILL_ROOT = Path(__file__).resolve().parent.parent
TYPESET_ROOT = Path(os.environ.get("WECHAT_TYPESET_HOME", SKILL_ROOT.parent / "wechat-typeset")).expanduser()
GZH_VALIDATE = TYPESET_ROOT / "scripts" / "check_html.py"
GZH_WRAP_PREVIEW = TYPESET_ROOT / "scripts" / "preview.py"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_env_file(SKILL_ROOT / ".env")
load_env_file(Path.cwd() / ".env")

APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
BASE_URL = "https://api.weixin.qq.com/cgi-bin"


def require_wechat_credentials() -> None:
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("缺少 WECHAT_APP_ID 或 WECHAT_APP_SECRET，请在 .env 中配置。")


def _url_with_params(url: str, params: dict[str, str]) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(params)}"


def _read_json_response(req: Request, timeout: int = 60) -> dict:
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def http_get_json(url: str, params: dict[str, str], timeout: int = 20) -> dict:
    req = Request(_url_with_params(url, params), method="GET")
    return _read_json_response(req, timeout=timeout)


def http_post_json(url: str, params: dict[str, str], payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        _url_with_params(url, params),
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return _read_json_response(req, timeout=timeout)


def http_post_multipart(
    url: str,
    params: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
    timeout: int = 60,
) -> dict:
    boundary = f"----codex-wechat-{uuid.uuid4().hex}"
    body = bytearray()
    for field, (filename, data, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{field}"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = Request(
        _url_with_params(url, params),
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return _read_json_response(req, timeout=timeout)


def get_access_token() -> str:
    require_wechat_credentials()
    data = http_get_json(
        f"{BASE_URL}/token",
        {
            "grant_type": "client_credential",
            "appid": APP_ID,
            "secret": APP_SECRET,
        },
        timeout=20,
    )
    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败: {data}")
    return data["access_token"]


def _content_type_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def upload_thumb_image(token: str, image_path: str) -> str:
    """Upload cover image to WeChat permanent material storage."""
    with open(image_path, "rb") as f:
        data = http_post_multipart(
            f"{BASE_URL}/material/add_material",
            {"access_token": token, "type": "image"},
            {
                "media": (
                    os.path.basename(image_path),
                    f.read(),
                    _content_type_for(image_path),
                )
            },
            timeout=60,
        )
    if "media_id" not in data:
        raise RuntimeError(f"上传封面图失败: {data}")
    return data["media_id"]


def upload_content_image(token: str, image_data: bytes, filename: str) -> str:
    """Upload an in-article image and return the WeChat CDN URL."""
    data = http_post_multipart(
        f"{BASE_URL}/media/uploadimg",
        {"access_token": token},
        {"media": (filename, image_data, _content_type_for(filename))},
        timeout=60,
    )
    if "url" not in data:
        raise RuntimeError(f"上传正文图片失败: {data}")
    return data["url"]


def create_draft(token: str, articles: list[dict]) -> str:
    data = http_post_json(
        f"{BASE_URL}/draft/add",
        {"access_token": token},
        {"articles": articles},
        timeout=60,
    )
    if "media_id" not in data:
        raise RuntimeError(f"创建草稿失败: {data}")
    return data["media_id"]


def freepublish(token: str, media_id: str) -> str:
    data = http_post_json(
        f"{BASE_URL}/freepublish/submit",
        {"access_token": token},
        {"media_id": media_id},
        timeout=60,
    )
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"发布失败: {data}")
    return data.get("publish_id", "")


def get_publish_status(token: str, publish_id: str) -> dict:
    data = http_post_json(
        f"{BASE_URL}/freepublish/get",
        {"access_token": token},
        {"publish_id": publish_id},
        timeout=60,
    )
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"查询发布状态失败: {data}")
    return data


def parse_article_md(filepath: str) -> dict:
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.splitlines()

    title = ""
    title_backup = ""
    in_title_options = False
    body_lines: list[str] = []
    source_line = ""

    for line in lines:
        stripped = line.strip()
        if stripped == "## 标题备选":
            in_title_options = True
            continue
        if in_title_options:
            match = re.match(r"^\d+\.\s*(.+)$", stripped)
            if match and not title_backup:
                title_backup = match.group(1).strip()
            if stripped.startswith("# "):
                in_title_options = False
            elif stripped.startswith("## ") and stripped != "## 标题备选":
                in_title_options = False
            else:
                continue
        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
            continue
        body_lines.append(line)

    if not title:
        title = title_backup or Path(filepath).stem

    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    if body_lines:
        last = body_lines[-1].strip()
        if "来源" in last or "信息主要" in last or "source" in last.lower():
            source_line = last

    body = "\n".join(body_lines)
    plain = re.sub(r"!\[[^\]]*]\([^)]+\)", "", body)
    plain = re.sub(r"`{1,3}[^`]*`{1,3}", "", plain, flags=re.DOTALL)
    plain = re.sub(r"[#>*_\-\[\]()`|]", "", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    digest = plain[:120]

    return {"title": title, "digest": digest, "source_line": source_line}


def find_gzh_html(md_path: str, explicit_html: str | None = None) -> Path:
    if explicit_html:
        path = Path(explicit_html).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(f"找不到排版 HTML: {path}")
        return path

    md = Path(md_path)
    parent = md.parent
    stem = md.stem
    stems = [stem]
    if stem.endswith("-gzh"):
        stems.append(stem[:-4])
    else:
        stems.append(f"{stem}-gzh")

    candidates: list[Path] = []
    for item in dict.fromkeys(stems):
        candidates.extend(parent.glob(f"{item}-排版.html"))

    candidates = [
        path
        for path in candidates
        if path.is_file()
    ]
    if not candidates:
        raise FileNotFoundError(
            "未找到 wechat-typeset 生成的正文 HTML（*-排版.html）。请先用 wechat-typeset 排版，"
            "或通过 --content-html 指定 HTML 文件。"
        )
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def validate_gzh_html(html_path: Path, allow_warnings: bool = False) -> str:
    if not GZH_VALIDATE.exists():
        raise FileNotFoundError(f"找不到 wechat-typeset 校验脚本: {GZH_VALIDATE}")
    result = subprocess.run(
        [sys.executable, str(GZH_VALIDATE), str(html_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip())
    warn = re.search(r"WARNING × (\d+)", output)
    if not allow_warnings and warn and int(warn.group(1)) > 0:
        raise RuntimeError(
            output.strip()
            + "\n\n校验仍有 WARNING。请先按 wechat-typeset 要求修到 0，"
            "或临时加 --allow-gzh-warnings。"
        )
    return output.strip()


def wrap_gzh_preview(html_path: Path) -> Path:
    if not GZH_WRAP_PREVIEW.exists():
        raise FileNotFoundError(f"找不到 wechat-typeset 预览脚本: {GZH_WRAP_PREVIEW}")
    result = subprocess.run(
        [sys.executable, str(GZH_WRAP_PREVIEW), str(html_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip())
    stem = html_path.stem[:-3] if html_path.stem.endswith("-排版") else html_path.stem
    preview = html_path.with_name(f"{stem}-预览.html")
    return preview


def _resolve_image_path(src: str, html_dir: Path, md_dir: Path) -> Path | None:
    src = html_lib.unescape(src).strip()
    parsed = urlparse(src)
    if parsed.scheme in {"http", "https", "data"}:
        return None
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))

    clean_src = unquote(src.split("#", 1)[0].split("?", 1)[0])
    path = Path(clean_src)
    if path.is_absolute():
        return path

    html_relative = html_dir / path
    if html_relative.exists():
        return html_relative
    return md_dir / path


def upload_local_images_in_html(
    html_content: str,
    html_path: Path,
    md_path: str,
    token: str,
) -> str:
    md_dir = Path(md_path).resolve().parent
    html_dir = html_path.resolve().parent

    def replace_src(match: re.Match) -> str:
        prefix, quote, src, suffix = match.groups()
        image_path = _resolve_image_path(src, html_dir, md_dir)
        if image_path is None:
            return match.group(0)
        if not image_path.exists():
            raise FileNotFoundError(f"HTML 引用的本地图片不存在: {image_path}")
        with open(image_path, "rb") as f:
            wechat_url = upload_content_image(token, f.read(), image_path.name)
        print(f"  上传正文图片: {image_path.name} → {wechat_url[:64]}...")
        return f"{prefix}{quote}{wechat_url}{suffix}"

    return re.sub(
        r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])([^"\']+)(\2)',
        replace_src,
        html_content,
        flags=re.IGNORECASE,
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def generate_plain_cover_png() -> str:
    width, height = 900, 383
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            shade = int(28 + (y / height) * 34)
            accent = int(42 + (x / width) * 16)
            rows.extend((shade, shade + 2, accent + 20))

    raw = bytes(rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(png)
    tmp.close()
    return tmp.name


def generate_cover(title: str, bg_image_data: bytes | None = None) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ModuleNotFoundError:
        print("提示: 未安装 Pillow，生成无标题简洁 PNG 封面作为兜底。")
        return generate_plain_cover_png()

    width, height = 900, 383
    if bg_image_data:
        bg = Image.open(BytesIO(bg_image_data)).convert("RGB")
        target_ratio = width / height
        image_ratio = bg.width / bg.height
        if image_ratio > target_ratio:
            new_width = int(bg.height * target_ratio)
            left = (bg.width - new_width) // 2
            bg = bg.crop((left, 0, left + new_width, bg.height))
        else:
            new_height = int(bg.width / target_ratio)
            top = (bg.height - new_height) // 2
            bg = bg.crop((0, top, bg.width, top + new_height))
        img = bg.resize((width, height), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    else:
        img = Image.new("RGB", (width, height), color=(28, 31, 36))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            shade = int(28 + (y / height) * 32)
            draw.line([(0, y), (width, y)], fill=(shade, shade + 2, shade + 6))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(height):
        alpha = int(90 + (y / height) * 80)
        overlay_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font = ImageFont.load_default()
    for font_path in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, 42)
                break
            except OSError:
                continue

    lines = textwrap.wrap(title, width=14)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:13] + "…"

    line_height = 58
    total_height = len(lines) * line_height
    y = (height - total_height) // 2 + 12
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x + 1, y + 1), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
        y += line_height

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, "JPEG", quality=92)
    return tmp.name


def prepare_cover(token: str, title: str, cover_path: str | None, cover_no_title: bool) -> str:
    if cover_path:
        cover = Path(cover_path).expanduser()
        if not cover.is_absolute():
            cover = Path.cwd() / cover
        if not cover.exists():
            raise FileNotFoundError(f"封面图不存在: {cover}")
        if cover_no_title:
            print(f"使用指定封面图（不叠加标题）: {cover}")
            return upload_thumb_image(token, str(cover))
        print(f"使用指定封面底图并叠加标题: {cover}")
        with open(cover, "rb") as f:
            generated = generate_cover(title, f.read())
    else:
        print("未指定封面，生成简洁标题封面。")
        generated = generate_cover(title)

    try:
        return upload_thumb_image(token, generated)
    finally:
        try:
            os.unlink(generated)
        except OSError:
            pass


def publish(
    md_path: str,
    content_html: str | None,
    cover_path: str | None,
    cover_no_title: bool,
    publish_now: bool,
    allow_gzh_warnings: bool,
    author: str,
    digest_override: str | None,
    preview_only: bool,
) -> str | None:
    article = parse_article_md(md_path)
    html_path = find_gzh_html(md_path, content_html)
    print(f"文章标题: {article['title']}")
    print(f"使用排版 HTML: {html_path}")

    validation = validate_gzh_html(html_path, allow_warnings=allow_gzh_warnings)
    print(validation)

    if preview_only:
        preview = wrap_gzh_preview(html_path)
        print(f"\n预览页已生成: {preview}")
        return None

    print("获取 access_token...")
    token = get_access_token()
    print("成功")

    html_content = html_path.read_text(encoding="utf-8")
    html_content = upload_local_images_in_html(html_content, html_path, md_path, token)

    print("准备封面...")
    thumb_media_id = prepare_cover(token, article["title"], cover_path, cover_no_title)
    print("封面上传成功")

    digest = digest_override or article["digest"]
    author_name = author or os.environ.get("WECHAT_AUTHOR", "")
    source_url = os.environ.get("WECHAT_CONTENT_SOURCE_URL", "")

    print("创建草稿...")
    draft_id = create_draft(
        token,
        [
            {
                "title": article["title"],
                "content": html_content,
                "thumb_media_id": thumb_media_id,
                "author": author_name,
                "digest": digest,
                "content_source_url": source_url,
                "need_open_comment": 1,
            }
        ],
    )
    print(f"草稿创建成功: {draft_id}")

    if publish_now:
        print("提交发布...")
        publish_id = freepublish(token, draft_id)
        print(f"已提交发布: {publish_id}")

    return draft_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 wechat-typeset 排好的 HTML 创建微信公众号草稿。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            注意:
              本脚本不做 Markdown 排版。正文 HTML 必须先由 wechat-typeset 生成并通过校验。
              如果不传 --content-html，脚本会在 Markdown 同目录查找 *_排版_*.html。
            """
        ),
    )
    parser.add_argument("markdown", nargs="?", help="文章母稿或 gzh 输入稿 Markdown")
    parser.add_argument("--content-html", help="wechat-typeset 生成的 *-排版.html")
    parser.add_argument("--preview", action="store_true", help="只生成预览页，不发布")
    parser.add_argument("--cover", help="封面图路径")
    parser.add_argument("--cover-no-title", action="store_true", help="封面图不再叠加标题")
    parser.add_argument("--publish", action="store_true", help="创建草稿后直接提交发布")
    parser.add_argument("--allow-gzh-warnings", action="store_true", help="允许校验 WARNING")
    parser.add_argument("--author", default="", help="公众号作者名，默认读取 WECHAT_AUTHOR")
    parser.add_argument("--digest", help="公众号摘要，默认从 Markdown 正文提取")
    parser.add_argument("--publish-status", help="查询 publish_id 状态")
    parser.add_argument("--with-images", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-images", action="store_true", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.publish_status:
            token = get_access_token()
            status = get_publish_status(token, args.publish_status)
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return

        if args.with_images or args.no_images:
            print("提示: --with-images/--no-images 已弃用。正文图片请在 Markdown 里处理，由 wechat-typeset 排进 HTML。")

        if not args.markdown:
            parser.error("缺少 Markdown 文件路径")
        if not Path(args.markdown).exists():
            raise FileNotFoundError(f"文件不存在: {args.markdown}")

        publish(
            md_path=args.markdown,
            content_html=args.content_html,
            cover_path=args.cover,
            cover_no_title=args.cover_no_title,
            publish_now=args.publish,
            allow_gzh_warnings=args.allow_gzh_warnings,
            author=args.author,
            digest_override=args.digest,
            preview_only=args.preview,
        )
    except Exception as exc:
        print(f"\n错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
