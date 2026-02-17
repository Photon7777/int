import io
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st
from pypdf import PdfReader
from docx import Document
from autofill import extract_fields

from tools import fetch_job_post, safe_clip
from agent import generate_application_materials

from db_store import (
    append_row,
    read_tracker_df,
    ensure_row_ids,
    overwrite_tracker_for_user,
    merge_uploaded_csv,
    replace_with_uploaded_csv,
    # make sure you added these in db_store.py
    delete_all_for_user,
    admin_list_users,
)

# auth helpers (make sure auth.py supports these)
from auth import create_user, verify_user, change_password, delete_user


# -------------------------
# PAGE CONFIG + LIGHT UI POLISH
# -------------------------
st.set_page_config(page_title="Internship Application Agent", layout="wide")
st.title("Internship Application Agent")
st.caption("Generate tailored application materials and maintain a private tracker — per user.")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
      section[data-testid="stSidebar"] { padding-top: 1rem; }
      h1, h2, h3 { letter-spacing: -0.02em; }

      .card {
        border: 1px solid rgba(49, 51, 63, 0.15);
        border-radius: 14px;
        padding: 14px 16px;
        background: rgba(255,255,255,0.04);
        margin-bottom: 0.75rem;
      }
      .muted { color: rgba(255,255,255,0.65); }
      .small { font-size: 0.9rem; color: rgba(255,255,255,0.75); }

      div.stButton > button, div.stDownloadButton > button {
        border-radius: 10px;
        padding: 0.55rem 0.9rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["🧠 Generate Pack", "📌 Tracker"])


# -------------------------
# AUTH (LOGIN + SIGNUP)
# -------------------------
def auth_box() -> str:
    if st.session_state.get("user_id"):
        return st.session_state["user_id"]

    with st.sidebar:
        st.markdown("### 👤 Account")
        mode = st.radio("Mode", ["Log in", "Sign up"], horizontal=True)

        username = st.text_input("Username", key="auth_user")
        password = st.text_input("Password", type="password", key="auth_pass")

        if mode == "Sign up":
            password2 = st.text_input("Confirm password", type="password", key="auth_pass2")
            if st.button("Create account", use_container_width=True):
                try:
                    if (username or "").strip() == "" or (password or "").strip() == "":
                        st.error("Username and password are required.")
                        st.stop()
                    if password != password2:
                        st.error("Passwords do not match.")
                        st.stop()
                    create_user(username, password)
                    st.success("Account created ✅ Now switch to Log in.")
                except Exception as e:
                    st.error(str(e))
        else:
            if st.button("Log in", type="primary", use_container_width=True):
                if verify_user(username, password):
                    st.session_state["user_id"] = (username or "").strip()
                    st.rerun()
                else:
                    st.error("Invalid username/password")

    st.stop()


user_id = auth_box()

