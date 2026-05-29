import json
import os
import re
from pathlib import Path

import gradio as gr

from modules import scripts


EXT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = EXT_DIR / "config.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "positive_blacklist": "",
    "negative_blacklist": "",
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(enabled: bool, positive: str, negative: str) -> None:
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "enabled": bool(enabled),
                    "positive_blacklist": positive or "",
                    "negative_blacklist": negative or "",
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except OSError:
        pass


def parse_blacklist(text: str) -> list[str]:
    if not text:
        return []
    words = [w.strip() for w in text.split(",")]
    return [w for w in words if w]


def build_pattern(words: list[str]) -> re.Pattern | None:
    if not words:
        return None
    escaped = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


def cleanup(text: str) -> str:
    # Drop weight tags whose content got emptied: (  :1.2), (), [  ]
    text = re.sub(r"\(\s*(?::\s*-?\d+(?:\.\d+)?)?\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    # Collapse repeated separators (preserve newlines)
    text = re.sub(r"[^\S\n]*,(?:[^\S\n]*,)+", ",", text)
    text = re.sub(r"[^\S\n]*,[^\S\n]*", ", ", text)
    # Trim leading/trailing junk per line and collapse whitespace
    text = re.sub(r"^[^\S\n,]*,?[^\S\n]*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[^\S\n]*,?[^\S\n]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse blank lines but keep intentional newlines
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def filter_text(text: str, pattern: re.Pattern | None) -> str:
    if not text or pattern is None:
        return text or ""
    filtered = pattern.sub("", text)
    if filtered == text:
        return text
    return cleanup(filtered)


def live_filter(prompt_text: str, enabled: bool, blacklist_text: str):
    if not enabled or not blacklist_text or not prompt_text:
        return gr.update()
    pattern = build_pattern(parse_blacklist(blacklist_text))
    if pattern is None:
        return gr.update()
    result = filter_text(prompt_text, pattern)
    if result == prompt_text:
        return gr.update()
    return result


class PromptBlacklist(scripts.Script):
    def __init__(self):
        super().__init__()
        self._prompt_component = None
        self._neg_prompt_component = None

    def title(self):
        return "Prompt Blacklist"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def after_component(self, component, **kwargs):
        elem_id = kwargs.get("elem_id")
        if elem_id in ("txt2img_prompt", "img2img_prompt"):
            self._prompt_component = component
        elif elem_id in ("txt2img_neg_prompt", "img2img_neg_prompt"):
            self._neg_prompt_component = component

    def ui(self, is_img2img):
        with gr.Accordion("Prompt Blacklist", open=False):
            enabled = gr.Checkbox(
                label="Enable filtering",
                value=lambda: load_config()["enabled"],
            )
            positive = gr.Textbox(
                label="Positive prompt blacklist (comma-separated)",
                value=lambda: load_config()["positive_blacklist"],
                placeholder="e.g. blurry, lowres, watermark",
                lines=2,
            )
            negative = gr.Textbox(
                label="Negative prompt blacklist (comma-separated)",
                value=lambda: load_config()["negative_blacklist"],
                placeholder="e.g. masterpiece, best quality",
                lines=2,
            )
            with gr.Row():
                clean_now = gr.Button("Clean current prompts now", variant="secondary")
                reload_btn = gr.Button("Reload from disk", variant="secondary")
            gr.Markdown(
                "Whole-word match, case-insensitive. Settings auto-save on every keystroke and persist between sessions. "
                "Prompts are also filtered live when edited (e.g. when Tagger sends tags to txt2img)."
            )

            for component in (enabled, positive, negative):
                component.change(
                    fn=save_config,
                    inputs=[enabled, positive, negative],
                    outputs=None,
                    show_progress=False,
                )

            for component in (positive, negative):
                component.input(
                    fn=save_config,
                    inputs=[enabled, positive, negative],
                    outputs=None,
                    show_progress=False,
                )

            def _reload_from_disk():
                cfg = load_config()
                return cfg["enabled"], cfg["positive_blacklist"], cfg["negative_blacklist"]

            reload_btn.click(
                fn=_reload_from_disk,
                inputs=None,
                outputs=[enabled, positive, negative],
                show_progress=False,
            )

        if self._prompt_component is not None:
            self._prompt_component.change(
                fn=live_filter,
                inputs=[self._prompt_component, enabled, positive],
                outputs=[self._prompt_component],
                show_progress=False,
            )
            clean_now.click(
                fn=live_filter,
                inputs=[self._prompt_component, enabled, positive],
                outputs=[self._prompt_component],
                show_progress=False,
            )

        if self._neg_prompt_component is not None:
            self._neg_prompt_component.change(
                fn=live_filter,
                inputs=[self._neg_prompt_component, enabled, negative],
                outputs=[self._neg_prompt_component],
                show_progress=False,
            )
            clean_now.click(
                fn=live_filter,
                inputs=[self._neg_prompt_component, enabled, negative],
                outputs=[self._neg_prompt_component],
                show_progress=False,
            )

        return [enabled, positive, negative]

    def process(self, p, enabled, positive_blacklist, negative_blacklist):
        if not enabled:
            return

        pos_pattern = build_pattern(parse_blacklist(positive_blacklist))
        neg_pattern = build_pattern(parse_blacklist(negative_blacklist))

        if pos_pattern is None and neg_pattern is None:
            return

        if pos_pattern is not None:
            p.prompt = filter_text(p.prompt, pos_pattern)
            if getattr(p, "all_prompts", None):
                p.all_prompts = [filter_text(t, pos_pattern) for t in p.all_prompts]
            if getattr(p, "main_prompt", None):
                p.main_prompt = filter_text(p.main_prompt, pos_pattern)
            if getattr(p, "hr_prompt", None):
                p.hr_prompt = filter_text(p.hr_prompt, pos_pattern)
            if getattr(p, "all_hr_prompts", None):
                p.all_hr_prompts = [filter_text(t, pos_pattern) for t in p.all_hr_prompts]

        if neg_pattern is not None:
            p.negative_prompt = filter_text(p.negative_prompt, neg_pattern)
            if getattr(p, "all_negative_prompts", None):
                p.all_negative_prompts = [filter_text(t, neg_pattern) for t in p.all_negative_prompts]
            if getattr(p, "hr_negative_prompt", None):
                p.hr_negative_prompt = filter_text(p.hr_negative_prompt, neg_pattern)
            if getattr(p, "all_hr_negative_prompts", None):
                p.all_hr_negative_prompts = [filter_text(t, neg_pattern) for t in p.all_hr_negative_prompts]

    def process_batch(self, p, enabled, positive_blacklist, negative_blacklist, **kwargs):
        if not enabled:
            return

        pos_pattern = build_pattern(parse_blacklist(positive_blacklist))
        neg_pattern = build_pattern(parse_blacklist(negative_blacklist))

        prompts = kwargs.get("prompts")
        if pos_pattern is not None and prompts is not None:
            for i, t in enumerate(prompts):
                prompts[i] = filter_text(t, pos_pattern)

        if neg_pattern is not None and getattr(p, "negative_prompts", None) is not None:
            for i, t in enumerate(p.negative_prompts):
                p.negative_prompts[i] = filter_text(t, neg_pattern)
