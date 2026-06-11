import os
import re
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Surrogacy Case Audit",
    layout="wide",
)

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_DIR = r"C:\Users\zhous\OneDrive - Tsong Law Group\Ralph Tsong's files - Active Cases\Surrogacy Cases"
_COLORS = {"drafting": "#2c7bb6", "review": "#d7191c"}

AGENCY_CANONICAL = {
    "gts":                                         "Giving Tree Surrogacy",
    "giving tree":                                 "Giving Tree Surrogacy",
    "giving tree surrogacy (review)":              "Giving Tree Surrogacy",
    "royal surrogacy":                             "Royal Surrogacy & Egg Donation",
    "royal":                                       "Royal Surrogacy & Egg Donation",
    "coast to coast":                              "Coast to Coast Surrogacy",
    "patriot conceptions (do not mention agency)": "Patriot Conceptions",
    "patriot":                                     "Patriot Conceptions",
    "los angeles surrogacy":                       "LAS",
    "la surrogacy":                                "LAS",
    "all families":                                "All Families Surrogacy",
    "all family surrogacy":                        "All Families Surrogacy",
    "afs":                                         "All Families Surrogacy",
    "blossom california":                          "Blossom California Fertility",
    "blossom":                                     "Blossom California Fertility",
    "csp":                                         "California Surrogacy Partners",
    "simple":                                      "Simple Surrogacy",
    "oneworld generations surrogacy":              "Oneworld Generations",
    "oneworld":                                    "Oneworld Generations",
    "modern baby family corp":                     "Modern Baby Family",
    "modern baby family":                          "Modern Baby Family",
    "lily baby surrogacy":                         "Lily Baby",
    "surrogatefirst":                              "SurrogateFirst",
    "surrogacy4all":                               "Surrogacy4All",
    "global fertility":                            "Global Fertility",
    "dream surrogacy":                             "Dream Surrogacy",
    "blissful bloom":                              "Blissful Bloom",
    "acrc":                                        "ACRC",
    "edsi":                                        "EDSI",
    "indy":                                        "Indy",
    "newgen families":                             "Newgen Families",
    "new gen families":                            "Newgen Families",
    "new gen":                                     "Newgen Families",
    "newgen":                                      "Newgen Families",
    "new generation families":                     "Newgen Families",
    "new generation":                              "Newgen Families",
}


# ── Core functions ─────────────────────────────────────────────────────────────
def canonicalize_agency(name):
    if not name:
        return name
    key = name.strip().lower()
    if key in AGENCY_CANONICAL:
        return AGENCY_CANONICAL[key]
    for variant, canonical in AGENCY_CANONICAL.items():
        if key == variant or key.startswith(variant + " ") or variant.startswith(key + " "):
            return canonical
    return name


def normalize_agency_name(agency_name):
    if "(do not use)" in agency_name.lower():
        return None
    normalized = re.sub(r"^review\s+", "", agency_name, flags=re.IGNORECASE)
    normalized = re.sub(r"^\s*\([A-Z]{2}\)\s*", "", normalized)
    normalized = re.sub(r"^-\s*", "", normalized)
    normalized = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", normalized)
    normalized = re.sub(r",?\s*(Inc\.?|LLC|PLLC|Corp\.?|Ltd\.?)\s*$", "", normalized, flags=re.IGNORECASE)
    words = normalized.split()
    if len(words) >= 3 and words[-1].lower() in ["surrogacy", "donation"]:
        normalized = " ".join(words[:-1])
    elif len(words) >= 2 and words[-1].lower() in ["nmc", "break", "review"]:
        normalized = " ".join(words[:-1])
    normalized = re.sub(r"\s+(Consulting|will change|for|do not)\s+.*$", "", normalized, flags=re.IGNORECASE)
    normalized = " ".join(normalized.split()).strip()
    if not normalized:
        return None
    if re.match(r"^[A-Z]{2}$", normalized):
        return None
    return canonicalize_agency(normalized)