# Sidebar header + logout
with st.sidebar:
    st.markdown(
        f"""
        <div class="card">
          <div class="small">Signed in as</div>
          <div style="font-size:1.05rem;"><b>{user_id}</b></div>
          <div class="muted small">Private tracker enabled ✅</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Log out", use_container_width=True):
        st.session_state["user_id"] = ""
        st.rerun()


# -------------------------
# ACCOUNT SETTINGS (Change password / Delete account)
# -------------------------
with st.sidebar.expander("⚙️ Account settings", expanded=False):
    st.markdown("#### Change password")
    with st.form("change_pw_form"):
        cur = st.text_input("Current password", type="password", key="pw_cur")
        new = st.text_input("New password", type="password", key="pw_new")
        new2 = st.text_input("Confirm new password", type="password", key="pw_new2")
        ok = st.form_submit_button("Update password")
        if ok:
            try:
                if new != new2:
                    st.error("New passwords do not match.")
                else:
                    change_password(user_id, cur, new)
                    st.success("Password updated ✅")
            except Exception as e:
                st.error(str(e))

    st.divider()

    st.markdown("#### Delete my account")
    st.warning("This permanently deletes your account AND all your tracker entries.")
    with st.form("delete_account_form"):
        del_pw = st.text_input("Password to confirm", type="password", key="del_pw")
        confirm_text = st.text_input('Type DELETE to confirm', key="del_confirm")
        do_del = st.form_submit_button("Delete account permanently")
        if do_del:
            try:
                if confirm_text.strip().upper() != "DELETE":
                    st.error("Confirmation text must be DELETE.")
                else:
                    delete_all_for_user(user_id)
                    delete_user(user_id, del_pw)
                    st.session_state["user_id"] = ""
                    st.success("Account deleted ✅")
                    st.rerun()
            except Exception as e:
                st.error(str(e))


# -------------------------
# ADMIN VIEW (only for admins in secrets)
# -------------------------
admins = st.secrets.get("admin_users", [])
is_admin = user_id in admins

if is_admin:
    with st.sidebar.expander("🛡️ Admin", expanded=False):
        admin_mode = st.checkbox("Enable admin panel", value=False)

    if admin_mode:
        st.markdown("## 🛡️ Admin panel")
        st.caption("Read-only: users + job counts. Optional: view a user's tracker.")

        users_df = admin_list_users()
        st.dataframe(users_df, use_container_width=True)

        if not users_df.empty and "user_id" in users_df.columns:
            target = st.selectbox("View tracker as user", users_df["user_id"].tolist())
            view_df = read_tracker_df(target).drop(columns=["_row_id"], errors="ignore")
            st.markdown(f"### Tracker for: {target}")
            st.dataframe(view_df, use_container_width=True)
        st.divider()


# -------------------------
# SESSION STATE DEFAULTS
# -------------------------
defaults = {
    "company_input": "",
    "role_input": "",
    "location_input": "",
    "contact_name_input": "",
    "contact_link_input": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "resume_text" not in st.session_state:
    st.session_state["resume_text"] = ""
if "resume_name" not in st.session_state:
    st.session_state["resume_name"] = ""

if "show_add_form" not in st.session_state:
    st.session_state["show_add_form"] = False

if "tracker_last_saved" not in st.session_state:
    st.session_state["tracker_last_saved"] = ""


# -------------------------
# HELPERS
# -------------------------
def read_pdf(file) -> str:
    reader = PdfReader(file)
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    return "\n".join(pages).strip()


def read_txt(file) -> str:
    return file.read().decode("utf-8", errors="ignore").strip()


def make_docx(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Applications")
    return bio.getvalue()


def _coerce_editor_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    text_cols = ["Company", "Role", "Job Link", "Location", "Status", "Contact Name", "Contact Link", "Notes"]
    date_cols = ["Date Applied", "Follow-up Date"]

    for c in text_cols:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    for c in date_cols:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    if "Delete" in df.columns:
        df["Delete"] = df["Delete"].fillna(False).astype(bool)

    return df


# -------------------------
# TAB 1: GENERATE PACK
# -------------------------
with tabs[0]:
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Step 1 — Job details")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        job_url = st.text_input("Job posting URL (optional)", placeholder="https://…")
        job_desc = st.text_area("Or paste job description", height=170, placeholder="Paste the job description…")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### Step 2 — Resume + notes")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        resume_file = st.file_uploader("Upload your resume (PDF or TXT)", type=["pdf", "txt"])

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🧹 Clear stored resume"):
                st.session_state["resume_text"] = ""
                st.session_state["resume_name"] = ""
                st.success("Stored resume cleared ✅")
                st.rerun()
        with c2:
            st.caption(f"Stored: **{st.session_state['resume_name']}**" if st.session_state["resume_name"] else "No resume stored yet.")

        if resume_file is not None and resume_file.name != st.session_state["resume_name"]:
            try:
                if resume_file.type == "application/pdf":
                    st.session_state["resume_text"] = read_pdf(resume_file)
                else:
                    st.session_state["resume_text"] = read_txt(resume_file)
                st.session_state["resume_name"] = resume_file.name
                st.success("Resume saved in memory ✅")
            except Exception as e:
                st.error(f"Could not read resume file. Error: {e}")

        extra_notes = st.text_area("Extra notes (optional)", height=100, placeholder="Anything to emphasize…")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### Step 3 — Tracker fields")
        with st.expander("📌 Tracker fields (recommended)", expanded=True):
            autofill_clicked = st.button("✨ Auto-fill from job post")

            # Determine autofill text
            autofill_source_text = job_desc.strip()
            if not autofill_source_text and job_url:
                try:
                    autofill_source_text = fetch_job_post(job_url)
                except Exception:
                    autofill_source_text = ""

            if autofill_clicked:
                if not autofill_source_text:
                    st.warning("Paste a job description or provide a fetchable URL to auto-fill.")
                else:
                    with st.spinner("Extracting company / role / location…"):
                        fields = extract_fields(autofill_source_text)
                    st.session_state["company_input"] = fields.get("company", "") or ""
                    st.session_state["role_input"] = fields.get("role", "") or ""
                    st.session_state["location_input"] = fields.get("location", "") or ""
                    st.success("Auto-filled ✅")
                    st.rerun()

            company = st.text_input("Company", key="company_input")
            role = st.text_input("Role / Title", key="role_input")
            location = st.text_input("Location (optional)", key="location_input")

            colA, colB = st.columns(2)
            with colA:
                status = st.selectbox(
                    "Status",
                    ["Interested", "Applied", "OA", "Interview", "Offer", "Rejected", "Ghosted"],
                    index=0,
                )
                date_applied = st.date_input("Date Applied", value=date.today())
            with colB:
                follow_up_date = st.date_input("Follow-up Date", value=date.today() + timedelta(days=7))
                log_to_tracker = st.checkbox("Log this to your tracker", value=True)

            contact_name = st.text_input("Contact Name (optional)", key="contact_name_input")
            contact_link = st.text_input("Contact Link (optional)", key="contact_link_input")

        run = st.button("🚀 Generate Application Pack", type="primary")

    with right:
        st.markdown("### Output")
        st.caption("Your application pack will appear here.")
        if run:
            resume_text = (st.session_state.get("resume_text") or "").strip()
            if not resume_text:
                st.error("No resume stored. Upload a resume first (or don’t clear it).")
                st.stop()

            job_post_text = ""
            if job_url:
                try:
                    job_post_text = fetch_job_post(job_url)
                except Exception as e:
                    st.warning(f"Could not fetch job URL (some sites block scraping). Paste description instead. Error: {e}")

            if not job_post_text:
                job_post_text = job_desc.strip()

            if not job_post_text:
                st.error("Provide a job URL that can be fetched OR paste the job description.")
                st.stop()

            # Auto-fill on generate if blank
            if (
                not st.session_state["company_input"].strip()
                or not st.session_state["role_input"].strip()
                or not st.session_state["location_input"].strip()
            ):
                with st.spinner("Auto-filling Company/Role/Location…"):
                    fields = extract_fields(job_post_text)

                if not st.session_state["company_input"].strip():
                    st.session_state["company_input"] = fields.get("company", "") or ""
                if not st.session_state["role_input"].strip():
                    st.session_state["role_input"] = fields.get("role", "") or ""
                if not st.session_state["location_input"].strip():
                    st.session_state["location_input"] = fields.get("location", "") or ""

                company = st.session_state["company_input"]
                role = st.session_state["role_input"]
                location = st.session_state["location_input"]

            with st.spinner("Generating…"):
                output = generate_application_materials(
                    job_post=safe_clip(job_post_text, 20000),
                    resume_text=safe_clip(resume_text, 20000),
                    extra_notes=extra_notes,
                )

            st.success("Generated ✅")

            with st.expander("📄 Application Pack", expanded=True):
                st.text_area("", value=output, height=520)

            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    "⬇️ Download .txt",
                    data=output.encode("utf-8"),
                    file_name="application_pack.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "⬇️ Download .docx",
                    data=make_docx(output),
                    file_name="application_pack.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

            if log_to_tracker:
                try:
                    append_row(
                        user_id,
                        {
                            "Date Applied": str(date_applied),
                            "Company": company,
                            "Role": role,
                            "Job Link": job_url or "",
                            "Location": location,
                            "Status": status,
                            "Follow-up Date": str(follow_up_date),
                            "Contact Name": contact_name,
                            "Contact Link": contact_link,
                            "Notes": extra_notes,
                        },
                    )
                    st.success("Logged to your tracker ✅")
                except Exception as e:
                    st.error(f"Could not write to tracker DB. Error: {e}")
        else:
            st.info("Fill job details, upload resume, then click Generate.")


# -------------------------
# TAB 2: TRACKER
# -------------------------
with tabs[1]:
    st.markdown(f"### 📌 Tracker — {user_id}")
    st.caption("Edits are saved to your private SQLite tracker.")

    # Load tracker
    try:
        df = read_tracker_df(user_id)
    except Exception as e:
        st.error(f"Could not read tracker DB. Error: {e}")
        st.stop()

    # Add job button at top
    topA, topB = st.columns([1, 3])
    with topA:
        if st.button("➕ Add job", type="primary", use_container_width=True):
            st.session_state["show_add_form"] = True

    with topB:
        if st.session_state.get("tracker_last_saved"):
            st.caption(f"Last saved: {st.session_state['tracker_last_saved']}")

    if st.session_state["show_add_form"]:
        with st.expander("Add a job", expanded=True):
            with st.form("add_job_form", clear_on_submit=True):
                a1, a2 = st.columns(2)
                with a1:
                    new_company = st.text_input("Company")
                    new_role = st.text_input("Role / Title")
                    new_job_link = st.text_input("Job Link")
                    new_location = st.text_input("Location")
                    new_status = st.selectbox(
                        "Status",
                        ["Interested", "Applied", "OA", "Interview", "Offer", "Rejected", "Ghosted"],
                        index=0,
                        key="manual_status",
                    )
                with a2:
                    new_date_applied = st.date_input("Date Applied", value=date.today(), key="manual_date_applied")
                    new_follow_up = st.date_input("Follow-up Date", value=date.today() + timedelta(days=7), key="manual_followup")
                    new_contact_name = st.text_input("Contact Name")
                    new_contact_link = st.text_input("Contact Link")
                    new_notes = st.text_area("Notes", height=90)

                cadd, ccancel = st.columns(2)
                with cadd:
                    submitted = st.form_submit_button("Add to tracker")
                with ccancel:
                    cancel = st.form_submit_button("Cancel")

                if cancel:
                    st.session_state["show_add_form"] = False
                    st.rerun()

                if submitted:
                    append_row(
                        user_id,
                        {
                            "Date Applied": str(new_date_applied),
                            "Company": new_company,
                            "Role": new_role,
                            "Job Link": new_job_link,
                            "Location": new_location,
                            "Status": new_status,
                            "Follow-up Date": str(new_follow_up),
                            "Contact Name": new_contact_name,
                            "Contact Link": new_contact_link,
                            "Notes": new_notes,
                        },
                    )
                    st.session_state["show_add_form"] = False
                    st.success("Added ✅")
                    st.rerun()

    st.divider()

    if df.empty:
        st.info("Your tracker is empty. Add a job or generate a pack and log it.")
        st.stop()

    df = ensure_row_ids(df)

    # Overview metrics
    st.markdown("#### 📊 Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", len(df))
    m2.metric("Applied", int((df["Status"].astype(str) == "Applied").sum()))
    m3.metric("Interview", int((df["Status"].astype(str) == "Interview").sum()))
    m4.metric("Offers", int((df["Status"].astype(str) == "Offer").sum()))

    # Next follow-ups
    if "Follow-up Date" in df.columns:
        up = df.copy()
        up["Follow-up Date"] = up["Follow-up Date"].astype(str)
        up = up[up["Follow-up Date"].str.strip() != ""]
        up = up.sort_values("Follow-up Date", ascending=True).head(5)
        with st.expander("⏰ Next follow-ups", expanded=False):
            show_cols = [c for c in ["Company", "Role", "Status", "Follow-up Date"] if c in up.columns]
            st.dataframe(up[show_cols], use_container_width=True, hide_index=True)

    st.divider()

    # Filters
    st.markdown("#### 🔎 Filter")
    f1, f2, f3 = st.columns(3)
    with f1:
        statuses = sorted([s for s in df["Status"].dropna().unique().tolist() if str(s).strip() != ""])
        status_filter = st.multiselect("Status", statuses)
    with f2:
        company_search = st.text_input("Company contains")
    with f3:
        role_search = st.text_input("Role contains")

    filtered = df.copy()
    if status_filter:
        filtered = filtered[filtered["Status"].isin(status_filter)]
    if company_search:
        filtered = filtered[filtered["Company"].astype(str).str.contains(company_search, case=False, na=False)]
    if role_search:
        filtered = filtered[filtered["Role"].astype(str).str.contains(role_search, case=False, na=False)]

    # Editor
    st.markdown("#### 🧾 Tracker table")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    editor_df = filtered.copy()
    if "Delete" not in editor_df.columns:
        editor_df["Delete"] = False

    editor_df = _coerce_editor_types(editor_df)
    editor_df = editor_df.set_index("_row_id", drop=True)

    edited = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete",
                help="Tick and click Save changes to remove the row.",
                default=False,
            ),
        },
        key="tracker_editor",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    a, b, c = st.columns([1, 1, 2])
    with a:
        if st.button("💾 Save changes", type="primary", use_container_width=True):
            try:
                out = edited.reset_index().rename(columns={"index": "_row_id"})
                if "Delete" in out.columns:
                    out = out[out["Delete"] != True].copy()  # noqa: E712
                    out = out.drop(columns=["Delete"], errors="ignore")

                out = out.fillna("").astype(str)
                overwrite_tracker_for_user(user_id, out)

                st.session_state["tracker_last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Saved ✅")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed. Error: {e}")

    with b:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    with c:
        st.caption("Tip: Use Delete checkboxes for quick removals. All edits save to your private tracker.")

    # Downloads (exclude _row_id)
    st.divider()
    download_df = filtered.drop(columns=["_row_id"], errors="ignore")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ Download CSV",
            data=download_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{user_id}_tracker.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "⬇️ Download Excel (.xlsx)",
            data=df_to_xlsx_bytes(download_df),
            file_name=f"{user_id}_tracker.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()

    # Import
    st.markdown("#### 📥 Import")
    upload = st.file_uploader("Upload CSV", type=["csv"], key="tracker_upload")
    mode = st.radio("Import mode", ["Merge into tracker", "Replace tracker"], horizontal=True)
    dedupe = st.checkbox("De-dupe after merge (Company + Role + Job Link + Date Applied)", value=True)

    if st.button("Import now", use_container_width=True):
        if not upload:
            st.error("Please upload a CSV file first.")
        else:
            try:
                uploaded_df = pd.read_csv(upload)
                if mode.startswith("Merge"):
                    merge_uploaded_csv(user_id, uploaded_df, dedupe=dedupe)
                    st.success("Imported via merge ✅")
                else:
                    replace_with_uploaded_csv(user_id, uploaded_df)
                    st.success("Replaced tracker ✅")
                st.rerun()
            except Exception as e:
                st.error(f"Import failed. Make sure it’s a valid CSV. Error: {e}")