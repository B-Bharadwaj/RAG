"""
styles.py
All CSS for the Multi-PDF RAG Assistant.
Import and call inject() once at the top of app.py.
"""

import streamlit as st

CSS = """
<style>

/* -- hide Streamlit default chrome ------------------------------------------ */
#MainMenu, footer, [data-testid="stDecoration"] { display:none !important; }

/* -- Base surfaces ----------------------------------------------------------- */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"]   { background:#0a0a0a !important; color:#e5e5e5; }
[data-testid="stSidebar"]         { background:#0d0d0d !important;
                                    border-right:1px solid #1f1f1f !important; }
[data-testid="stHeader"]          { background:#0a0a0a !important;
                                    border-bottom:1px solid #1f1f1f !important; }
[data-testid="stToolbar"]         { background:#0a0a0a !important; }

/* -- Typography -------------------------------------------------------------- */
h1,h2,h3,h4            { color:#ffffff !important; font-weight:700 !important; }
p, li, label, span     { color:#e5e5e5; }
.stMarkdown p          { color:#e5e5e5; line-height:1.65; }
code                   { background:#1a1a1a !important; color:#a5b4fc !important;
                         border:1px solid #2a2a2a !important;
                         border-radius:4px; padding:1px 6px; }

/* -- TAB BAR - override Streamlit default completely ------------------------- */
/* Kill the default red underline and white box */
[data-testid="stTabs"] [role="tablist"]          { background:#111111;
                                                   border:1px solid #222222;
                                                   border-radius:10px;
                                                   padding:4px; gap:3px;
                                                   box-shadow:none !important; }
[data-testid="stTabs"] [role="tab"]              { color:#6b7280 !important;
                                                   background:transparent !important;
                                                   border:none !important;
                                                   border-radius:7px !important;
                                                   font-size:0.84rem !important;
                                                   font-weight:500 !important;
                                                   padding:7px 20px !important;
                                                   outline:none !important;
                                                   box-shadow:none !important;
                                                   transition:all 0.15s; }
[data-testid="stTabs"] [role="tab"]:hover        { color:#d1d5db !important;
                                                   background:#1a1a1a !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"]
                                                 { color:#0a0a0a !important;
                                                   background:#727374 !important;
                                                   font-weight:600 !important; }
/* Kill the red bottom border Streamlit draws on active tab */
[data-testid="stTabs"] [role="tab"][aria-selected="true"]::before,
[data-testid="stTabs"] [role="tab"][aria-selected="true"]::after,
[data-testid="stTabs"] [role="tab"]::before,
[data-testid="stTabs"] [role="tab"]::after       { display:none !important;
                                                   border:none !important;
                                                   background:none !important; }
/* The underline bar Streamlit injects as a sibling div */
[data-testid="stTabs"] [role="tablist"] + div,
[data-testid="stTabs"] div[data-baseweb="tab-highlight"],
[data-testid="stTabs"] div[data-baseweb="tab-border"]
                                                 { display:none !important; }

/* -- Inputs ------------------------------------------------------------------ */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea    { background:#111111 !important;
                                         color:#ffffff !important;
                                         border:1px solid #2a2a2a !important;
                                         border-radius:8px !important;
                                         font-size:0.9rem !important; }
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus
                                       { border-color:#6366f1 !important;
                                         box-shadow:0 0 0 2px #6366f125 !important; }
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label       { color:#6b7280 !important;
                                         font-size:0.78rem !important; }

/* -- Selectbox --------------------------------------------------------------- */
[data-baseweb="select"] > div          { background:#111111 !important;
                                         border:1px solid #2a2a2a !important;
                                         color:#ffffff !important;
                                         border-radius:8px !important; }
[data-baseweb="select"] svg            { fill:#6b7280 !important; }
[data-baseweb="menu"]                  { background:#111111 !important;
                                         border:1px solid #2a2a2a !important; }
[data-baseweb="menu"] li               { color:#e5e5e5 !important; }
[data-baseweb="menu"] li:hover         { background:#1a1a1a !important; }

/* -- Buttons ----------------------------------------------------------------- */
[data-testid="stButton"] button        { background:#111111 !important;
                                         border:1px solid #2a2a2a !important;
                                         color:#e5e5e5 !important;
                                         border-radius:8px !important;
                                         font-size:0.84rem !important;
                                         transition:all 0.15s !important; }
[data-testid="stButton"] button:hover  { border-color:#6366f1 !important;
                                         color:#a5b4fc !important; }
[data-testid="stButton"] button[kind="primary"]
                                       { background:#6366f1 !important;
                                         border-color:#6366f1 !important;
                                         color:#ffffff !important; }
[data-testid="stButton"] button[kind="primary"]:hover
                                       { background:#4f52d0 !important; }
[data-testid="stFormSubmitButton"] button
                                       { background:#6366f1 !important;
                                         border:none !important;
                                         color:#ffffff !important;
                                         border-radius:8px !important;
                                         font-weight:600 !important; }

/* -- Chat messages ----------------------------------------------------------- */
[data-testid="stChatMessage"]          { background:transparent !important;
                                         border:none !important;
                                         padding:2px 0 !important; }
[data-testid="stChatMessageAvatar"]    { background:#1a1a1a !important;
                                         border:1px solid #2a2a2a !important;
                                         border-radius:50% !important; }

/* -- Expanders --------------------------------------------------------------- */
[data-testid="stExpander"]             { background:#111111 !important;
                                         border:1px solid #1f1f1f !important;
                                         border-radius:8px !important; }
[data-testid="stExpander"] summary     { color:#9ca3af !important;
                                         font-size:0.84rem !important; }
[data-testid="stExpander"] summary:hover { color:#ffffff !important; }

/* -- Dataframe --------------------------------------------------------------- */
[data-testid="stDataFrame"]            { border:1px solid #1f1f1f !important;
                                         border-radius:8px !important;
                                         overflow:hidden; }
[data-testid="stDataFrame"] th         { background:#111111 !important;
                                         color:#6b7280 !important;
                                         font-size:0.75rem !important;
                                         text-transform:uppercase;
                                         letter-spacing:0.04em; }
[data-testid="stDataFrame"] td         { background:#0a0a0a !important;
                                         color:#e5e5e5 !important;
                                         font-size:0.85rem !important; }
[data-testid="stDataFrame"] tr:hover td { background:#111111 !important; }

/* -- Progress ---------------------------------------------------------------- */
[data-testid="stProgressBar"] > div    { background:#6366f1 !important; }

/* -- Divider ----------------------------------------------------------------- */
hr                                     { border-color:#1f1f1f !important; margin:1.5rem 0; }

/* -- Scrollbar --------------------------------------------------------------- */
::-webkit-scrollbar                    { width:5px; height:5px; }
::-webkit-scrollbar-track              { background:#0a0a0a; }
::-webkit-scrollbar-thumb              { background:#2a2a2a; border-radius:3px; }
::-webkit-scrollbar-thumb:hover        { background:#3a3a3a; }

/* -- KPI grid (SENN dashboard style) ---------------------------------------- */
.kpi-grid  { display:flex; gap:48px; flex-wrap:wrap; margin:0.4rem 0 1.5rem; }
.kpi-item  { display:flex; flex-direction:column; gap:6px; }
.kpi-label { font-size:0.78rem; color:#6b7280; font-weight:400; letter-spacing:0.01em; }
.kpi-value { font-size:2.1rem; font-weight:700; color:#ffffff; line-height:1; }
.kpi-sm    { font-size:1.5rem; font-weight:700; color:#ffffff; line-height:1; }

/* -- Section headings -------------------------------------------------------- */
.sec-title { font-size:1.05rem; font-weight:700; color:#ffffff;
             margin:1.4rem 0 0.7rem; letter-spacing:-0.01em; }
.muted     { font-size:0.78rem; color:#6b7280; margin:0; }

/* -- Score badges ------------------------------------------------------------ */
.badge-g { background:#052e16; color:#4ade80; padding:2px 10px;
           border-radius:20px; font-size:0.75rem; font-weight:600; }
.badge-m { background:#1c1000; color:#facc15; padding:2px 10px;
           border-radius:20px; font-size:0.75rem; font-weight:600; }
.badge-r { background:#1f0000; color:#f87171; padding:2px 10px;
           border-radius:20px; font-size:0.75rem; font-weight:600; }

/* -- Terminal log box -------------------------------------------------------- */
.log-term  { background:#000000; border:1px solid #1f1f1f; border-radius:8px;
             padding:1rem; font-family:'JetBrains Mono','Fira Code',monospace;
             font-size:0.76rem; color:#4ade80; max-height:220px;
             overflow-y:auto; white-space:pre-wrap; line-height:1.6; }

/* -- Source card ------------------------------------------------------------- */
.src-card  { background:#111111; border:1px solid #1f1f1f; border-radius:6px;
             padding:0.6rem 0.9rem; margin:4px 0; font-size:0.8rem;
             color:#9ca3af; line-height:1.5; }

/* -- Empty state ------------------------------------------------------------- */
.empty-box { text-align:center; padding:3rem 1rem; border:1px solid #1f1f1f;
             border-radius:12px; background:#0d0d0d; margin:1rem 0; }
.empty-icon  { font-size:2.5rem; margin-bottom:10px; }
.empty-title { font-size:0.95rem; color:#9ca3af; font-weight:500; }
.empty-sub   { font-size:0.78rem; color:#4b5563; margin-top:4px; }

/* -- Example chip buttons ---------------------------------------------------- */
div[data-testid="column"] [data-testid="stButton"] button {
    border-radius:20px !important;
    font-size:0.74rem !important;
    color:#9ca3af !important;
    padding:4px 12px !important;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
div[data-testid="column"] [data-testid="stButton"] button:hover {
    color:#a5b4fc !important;
    border-color:#6366f1 !important;
}

/* -- Sidebar ----------------------------------------------------------------- */
.sb-title { font-size:1rem; font-weight:700; color:#ffffff; margin:0; }
.sb-sub   { font-size:0.72rem; color:#4b5563; margin:2px 0 0; }
.sb-count { font-size:0.8rem; color:#6b7280; }

</style>
"""


def inject():
    """Inject the dark theme CSS into the Streamlit app."""
    st.markdown(CSS, unsafe_allow_html=True)
