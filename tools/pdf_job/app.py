"""Beginner-friendly Streamlit UI for Coconala PDF → Excel jobs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pdf_job import service  # noqa: E402

st.set_page_config(
    page_title="構造くん | PDF表→Excel",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Dark workspace with high-contrast text (readable on charcoal panels)
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+JP:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --bg: #0b1220;
  --panel: #152033;
  --panel-2: #1c2a42;
  --ink: #f8fafc;
  --muted: #cbd5e1;
  --line: #334155;
  --accent: #5eead4;
  --accent-deep: #2dd4bf;
  --btn: #0d9488;
  --btn-hover: #14b8a6;
  --warn-bg: #3b250f;
  --ok-bg: #0f2f28;
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans JP", "Hiragino Sans", sans-serif;
  color: var(--ink) !important;
}

.stApp {
  background:
    radial-gradient(900px 420px at 0% 0%, rgba(45, 212, 191, 0.12) 0%, transparent 55%),
    radial-gradient(800px 380px at 100% 10%, rgba(251, 191, 36, 0.08) 0%, transparent 50%),
    linear-gradient(180deg, #0b1220 0%, #111827 100%);
  color: var(--ink);
}

#MainMenu, footer { visibility: hidden; }
header { visibility: hidden; }

.block-container {
  padding-top: 1.2rem;
  padding-bottom: 3rem;
  max-width: 1100px;
}

/* Force readable text across Streamlit widgets */
.stMarkdown, .stMarkdown p, .stMarkdown li, .stCaption, label,
[data-testid="stWidgetLabel"] p, [data-testid="stMetricValue"],
[data-testid="stMetricLabel"], .stTextInput label, .stSelectbox label {
  color: var(--ink) !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
}

.brand-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
  padding: 1rem 1.15rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(135deg, #152033 0%, #1a2740 60%, #1f2937 100%);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
}
.brand-bar h1 {
  font-family: "Fraunces", "IBM Plex Sans JP", serif;
  font-size: 1.85rem;
  line-height: 1.15;
  margin: 0;
  color: #ecfeff !important;
  letter-spacing: 0.01em;
}
.brand-bar p {
  margin: 0.35rem 0 0;
  color: #e2e8f0 !important;
  font-size: 0.95rem;
}
.brand-pill {
  white-space: nowrap;
  background: var(--btn);
  color: #042f2e !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.8rem;
  font-weight: 700;
}

.job-strip {
  margin: 0.4rem 0 1rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px dashed #475569;
  background: rgba(21, 32, 51, 0.9);
  color: #f8fafc !important;
}
.job-strip strong { color: var(--accent) !important; }

div[data-testid="stTabs"] {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 0.35rem 0.75rem 1rem;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
}
div[data-testid="stTabs"] button[role="tab"] {
  font-weight: 700;
  color: #94a3b8 !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: #ecfeff !important;
}
div[data-testid="stTabs"] div[data-baseweb="tab-highlight"],
div[data-testid="stTabs"] [data-testid="stTabHighlight"] {
  background-color: var(--accent-deep) !important;
}

/* Inputs / selects */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
.stTextInput input, .stNumberInput input {
  background-color: #0f172a !important;
  color: #f8fafc !important;
  border-color: #475569 !important;
  caret-color: #f8fafc !important;
}
div[data-baseweb="select"] svg { fill: #e2e8f0 !important; }

.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(180deg, #14b8a6 0%, #0d9488 100%) !important;
  border: 1px solid #5eead4 !important;
  color: #042f2e !important;
  font-weight: 700 !important;
  border-radius: 12px;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="baseButton-secondary"] {
  border-radius: 12px;
  border: 1px solid #64748b !important;
  color: #f8fafc !important;
  background: #1e293b !important;
}

div[data-testid="stAlert"] {
  border-radius: 12px;
  color: #f8fafc !important;
}
section[data-testid="stFileUploader"] {
  background: #1e293b;
  border: 1px solid #475569;
  border-radius: 12px;
  padding: 0.4rem;
  color: #f8fafc !important;
}

/* Dataframes / editors */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 10px;
}
[data-testid="stDataFrame"] *, [data-testid="stDataEditor"] * {
  color: #f1f5f9 !important;
}

code, pre, .stCodeBlock {
  background: #0f172a !important;
  color: #e2e8f0 !important;
}
</style>
"""


def _ensure_state() -> None:
    st.session_state.setdefault("job_name", "")


def _job_options() -> list[str]:
    return [p.name for p in service.list_jobs()]


def _current_job() -> Path | None:
    name = st.session_state.get("job_name") or ""
    if not name:
        return None
    try:
        return service.resolve_job(name)
    except FileNotFoundError:
        return None


def _require_job() -> Path | None:
    job = _current_job()
    if job is None:
        st.warning("上の「いまの案件」で案件を選ぶか、「案件」タブで新規作成してください。")
        return None
    return job


