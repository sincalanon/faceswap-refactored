#!/usr/bin/env python3
""" Launch the simplified Faceswap web UI (简易版图形界面).

Usage::

    pip install -r requirements/_requirements_simple_gui.txt   # once (installs gradio)
    python app.py                     # http://127.0.0.1:7860
    python app.py --port 8000 --host 0.0.0.0 --share

See SIMPLE_GUI_zh-CN.md for a walkthrough.
"""
from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """ Command line options for the launcher """
    parser = argparse.ArgumentParser(description="Faceswap 简易版图形界面 (Gradio)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="监听地址。默认 127.0.0.1（仅本机）；0.0.0.0 允许局域网访问")
    parser.add_argument("--port", type=int, default=7860, help="端口，默认 7860")
    parser.add_argument("--share", action="store_true",
                        help="生成 Gradio 公网分享链接（注意：任何拿到链接的人都能操作本机）")
    parser.add_argument("--inbrowser", action="store_true", help="启动后自动打开浏览器")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """ Entry point """
    args = parse_args(argv)
    try:
        from simple_gui import ui  # pylint:disable=import-outside-toplevel
    except ImportError as err:
        if "gradio" not in str(err):
            raise
        print("未安装 Gradio，无法启动简易版界面。请先执行：\n"
              "    pip install -r requirements/_requirements_simple_gui.txt\n"
              "（或 pip install gradio）", file=sys.stderr)
        return 1
    print(f"Faceswap 简易版界面启动中： http://{args.host}:{args.port}  （按 Ctrl+C 退出）")
    ui.launch(host=args.host, port=args.port, share=args.share, inbrowser=args.inbrowser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
