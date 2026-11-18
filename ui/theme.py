"""Visual theme (dark navy, purple and orange) and small HTML helpers for the module pages."""
from __future__ import annotations

import html

PIPELINE_STEPS = ["Upload syllabus", "Extract skills", "Gap analysis", "Choose career", "Career roadmap",
                  "Assess & build", "Readiness update"]

CSS = """
<style>
  .stApp { background: radial-gradient(1100px 500px at 85% -5%, rgba(139,108,255,.16), transparent 60%), #0a0a18; }
  .main-header { background: linear-gradient(135deg, #1b1245 0%, #3a1f7a 55%, #b5560f 140%) !important; border: 1px solid #3b2d78; }
  .section-title { color: #e9e9f5; }
  .cq-head h2 { margin: 0 0 .15rem; font-size: 1.7rem; background: linear-gradient(90deg,#fff,#c9bcff 60%,#ffb347);
                -webkit-background-clip: text; background-clip: text; color: transparent; }
  .cq-head p { margin: 0 0 1rem; color: #9b97c4; }
  .cq-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: .4rem 0 1rem; }
  .cq-card { background: #12122b; border: 1px solid #2d2560; border-radius: 18px; padding: 1rem 1.1rem; position: relative; overflow: hidden; }
  .cq-card::before { content: ""; position: absolute; inset: 0 0 auto; height: 3px; background: linear-gradient(90deg,#8b6cff,#ff9f43); }
  .cq-card.o::before { background: linear-gradient(90deg,#ff9f43,#ff6a3d); }
  .cq-card span { display: block; font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: #8d88bb; }
  .cq-card b { display: block; font-size: 2rem; line-height: 1.25; color: #b9a6ff; }
  .cq-card.o b { color: #ffb347; }
  .cq-card small { color: #8d88bb; }
  .cq-pipe { display: flex; flex-wrap: wrap; gap: 8px; margin: .2rem 0 1rem; }
  .cq-step { border: 1px solid #2d2560; background: #11112a; color: #9b97c4; border-radius: 999px; padding: .35rem .85rem; font-size: .8rem; }
  .cq-step.done { border-color: #5b3df5; color: #d9d0ff; background: #1a1448; }
  .cq-step.now { border-color: #ff9f43; color: #ffd9a3; background: #2a1a08; }
  .cq-skill { margin: .35rem 0; }
  .cq-skill .row { display: flex; justify-content: space-between; font-size: .85rem; color: #cfc9f5; }
  .cq-skill .bar { height: 8px; border-radius: 6px; background: #1c1940; overflow: hidden; margin-top: 3px; }
  .cq-skill .bar i { display: block; height: 100%; background: linear-gradient(90deg,#8b6cff,#ff9f43); }
  .stTabs [data-baseweb="tab"] { border-radius: 999px; }
</style>
"""


def inject_theme(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(st, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="cq-head"><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>', unsafe_allow_html=True)


def cards_html(cards: list[tuple]) -> str:
    """cards: (label, value, sub, tone) with tone 'p' (purple) or 'o' (orange)."""
    body = "".join(
        f'<div class="cq-card {"o" if tone == "o" else ""}"><span>{html.escape(str(label))}</span>'
        f'<b>{html.escape(str(value))}</b><small>{html.escape(str(sub))}</small></div>'
        for label, value, sub, tone in cards)
    return f'<div class="cq-cards">{body}</div>'


def pipeline_html(flags: list[bool]) -> str:
    """Seven workflow steps; finished steps are filled, the first unfinished one is highlighted."""
    now = next((i for i, f in enumerate(flags) if not f), -1)
    steps = []
    for i, (name, done) in enumerate(zip(PIPELINE_STEPS, flags)):
        cls = "done" if done else "now" if i == now else ""
        steps.append(f'<span class="cq-step {cls}">{"✓ " if done else ""}{i + 1}. {html.escape(name)}</span>')
    return f'<div class="cq-pipe">{"".join(steps)}</div>'


def skill_bar_html(label: str, pct: float) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    return (f'<div class="cq-skill"><div class="row"><span>{html.escape(label)}</span><span>{pct:.0f}%</span></div>'
            f'<div class="bar"><i style="width:{pct:.0f}%"></i></div></div>')
