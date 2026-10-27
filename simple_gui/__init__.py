#!/usr/bin/env python3
""" Simplified, beginner friendly web UI for Faceswap (简易版图形界面).

The package is deliberately thin. It never touches the deep learning core: every job is run by
launching ``faceswap.py extract|train|convert`` (or ``tools.py effmpeg``) as a subprocess with
a small, curated set of arguments. Only :mod:`simple_gui.ui` depends on Gradio, so the rest of
the package can be imported and tested without it.
"""
