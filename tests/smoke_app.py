"""Smoke test: runs the real app.py for every module against a stand-in Streamlit (no browser, no network).

Run from the project root:  python tests/smoke_app.py
It exercises uploads, the quiz, projects, profile import and every module page.
"""
import json, os, shutil, sys, tempfile
import runpy, types
from unittest.mock import MagicMock

RSS = b'<rss><channel><item><title>Google lays off 52 in US - X</title><link>https://e.com/a</link><pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate><source url="u">X</source></item></channel></rss>'
class Rerun(Exception): pass
class Stub:
    def __call__(self, *a, **k): return Stub()
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, n): return Stub()
class SS(dict):
    pass
class FakeFile:
    def __init__(self, name, data): self.name, self.data, self.size = name, data, len(data)
    def getvalue(self): return self.data

class Col(Stub):
    """A column/tab/container: widget calls on it behave like the same call on st."""
    def __init__(self, st): object.__setattr__(self, "_st", st)
    def __getattr__(self, n): return getattr(self._st, n, None) or Stub()

def make_st(force=None, uploads=None, clicks=(), session=None):
    force, uploads = force or {}, uploads or {}
    st = types.ModuleType("streamlit"); st.log = []
    st.session_state = SS(session or {})
    for n in "markdown caption write info success warning dataframe plotly_chart bar_chart line_chart progress title header subheader code json divider table image set_page_config toast metric".split():
        setattr(st, n, lambda *a, **k: Stub())
    st.error = lambda *a, **k: st.log.append(str(a[0]) if a else "error") or Stub()
    st.exception = lambda *a, **k: st.log.append("exception") or Stub()
    def selectbox(label, options, index=0, **k):
        o = list(options); return force.get(label, o[index] if o and index is not None else None)
    st.selectbox = selectbox
    st.multiselect = lambda label, options, default=None, **k: force.get(label, list(default or []))
    def slider(label, *a, **k):
        v = a[2] if len(a) > 2 else k.get("value", a[0] if a else 0); return force.get(label, v)
    st.slider = slider
    st.text_input = lambda label, value="", **k: force.get(label, value)
    st.text_area = lambda label, value="", **k: force.get(label, value)
    st.checkbox = lambda label, value=False, **k: force.get(label, value)
    st.radio = lambda label, options, index=0, **k: force.get(label, list(options)[index] if index is not None else None)
    st.button = lambda label, **k: label in clicks
    st.download_button = lambda *a, **k: False
    st.form_submit_button = lambda label="Submit", **k: label in clicks
    def file_uploader(label, type=None, accept_multiple_files=False, **k):
        hit = next((v for key, v in uploads.items() if key in label), None)
        return ([hit] if hit else []) if accept_multiple_files else hit
    st.file_uploader = file_uploader
    st.columns = lambda spec, **k: [Col(st) for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.tabs = lambda names, **k: [Col(st) for _ in names]
    st.sidebar = Col(st)
    for n in "expander container spinner form empty".split(): setattr(st, n, lambda *a, **k: Col(st))
    def rerun(): raise Rerun()
    st.rerun = rerun
    st.cache_data = lambda *a, **k: a[0] if a and callable(a[0]) else (lambda f: f)
    st.fragment = lambda *a, **k: a[0] if a and callable(a[0]) else (lambda f: f)
    st.secrets = types.SimpleNamespace(get=lambda k, d=None: None)
    st.column_config = Stub()
    return st

def run_app(root, **kw):
    st = make_st(**kw)
    sys.modules["streamlit"] = st
    for n in ("plotly", "plotly.express", "plotly.graph_objects"): sys.modules[n] = MagicMock()
    for m in [m for m in sys.modules if m.startswith(("modules", "ui"))]: del sys.modules[m]
    sys.path.insert(0, root); cwd = os.getcwd(); os.chdir(root)
    rerun = False
    import modules.industry_tracker.news as _news            # fresh import; give the news tab canned headlines
    _news.fetch_google_news = lambda *a, **k: _news.parse_google_news(RSS)
    try:
        runpy.run_path(os.path.join(root, "app.py"), run_name="__main__")
    except Rerun:
        rerun = True
    finally:
        os.chdir(cwd); sys.path.remove(root)
    return st, rerun

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root = tempfile.mkdtemp(); shutil.copytree(SRC, root + "/p", ignore=shutil.ignore_patterns("__pycache__", ".git")); root += "/p"
sys.path.insert(0, root)
from modules.industry_tracker.jobs import append_snapshot, make_snapshot
from modules.industry_tracker import news as newsmod
from modules.skill_assessment import QUESTIONS
RSS = b'<rss><channel><item><title>Google lays off 52 in US - X</title><link>https://e.com/a</link><pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate><source url="u">X</source></item></channel></rss>'
# a populated job snapshot (two days) so the job-postings demand source and trends are exercised
posts = [{"source": "remotive", "title": "t", "company": str(i), "date": "2026-10-28", "text": "Python SQL Docker AWS React" if i % 2 else "Python Kubernetes"} for i in range(30)]
from datetime import date
append_snapshot("data/job_market.json" if False else root + "/data/job_market.json", make_snapshot(posts, date(2026, 10, 1)))
append_snapshot(root + "/data/job_market.json", make_snapshot(posts[:20], date(2026, 10, 30)))
MODS = ["🎓 Curriculum Analyzer", "📡 Industry Skill Tracker", "🧭 AI Career Roadmap", "📝 Skill Assessment", "🛠️ Project Recommender", "🎯 Job Role Matcher"]
pdf = open(root + "/sample_data/College_Skills_Industry_Report.pdf", "rb").read()
fails = []
def check(name, st, rerun=None, expect_rerun=False, extra=None):
    bad = list(st.log)
    if expect_rerun and not rerun: bad.append("expected a rerun")
    if not expect_rerun and rerun: bad.append("unexpected rerun")
    if extra: bad += [extra] if isinstance(extra, str) else extra
    print(("FAIL " if bad else "ok   ") + name, *bad[:3]); fails.extend(bad)
for m in MODS:                                   # every module, default state
    st, rr = run_app(root, force={"Module": m}); check("module: " + m, st, rr)
# rich state: college report + uploaded syllabus + job-posting demand + a different role
for m in MODS:
    st, rr = run_app(root, force={"Module": m, "Curriculum Input": "📄 Upload PDF/TXT", "Target role": "Senior Data Scientist"},
                     uploads={"College reports": FakeFile("r.pdf", pdf), "Upload Syllabus": FakeFile("s.txt", b"BCS501 Cloud\nPython, SQL, Docker, Kubernetes, CI/CD\nNeural networks and Machine Learning\n")})
    check("rich state: " + m, st, rr)
st, rr = run_app(root, force={"Module": MODS[0], "Demand scores from": "College reports"}, uploads={"College reports": FakeFile("r.pdf", pdf)}); check("demand source = college reports", st, rr)
st, rr = run_app(root, force={"Module": MODS[0], "Demand scores from": "Built-in estimates"}); check("demand source = built-in", st, rr)
# quiz submission: answer everything correctly
answers = {f"ans_{s}:{i}": q[1] for s, qs in QUESTIONS.items() for i, q in enumerate(qs)}
st, rr = run_app(root, force={"Module": MODS[3]}, clicks={"Submit answers"}, session=dict(answers))
prof = st.session_state["profile"]
check("quiz submit saves results and reruns", st, rr, True, None if prof["assessments"] and all(a["correct"] == a["total"] for a in prof["assessments"].values()) else "assessments not saved")
# project completion
st, rr = run_app(root, force={"Module": MODS[4]}, clicks={"Mark as completed"})
check("project completion", st, rr, True, None if len(st.session_state["profile"]["projects_done"]) == 1 else "project not recorded")
# profile load from JSON
from modules.student_profile import export_profile, new_profile
p = new_profile(); p["assessments"] = {"Python": {"correct": 3, "total": 3, "date": "2026-11-01"}}
st, rr = run_app(root, force={"Module": MODS[5]}, uploads={"Load a saved profile": FakeFile("p.json", export_profile(p).encode())})
check("profile import", st, rr, False, None if "Python" in st.session_state["profile"]["assessments"] else "profile not loaded")
st, rr = run_app(root, force={"Module": MODS[5]}, uploads={"Load a saved profile": FakeFile("p.json", b"[1,2]")})
shown = any("Couldn't read the profile" in x for x in st.log); st.log.clear()
check("bad profile file is reported, not crashed", st, rr, False, None if shown else "no error shown")
print("\nSMOKE FAILURES:" if any(f for f in fails if "Couldn't read the profile" not in str(f)) else "\nALL SMOKE SCENARIOS PASSED")
