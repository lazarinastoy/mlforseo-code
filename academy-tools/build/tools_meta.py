"""Per-tool copy for the academy tool pages, read from ../meta/<slug>.json (one file per tool).

Each file: slug, title, short, course (www course slug), lesson, needs, cost, inputs, outputs, how[], note.
The tool's source is ../tools/<slug>.html.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
META = HERE.parent / "meta"

# www course slug -> official name (never shorten course names)
COURSES = {
    "introduction-to-machine-learning-for-seo": "Introduction to Machine Learning for SEO",
    "semantic-ml-enabled-keyword-research": "Semantic AI-powered SEO Keyword Research",
    "ai-search-optimisation-agentic-seo": "AI Search Optimization & Agentic SEO",
    "ai-search-llms-entity-seo-and-knowledge-graph-strategies-for-brands": "AI Search & LLMs: Entity SEO and Knowledge Graph Strategies for Brands",
    "the-ai-powered-entity-audit": "The AI-powered Entity Audit",
}


def load_tools():
    tools = []
    for f in sorted(META.glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        t["file"] = t["slug"] + ".html"
        t["course_name"] = COURSES.get(t["course"], t["course"])
        tools.append(t)
    return tools


TOOLS = load_tools()
