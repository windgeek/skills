#!/usr/bin/env python3
"""把本地电子书发到 Kindle。

用法: python3 -I send_kindle.py <文件路径> [--name 附件文件名]

读取 ~/.config/zlib/kindle.json（收件、发件、SMTP 主机端口）和
~/.config/zlib/.env 里的 ZLIB_SMTP_PWD（也可用同名环境变量覆盖）。
密码不会被打印。附件名默认取 ASCII 安全名，中文名可能被亚马逊拒收。
"""
import argparse
import json
import mimetypes
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage

CONF = os.path.expanduser("~/.config/zlib")
KINDLE_TYPES = {".epub", ".pdf", ".txt", ".doc", ".docx", ".rtf", ".html", ".htm"}


def read_password():
    if os.environ.get("ZLIB_SMTP_PWD"):
        return os.environ["ZLIB_SMTP_PWD"]
    try:
        for line in open(os.path.join(CONF, ".env"), encoding="utf-8"):
            if line.startswith("ZLIB_SMTP_PWD="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    sys.exit("未找到 ZLIB_SMTP_PWD：请让用户在终端把 SMTP 授权码写入 ~/.config/zlib/.env")


def safe_name(path):
    stem, ext = os.path.splitext(os.path.basename(path))
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")
    return (ascii_stem or "book") + ext.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--name", help="附件文件名（含扩展名）")
    a = ap.parse_args()

    path = os.path.expanduser(a.file)
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path):
        sys.exit(f"文件不存在: {path}")
    if ext not in KINDLE_TYPES:
        sys.exit(f"Kindle 不支持 {ext}，可用格式: {', '.join(sorted(KINDLE_TYPES))}")

    try:
        cfg = json.load(open(os.path.join(CONF, "kindle.json"), encoding="utf-8"))
    except (OSError, ValueError):
        sys.exit("读不到 ~/.config/zlib/kindle.json：请让用户先运行 zlib kindle config")

    filename = a.name or safe_name(path)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if ext == ".epub":
        ctype = "application/epub+zip"
    maintype, subtype = ctype.split("/", 1)

    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg["Subject"] = os.path.splitext(filename)[0]
    msg.set_content("Sent to Kindle")
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=filename)

    port = int(cfg["smtp_port"])
    ctx = ssl.create_default_context()
    try:
        if port == 465 or port == 994:
            s = smtplib.SMTP_SSL(cfg["smtp_host"], port, timeout=60, context=ctx)
        else:
            s = smtplib.SMTP(cfg["smtp_host"], port, timeout=60)
            s.starttls(context=ctx)
        s.login(cfg["from"], read_password())
        refused = s.send_message(msg)
        s.quit()
    except smtplib.SMTPAuthenticationError:
        sys.exit("SMTP 认证失败：授权码不对或已失效，让用户在邮箱网页重新生成并写入 .env")
    except (smtplib.SMTPException, OSError) as e:
        sys.exit(f"发送失败: {type(e).__name__}: {str(e)[:200]}")
    if refused:
        sys.exit(f"部分收件人被拒: {refused}")
    print(f"已发送 {filename} -> {cfg['to']}（Kindle 同步通常要几分钟）")


if __name__ == "__main__":
    main()
