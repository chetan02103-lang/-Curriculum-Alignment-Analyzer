# 🎓 CurriculumIQ: from syllabus to career readiness

A Streamlit app that connects what students learn in college with what companies expect, in six modules.

**Workflow:** upload a VTU syllabus → extract skills → find industry gaps → choose a target career → get a roadmap → take skill checks and build projects → the career readiness score updates.

## 🌐 Live demo

- 👉 **Clickable preview:** [Open the preview](https://claude.ai/artifact/94W8VrLNaSUQ2G8cRcbidp) (browser version of all six modules; no live news or job data, no PDF reading of reports)
- 👉 **Full Streamlit app:** https://curriculum-alignment-analyzer.streamlit.app

## 🧩 The six modules

| Module | What it does | Code |
|---|---|---|
| 🎓 **Curriculum Analyzer** | Reads a syllabus (PDF/TXT), extracts skills, scores alignment, shows gaps, department and university comparison, college-report analysis, Excel/CSV/PDF export | `modules/curriculum_analyzer.py` |
| 📡 **Industry Skill Tracker** | Live news and dated job-posting skill counts with trends, refreshed daily | `modules/industry_tracker/` |
| 🧭 **AI Career Roadmap** | Ordered learning path to a target role (prerequisites first), journey diagram, phases, finish date, optional Grok explanation | `modules/career_roadmap.py` |
| 📝 **Skill Assessment** | 3-question checks for each of the 30 tracked skills; results set your real skill level | `modules/skill_assessment.py` |
| 🛠️ **Project Recommender** | 12 portfolio projects ranked by the role gaps they close | `modules/project_recommender.py` |
| 🎯 **Job Role Matcher** | Match score for 11 roles from your skill levels, with missing core skills | `modules/job_role_matcher.py` |

`modules/student_profile.py` ties them together: the **career readiness score** and the saveable student profile.

### How the numbers are calculated (all shown in the app)

- **Alignment** = skills matched ÷ 30 tracked skills; a skill matches if its name or an alias (e.g. `k8s`) appears in the curriculum.
- **Skill level** per skill = your quiz score if tested, else 40 if it is in your curriculum, else 0. A skill counts as *known* at 60+.
- **Role match** = weighted average of skill levels over the role's skills (core skills count double).
- **Career readiness** = skill levels 55% + project evidence 30% + internships 15%; the "confidence" label says how many of the role's skills were actually tested.
- **Roadmap**: missing role skills plus missing prerequisites, ordered by prerequisites, then core, then bonus, then demand; weeks assume about 8 study hours a week and scale with your pace.

The demand scores, department baselines and university benchmarks are **illustrative estimates** unless you choose *Job postings* or *College reports* under "Demand scores from". The employability and readiness scores are heuristics, not predictions, and 3 quiz questions per skill is a quick check, not a certification.

## 🚀 Quick start

```bash
cd curriculum-alignment-analyzer
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501 (Python 3.10+, Streamlit 1.50+). The dark theme lives in `.streamlit/config.toml` and `ui/theme.py`.

## 💾 Student profile

Skill-test results, completed projects and readiness history live in your browser session. Use **💾 Student profile → Save profile (JSON)** in the sidebar to keep them and **Load a saved profile** next time. There is no database; the file holds no keys or passwords.

## 🔄 Keeping the data up to date

| What | How often | How |
|---|---|---|
| Job-market skill snapshot (`data/job_market.json`) | daily | `.github/workflows/update-data.yml` runs `update_data.py` and commits the result |
| News headlines | every 15 min while the page is open | Google News RSS, cached 15 min |
| Job-market tab | re-read hourly while open | reads the committed snapshot file |

**One-time setup**
1. Push the project to GitHub. In *Settings → Actions → General → Workflow permissions* choose **Read and write**.
2. Open the *Actions* tab, pick *Update job-market data* and press **Run workflow** once (or run `python update_data.py` locally and commit `data/job_market.json`).
3. Streamlit Community Cloud redeploys on every push, so the app picks up each new snapshot.

Trends need two snapshots. GitHub can pause scheduled workflows in repositories with no activity for 60 days; the app warns when the newest snapshot is more than 3 days old.

**Data policy.** Sources are Remotive and Arbeitnow (free public feeds, no key). Only aggregate skill counts are stored, never the postings. Remotive asks for credit and a link back, at most 4 fetches a day and no republishing of listings; this project makes one request per source per day. Both feeds lean towards remote and European tech jobs: one market signal, not the whole market. Skills seen fewer than 3 times keep the built-in demand score.

## 📰 Live news and Grok setup

The news tab works with no setup. For the optional **Grok briefing** and roadmap explanation you need an xAI API key:

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste the key (git-ignored).
2. On Streamlit Community Cloud paste the same line under *App → Settings → Secrets*.
3. Or type it into the news tab for the current session only (never saved or logged).

Grok is called through the xAI Responses API with its `web_search` tool, and answers are flagged as unverified if no search ran. Set `XAI_MODEL` if the default model name is retired. xAI bills per call. Never put a key in code, the README or a GitHub issue.

## 🏫 College report format

Upload report PDFs under **College reports** in the sidebar (several allowed). The reader expects the table layout of `sample_data/College_Skills_Industry_Report.pdf`: a skills table with columns like *Skill, Dept, Industry Demand (1-10), Student Proficiency (%), Gap Score*, plus optional department, soft-skill and sector tables. Scanned PDFs can't be read. Reports can replace demand scores, provide department baselines and feed the roadmap's salary benchmarks (average CTC by department).

## 🏢 Department data format

One row per department, one column per skill category, values 0-100 (see `sample_data/department_data_example.csv`; a template is downloadable in the sidebar).

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest                         # 51+ unit tests, no network needed
python tests/smoke_app.py      # runs the real app.py through every module with a stand-in Streamlit
```

## ☁️ Deploy (Streamlit Community Cloud)

Push to GitHub, then at share.streamlit.io choose the repo, branch `main`, main file `app.py`, and paste the app URL in "Live demo" above.

## 📁 Structure

```
curriculum-alignment-analyzer/
├── app.py                          # shell: theme, sidebar, profile, module switcher
├── modules/
│   ├── curriculum_analyzer.py      # syllabus extraction, alignment, reports
│   ├── industry_tracker/           # jobs.py (job postings) + news.py (news, Grok)
│   ├── career_roadmap.py           # roadmap planner + journey diagram
│   ├── skill_assessment.py         # 90 quiz questions, grading
│   ├── project_recommender.py      # project catalogue + ranking
│   ├── job_role_matcher.py         # roles, skill levels, matching
│   └── student_profile.py          # readiness score, profile import/export
├── ui/                             # theme.py + pages.py (module pages)
├── update_data.py                  # daily job-market updater
├── data/job_market.json            # snapshots (committed by the Action)
├── .github/workflows/update-data.yml
├── .streamlit/                     # config.toml (theme) + secrets.toml.example
├── sample_data/                    # example CSV, syllabus, college report PDF
├── preview/index.html              # standalone browser preview
└── tests/                          # unit tests + smoke test
```

## 📄 License

MIT License