def parse_folder_name(folder_name):
    if not (folder_name.startswith("24-") or folder_name.startswith("25-") or folder_name.startswith("26-")):
        return None
    is_review = "review" in folder_name.lower()
    clean_name = re.sub(r"\s*-\s*(TERMINATE4D|TERMINATED)\s*$", "", folder_name, flags=re.IGNORECASE).strip()
    name_part = re.sub(r"^2[456]-\S+\s+", "", clean_name, flags=re.IGNORECASE).strip()
    agency = None
    parts = [p.strip() for p in clean_name.split(" - ")]
    if len(parts) >= 2:
        agency = parts[-1]
    if not agency:
        norm = re.sub(r"\s*[–—]\s*", " - ", name_part)
        norm = re.sub(r"(?<!\s)-\s+", " - ", norm)
        norm = re.sub(r"\s+-([^\s-])", r" - \1", norm)
        parts = [p.strip() for p in norm.split(" - ")]
        if len(parts) >= 2:
            agency = parts[-1]
    if not agency and is_review:
        m = re.search(r"\breview\s+([^\s].+?)\s*$", name_part, re.IGNORECASE)
        if m:
            agency = m.group(1).strip()
    if not agency and "&" in name_part:
        after_amp = name_part.split("&")[-1].strip()
        after_amp = re.sub(r"\s*\([A-Z]{2,3}(?:-[A-Z]{2,3})?\)\s*", " ", after_amp).strip()
        after_amp = re.sub(r"\s*\b(PBO|nmc|review|clean\s+up)\s*$", "", after_amp, flags=re.IGNORECASE).strip()
        after_amp = re.sub(r"^(\w[\w\-]+(?:\s+and\s+\w[\w\-]+)?)\s+", "", after_amp).strip()
        after_amp = re.sub(r"\s*\b(PBO|nmc|review)\s*$", "", after_amp, flags=re.IGNORECASE).strip()
        if after_amp:
            agency = after_amp
    if agency:
        agency = agency.strip()
        if agency.upper() not in ["XX", "XXX", "XXXX"]:
            return (agency, is_review)
    return None


