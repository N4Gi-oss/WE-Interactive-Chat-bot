"""
Standalone Gradio app. Run with: python app.py
No Colab dependency — works locally, on a VM, or in a Docker container.

Layout (per hand-drawn spec): small "WE" badge top-left, big centered
avatar as the focal point, minimal reply text under it, full-width
textbox pinned at the bottom. Purple brand background.

Avatar states — put PNGs in ./avatar_frames/ next to this file:
    base.png     - idle: shown before any message, and after a reply
                   finishes typing out (if it was a normal answer)
    thinking.png - shown while waiting for Gemini's response
    talking.png  - shown while the reply is being "typed" onto the screen
    confused.png - shown once a "don't have this info" fallback reply
                   finishes typing out
If any are missing, the app still runs fine — it falls back to base.png
for whichever state is missing (never crashes).
"""

import threading
import time
from pathlib import Path

import gradio as gr

from rag import generate_answer

# ============================================================
# CONFIG
# ============================================================
WE_PURPLE = "#5C2D91"
WE_PURPLE_DARK = "#3E1F63"
WE_PURPLE_LIGHT = "#7B4FA8"

TYPE_CHUNK_SIZE = 2      # characters revealed per animation tick
TYPE_TICK_SECONDS = 0.02  # delay between ticks

# Phrases that mean "the bot didn't find the info" -> show confused
NO_INFO_MARKERS = [
    "مش لاقي معلومات",
    "لا أملك هذه المعلومة",
    "don't have this information",
    "I don't have that information",
]

EXAMPLE_QUESTIONS = [
    "عايز اشترك في واتش إت، التكلفة كام؟",
    "عايز اعرف سعر الكول تون",
    "فيه خدمة لمتابعة أخبار الكورة؟",
]

# ============================================================
# AVATAR — resolve the 4 frame images once at startup
# ============================================================
AVATAR_DIR = Path(__file__).parent / "avatar_frames"


def _frame(name: str):
    p = AVATAR_DIR / f"{name}.png"
    return str(p) if p.exists() else None


AVATAR = {
    "base": _frame("base"),
    "thinking": _frame("thinking"),
    "talking": _frame("talking"),
    "confused": _frame("confused"),
}

missing = [k for k, v in AVATAR.items() if v is None]
if missing:
    print(
        f"[avatar] Missing frames in {AVATAR_DIR}: {missing} "
        "-> will fall back to base.png for those states."
    )

WAITING_FRAME = AVATAR["thinking"] or AVATAR["base"]
TALKING_FRAME = AVATAR["talking"] or AVATAR["base"]
CONFUSED_FRAME = AVATAR["confused"] or AVATAR["base"]
BASE_FRAME = AVATAR["base"]


# ============================================================
# STYLES
# ============================================================
custom_css = f"""
.gradio-container {{
    font-family: 'Segoe UI', Tahoma, sans-serif !important;
    direction: rtl;
    background: linear-gradient(160deg, {WE_PURPLE} 0%, {WE_PURPLE_DARK} 100%) !important;
}}

#we-badge {{
    position: fixed;
    top: 18px;
    left: 18px;
    background: white;
    border: 2px solid {WE_PURPLE};
    color: {WE_PURPLE};
    font-weight: 700;
    padding: 6px 18px;
    border-radius: 999px;
    z-index: 20;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}}

#hero-col {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding-top: 40px;
    min-height: 55vh;
}}

#avatar-box img {{
    border-radius: 50%;
    border: 5px solid white;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.35);
    width: 260px;
    height: 260px;
    object-fit: cover;
    background: white;
}}

#reply-text {{
    max-width: 680px;
    margin: 24px auto 0 auto;
    text-align: center;
    font-size: 1.05rem;
    min-height: 1.4em;
    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.35);
    border-radius: 18px;
    padding: 22px 28px;
}}

#reply-text * {{
    color: white !important;
}}

#input-bar {{
    max-width: 620px;
    margin: 40px auto 0 auto !important;
}}

#input-bar textarea {{
    background: white !important;
    color: {WE_PURPLE_DARK} !important;
    border: none !important;
    border-radius: 14px !important;
    font-size: 1rem !important;
    padding: 12px 16px !important;
}}

#input-bar label, #input-bar span {{
    color: white !important;
}}

#examples-row {{
    max-width: 620px;
    margin: 18px auto 0 auto !important;
}}

#examples-row * {{
    color: white !important;
}}
"""


# ============================================================
# LOGIC — one function drives the avatar + reply text
# ============================================================
def respond(message, history):
    """
    Generator: yields (textbox, hidden_log, reply_text, avatar_image).

    Flow: base -> (waiting on Gemini) thinking -> (typing out the reply,
    character by character) talking -> (done) base, or confused if the
    reply was a "don't have this info" fallback.

    hidden_log keeps the full conversation in Gradio's "messages" format
    purely as state; only the latest reply is shown under the avatar.
    """
    result = {}

    def worker():
        try:
            result["answer"] = generate_answer(message)
        except Exception as exc:
            result["error"] = str(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    # 1) thinking, while Gemini is still working
    yield "", history, "...", WAITING_FRAME
    thread.join()

    if "error" in result:
        answer = (
            "معلش، حصل خطأ أثناء توليد الرد. "
            "برجاء المحاولة تاني أو التواصل مع خدمة عملاء WE على 155."
        )
        is_no_info = True
    else:
        answer = result.get("answer", "")
        is_no_info = any(marker in answer for marker in NO_INFO_MARKERS)

    # 2) talking, typed out progressively
    for i in range(TYPE_CHUNK_SIZE, len(answer) + TYPE_CHUNK_SIZE, TYPE_CHUNK_SIZE):
        yield "", history, answer[:i], TALKING_FRAME
        time.sleep(TYPE_TICK_SECONDS)

    # 3) done: back to base, or confused if it was a fallback answer
    final_frame = CONFUSED_FRAME if is_no_info else BASE_FRAME
    final_log = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": answer},
    ]
    yield "", final_log, answer, final_frame


# ============================================================
# UI
# ============================================================
with gr.Blocks() as demo:
    gr.Markdown("<div id='we-badge'>WE</div>")

    with gr.Column(elem_id="hero-col"):
        avatar_img = gr.Image(
            value=BASE_FRAME,
            elem_id="avatar-box",
            show_label=False,
            interactive=False,
            container=False,
        )
        reply_text = gr.Markdown("", elem_id="reply-text")

    # keeps full conversation history for context; not rendered
    chat_log = gr.State([])

    with gr.Column(elem_id="input-bar"):
        msg = gr.Textbox(
            placeholder="اكتب سؤالك هنا...",
            show_label=False,
        )

    with gr.Column(elem_id="examples-row"):
        gr.Examples(examples=EXAMPLE_QUESTIONS, inputs=msg)

    msg.submit(respond, [msg, chat_log], [msg, chat_log, reply_text, avatar_img])


# ============================================================
# LAUNCH
# ============================================================
if __name__ == "__main__":
    # share=False for on-prem deployment; set server_name="0.0.0.0" to expose on the network
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        css=custom_css,
        theme=gr.themes.Soft(primary_hue="purple"),
    )