def render_brand() -> None:
    st.markdown(
        """
        <div class="brand-bar">
          <div>
            <h1>構造くん</h1>
            <p>PDFの表を、依頼どおりのExcel / CSVに整える作業台（ココナラ受注用）</p>
          </div>
          <div class="brand-pill">暗色ハイコントラスト</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_job_strip() -> None:
    options = _job_options()
    left, right = st.columns([3, 2])
    with left:
        if options:
            current = st.session_state.get("job_name") or ""
            index = options.index(current) if current in options else 0
            selected = st.selectbox(
                "いまの案件",
                options,
                index=index,
                help="どのタブにいても、ここで案件を切り替えられます",
            )
            st.session_state.job_name = selected
        else:
            st.selectbox("いまの案件", ["（まだありません）"], disabled=True)
            st.session_state.job_name = ""
    with right:
        st.caption("ヒント")
        st.write("タブは好きな順に開けます。戻るボタンは不要です。")

    job = _current_job()
    if job:
        st.markdown(
            f'<div class="job-strip">作業中: <strong>{job.name}</strong></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="job-strip">案件未選択 — まず「案件」タブでフォルダを作ってください</div>',
            unsafe_allow_html=True,
        )


def tab_job() -> None:
    st.subheader("案件フォルダ")
    st.write("受注したら、お客様ごとにフォルダを1つ作ります。")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 新規")
        name = st.text_input("お客様名や案件名", placeholder="例: tanaka / 請求明細A", key="new_job_name")
        if st.button("案件フォルダを作る", type="primary", use_container_width=True, key="btn_create_job"):
            if not name.strip():
                st.error("名前を入力してください")
            else:
                try:
                    folder = service.create_job(name.strip())
                    st.session_state.job_name = folder.name
                    st.success(f"作りました: {folder.name}")
                    st.rerun()
                except FileExistsError as exc:
                    st.error(str(exc))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"作成に失敗しました: {exc}")

    with c2:
        st.markdown("##### 既存を開く")
        options = _job_options()
        if not options:
            st.info("まだ案件がありません。左で作成してください。")
            return
        selected = st.selectbox("案件フォルダ", options, key="open_job_select")
        if st.button("この案件にする", use_container_width=True, key="btn_open_job"):
            st.session_state.job_name = selected
            st.success(f"選択中: {selected}")
            st.rerun()


def tab_pdf() -> None:
    job = _require_job()
    if job is None:
        return

    st.subheader("PDFの受け取りと確認")
    st.caption(f"保存先: `{job / '01_input'}`")

    uploaded = st.file_uploader("お客様のPDFをアップロード", type=["pdf"], key="pdf_uploader")
    if uploaded is not None:
        saved = service.save_uploaded_pdf(job, uploaded.name, uploaded.getvalue())
        st.success(f"保存しました: {saved.name}")

    try:
        pdf = service.find_pdf(job)
        st.write(f"現在のPDF: **{pdf.name}**")
    except FileNotFoundError:
        st.warning("まだPDFがありません。上からアップロードしてください。")
        return

    if st.button("PDFをチェックする", type="primary", key="btn_check_pdf"):
        result = service.check_job(job)
        st.session_state["last_check"] = result
        m1, m2 = st.columns(2)
        m1.metric("ページ数", result["pages"])
        m2.metric("文字選択", "できる" if result["selectable"] else "できない")
        if result["selectable"]:
            st.success(result["messages"][0])
        else:
            st.error(result["messages"][0])
        for msg in result["messages"][1:]:
            st.warning(msg)

    if "last_check" in st.session_state and st.session_state.get("job_name"):
        cached = st.session_state["last_check"]
        if cached.get("pdf_name"):
            st.caption(f"直近チェック: {cached['pdf_name']} / {cached['pages']}ページ")


def tab_columns() -> None:
    job = _require_job()
    if job is None:
        return

    st.subheader("依頼された列の設定")
    st.write("左が納品する列名、右がPDF側にありそうな見出しです。")

    data = service.load_columns_yaml(job)
    pages_val = data.get("pages")
    pages_text = "" if pages_val in (None, "null") else ",".join(str(p) for p in pages_val)
    pages_text = st.text_input(
        "対象ページ（例: 1,2,3 / 空欄=全部）",
        value=pages_text,
        help="基本料金は5ページまで",
        key="pages_input",
    )

    columns = data.get("columns") or []
    if not columns:
        columns = [
            {"name": "日付", "source": ["日付"], "type": "date"},
            {"name": "品名", "source": ["商品名", "品名"], "type": "text"},
            {"name": "数量", "source": ["数量"], "type": "number"},
            {"name": "金額", "source": ["金額"], "type": "number"},
        ]

    edited = st.data_editor(
        pd.DataFrame(
            [
                {
                    "納品名": c.get("name", ""),
                    "PDFの見出し（カンマ区切り）": ", ".join(c.get("source") or [c.get("name", "")]),
                    "種類": c.get("type", "text"),
                }
                for c in columns
            ]
        ),
        num_rows="dynamic",
        use_container_width=True,
        key="columns_editor",
        column_config={
            "種類": st.column_config.SelectboxColumn(
                options=["text", "number", "date"],
                required=True,
            )
        },
    )

    if st.button("列設定を保存", type="primary", key="btn_save_columns"):
        new_cols = []
        for _, row in edited.iterrows():
            name = str(row["納品名"]).strip()
            if not name or name == "nan":
                continue
            sources = [s.strip() for s in str(row["PDFの見出し（カンマ区切り）"]).split(",") if s.strip()]
            new_cols.append(
                {
                    "name": name,
                    "source": sources or [name],
                    "type": str(row["種類"]).strip() or "text",
                }
            )
        if pages_text.strip():
            try:
                pages = [int(p.strip()) for p in pages_text.split(",") if p.strip()]
            except ValueError:
                st.error("ページは数字をカンマ区切りで入力してください")
                return
        else:
            pages = None
        service.save_columns_yaml(job, {"pages": pages, "columns": new_cols})
        st.success("保存しました。次は「抽出」タブへ。")


def tab_extract() -> None:
    job = _require_job()
    if job is None:
        return

    st.subheader("表の抽出プレビュー")
    if st.button("抽出する", type="primary", key="btn_extract"):
        try:
            result = service.extract_job(job)
            st.session_state["extract_result"] = result
            if result["found_any"]:
                st.success(f"抽出しました: {result['preview_path'].name}")
            else:
                st.error("表が取れませんでした。スキャンの可能性があります。")
        except Exception as exc:  # noqa: BLE001
            st.error(f"抽出に失敗しました: {exc}")

    result = st.session_state.get("extract_result")
    if not result:
        st.info("まだ抽出していません。「抽出する」を押してください。")
        return

    st.markdown("##### 見つかった表一覧")
    st.dataframe(result["index"], use_container_width=True)
    for item in result["tables"]:
        with st.expander(f"{item['sheet']}（page {item['page']}）", expanded=False):
            if item["note"]:
                st.warning(item["note"])
            if item["dataframe"] is not None and not item["dataframe"].empty:
                st.dataframe(item["dataframe"], use_container_width=True)
            else:
                st.write("（空）")
    preview_path: Path = result["preview_path"]
    if preview_path.exists():
        st.download_button(
            "プレビューExcelをダウンロード",
            data=preview_path.read_bytes(),
            file_name=preview_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_preview",
        )


def tab_deliver() -> None:
    job = _require_job()
    if job is None:
        return

    st.subheader("納品ファイル")
    st.info("作ったあと、必ず先頭・末尾と金額を元PDFと目視で突合してください。")

    if st.button("成果物をつくる", type="primary", key="btn_deliver"):
        try:
            result = service.deliver_job(job)
            st.session_state["deliver_result"] = result
            st.success(f"作成完了: {result['rows']}行 / 要確認 {result['review_rows']}件")
        except Exception as exc:  # noqa: BLE001
            st.error(f"作成に失敗しました: {exc}")

    result = st.session_state.get("deliver_result")
    if not result:
        return

    view_tabs = st.tabs(["data（納品本体）", "review（要確認）", "log（作業メモ）"])
    with view_tabs[0]:
        show = result["data"].drop(
            columns=[c for c in result["data"].columns if str(c).startswith("_")],
            errors="ignore",
        )
        st.dataframe(show, use_container_width=True)
    with view_tabs[1]:
        st.dataframe(result["review"], use_container_width=True)
    with view_tabs[2]:
        st.dataframe(result["log"], use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Excelをダウンロード",
            data=Path(result["xlsx"]).read_bytes(),
            file_name=Path(result["xlsx"]).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_xlsx",
        )
    with c2:
        st.download_button(
            "CSVをダウンロード",
            data=Path(result["csv"]).read_bytes(),
            file_name=Path(result["csv"]).name,
            mime="text/csv",
            use_container_width=True,
            key="dl_csv",
        )

    st.markdown("##### お客様への定型文")
    st.code(
        "Excelの「review」シートは、読み取りや型変換で確認が必要だった箇所です。\n"
        "空欄にしてごまかしていません。元PDFと突合してください。",
        language=None,
    )


def tab_help() -> None:
    st.subheader("使い方（最短）")
    st.markdown(
        """
1. **案件** … お客様名でフォルダ作成  
2. **PDF** … アップロード → チェック（文字が選べるか）  
3. **列設定** … 依頼どおりの列名を保存  
4. **抽出** … 表プレビューを確認  
5. **納品** … 成果物作成 → Excel/CSVダウンロード → 目視  

くわしくは `docs/beginner_runbook.md` を見てください。
        """
    )
    st.markdown("##### 色の意図")
    st.write("暗い背景＋ほぼ白の文字で読みやすくしています。アクセントはミント系で、競馬ソフトの緑黒とは分けています。")


def main() -> None:
    _ensure_state()
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    render_brand()
    render_job_strip()

    tabs = st.tabs(["案件", "PDF", "列設定", "抽出", "納品", "ヘルプ"])
    with tabs[0]:
        tab_job()
    with tabs[1]:
        tab_pdf()
    with tabs[2]:
        tab_columns()
    with tabs[3]:
        tab_extract()
    with tabs[4]:
        tab_deliver()
    with tabs[5]:
        tab_help()


main()