def find_agreement_file(folder_path):
    try:
        for entry in os.scandir(folder_path):
            if not entry.is_file():
                continue
            n = entry.name.lower()
            if any(n.endswith(ext) for ext in [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp"]):
                if "agreement" in n and "legal" in n and "representation" in n and "signed" in n:
                    return entry
    except Exception:
        pass
    return None


def find_clearance_letter(folder_path):
    try:
        for entry in os.scandir(folder_path):
            if not entry.is_file():
                continue
            n = entry.name.lower()
            if "clearance" in n and any(n.endswith(e) for e in [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp"]):
                return entry
    except Exception:
        pass
    return None


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    _SKIP = re.compile(
        r"\b(TERMINATE4D|TERMINATED|NOT\s+DRAFTED\s+YET|DECIDE\s+NOT\s+TO\s+REPRESENT|DECLINED)\b",
        re.IGNORECASE,
    )
    records = []
    for folder_name in sorted(os.listdir(BASE_DIR)):
        if folder_name.startswith(".") or folder_name.startswith("~"):
            continue
        folder_path = os.path.join(BASE_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
        if _SKIP.search(folder_name):
            continue
        parsed = parse_folder_name(folder_name)
        if not parsed:
            continue
        raw_agency, is_review = parsed
        agency = normalize_agency_name(raw_agency)
        if not agency:
            continue
        entry = find_agreement_file(folder_path)
        source = "signed agreement"
        if not entry:
            entry = find_clearance_letter(folder_path)
            source = "legal clearance letter"
        if not entry:
            continue
        try:
            mtime = entry.stat().st_mtime
            agreement_date = datetime.fromtimestamp(mtime)
        except Exception:
            continue
        records.append({
            "month":          agreement_date.strftime("%Y-%m"),
            "date":           agreement_date.strftime("%Y-%m-%d"),
            "agency":         agency,
            "status":         "review" if is_review else "drafting",
            "case_folder":    folder_name,
            "agreement_file": entry.name,
            "source":         source,
        })
    return pd.DataFrame(records).sort_values(["month", "agency", "date"]).reset_index(drop=True)


df = load_data()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Surrogacy Case Audit")
    st.metric("Total Cases", len(df))
    col1, col2 = st.columns(2)
    col1.metric("Drafting", (df["status"] == "drafting").sum())
    col2.metric("Review", (df["status"] == "review").sum())
    st.metric("Unique Agencies", df["agency"].nunique())
    st.metric("Months Covered", df["month"].nunique())
    st.caption(f"{df['month'].min()} → {df['month'].max()}")

# ── Precompute shared data ─────────────────────────────────────────────────────
_m = (
    df.groupby(["month", "status"])
    .size()
    .unstack(fill_value=0)
    .reindex(columns=["drafting", "review"], fill_value=0)
)
_m["total"] = _m.sum(axis=1)

# ── Chart 1: Monthly case volume ───────────────────────────────────────────────
st.header("1. Monthly Case Volume")
fig1 = go.Figure()
fig1.add_bar(x=_m.index, y=_m["drafting"], name="Drafting",
             marker_color=_COLORS["drafting"],
             text=_m["drafting"], textposition="inside")
fig1.add_bar(x=_m.index, y=_m["review"], name="Review",
             marker_color=_COLORS["review"],
             text=_m["review"], textposition="inside")
fig1.add_scatter(x=_m.index, y=_m["total"], name="Total",
                 mode="lines+markers", line=dict(color="#333", width=2),
                 marker=dict(size=6))
fig1.update_layout(
    barmode="stack", xaxis_title="Month", yaxis_title="Cases",
    hovermode="x unified", template="plotly_white",
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig1, use_container_width=True)



# ── Chart 2: Agency × Month heatmap ───────────────────────────────────────────
st.header("2. Agency × Month Heatmap (Top 30)")
_h = df.groupby(["agency", "month"]).size().unstack(fill_value=0)
_h["_total"] = _h.sum(axis=1)
_h = _h.sort_values("_total", ascending=False).head(30).drop(columns="_total")

fig3 = go.Figure(go.Heatmap(
    z=_h.values,
    x=_h.columns.tolist(),
    y=_h.index.tolist(),
    colorscale="Blues",
    text=_h.values,
    texttemplate="%{text}",
    hovertemplate="Agency: %{y}<br>Month: %{x}<br>Cases: %{z}<extra></extra>",
))
fig3.update_layout(
    xaxis_title="Month", template="plotly_white", height=800,
    xaxis=dict(tickangle=-45),
)
st.plotly_chart(fig3, use_container_width=True)

# ── Chart 3: Cumulative cases ──────────────────────────────────────────────────
st.header("3. Cumulative Cases Over Time")
_cum = _m[["drafting", "review", "total"]].cumsum()

fig4 = go.Figure()
fig4.add_scatter(x=_cum.index, y=_cum["total"], name="Total",
                 fill="tozeroy", line=dict(color="#555", width=2))
fig4.add_scatter(x=_cum.index, y=_cum["drafting"], name="Drafting",
                 line=dict(color=_COLORS["drafting"], width=2, dash="dot"))
fig4.add_scatter(x=_cum.index, y=_cum["review"], name="Review",
                 line=dict(color=_COLORS["review"], width=2, dash="dot"))
fig4.update_layout(
    xaxis_title="Month", yaxis_title="Cumulative Cases",
    template="plotly_white", hovermode="x unified",
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig4, use_container_width=True)

# ── Chart 4: Source breakdown donut ───────────────────────────────────────────
st.header("4. Cases by Source")
_src = df["source"].value_counts()
fig5 = go.Figure(go.Pie(
    labels=_src.index, values=_src.values,
    hole=0.45,
    marker_colors=["#2c7bb6", "#abd9e9"],
    textinfo="label+percent+value",
))
fig5.update_layout(template="plotly_white", height=450)
st.plotly_chart(fig5, use_container_width=True)

# ── Chart 5: Agency time series ────────────────────────────────────────────────
st.header("5. Monthly Cases Over Time by Agency")

_ts = (
    df.groupby(["agency", "month", "status"])
    .size()
    .unstack(fill_value=0)
    .reindex(columns=["drafting", "review"], fill_value=0)
    .reset_index()
)
_agency_order = df.groupby("agency").size().sort_values(ascending=False).index.tolist()

selected_agency = st.selectbox("Select agency", _agency_order)

ag = _ts[_ts["agency"] == selected_agency].sort_values("month")

fig6 = go.Figure()
fig6.add_scatter(
    x=ag["month"], y=ag["drafting"],
    name="Drafting", mode="lines+markers",
    line=dict(color=_COLORS["drafting"], width=2),
    marker=dict(size=7),
    hovertemplate="%{x}<br>Drafting: %{y}<extra></extra>",
)
fig6.add_scatter(
    x=ag["month"], y=ag["review"],
    name="Review", mode="lines+markers",
    line=dict(color=_COLORS["review"], width=2),
    marker=dict(size=7),
    hovertemplate="%{x}<br>Review: %{y}<extra></extra>",
)
fig6.update_layout(
    xaxis_title="Month", yaxis_title="Cases",
    template="plotly_white", height=480,
    hovermode="x unified",
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig6, use_container_width=True)
