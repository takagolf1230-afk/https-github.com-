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
    page_title="PDF表→Excel 作業画面",
    page_icon="📄",
    layout="wide",
)

STEPS = ["① 案件", "② PDF確認", "③ 列の設定", "④ 抽出プレビュー", "⑤ 納品"]


def _ensure_state() -> None:
    st.session_state.setdefault("job_name", "")
    st.session_state.setdefault("step", 0)


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


def render_sidebar() -> None:
    st.sidebar.title("PDF表→Excel")
    st.sidebar.caption("ココナラ受注用・素人向け作業画面")
    st.sidebar.markdown("---")
    for i, label in enumerate(STEPS):
        mark = "▶" if i == st.session_state.step else "○"
        st.sidebar.write(f"{mark} {label}")
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "困ったら `docs/beginner_runbook.md` を開いてください。"
    )


def step_job() -> None:
    st.header("① 案件を用意する")
    st.write("受注したら、まず案件フォルダを作ります。")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("新しい案件")
        name = st.text_input("お客様名や案件名", placeholder="例: tanaka / 請求明細A")
        if st.button("案件フォルダを作る", type="primary", use_container_width=True):
            if not name.strip():
                st.error("名前を入力してください")
            else:
                try:
                    folder = service.create_job(name.strip())
                    st.session_state.job_name = folder.name
                    st.success(f"作りました: {folder.name}")
                    st.session_state.step = 1
                    st.rerun()
                except FileExistsError as exc:
                    st.error(str(exc))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"作成に失敗しました: {exc}")

    with col2:
        st.subheader("既存の案件を開く")
        options = _job_options()
        if not options:
            st.info("まだ案件がありません。左で新規作成してください。")
            return
        selected = st.selectbox("案件フォルダ", options, index=0)
        if st.button("この案件で進む", use_container_width=True):
            st.session_state.job_name = selected
            st.session_state.step = 1
            st.rerun()


def step_pdf() -> None:
    job = _current_job()
    if job is None:
        st.warning("先に案件を選んでください")
        if st.button("①へ戻る"):
            st.session_state.step = 0
            st.rerun()
        return

    st.header("② PDFを入れて確認する")
    st.caption(f"案件: `{job.name}`")

    uploaded = st.file_uploader("お客様のPDFをアップロード", type=["pdf"])
    if uploaded is not None:
        saved = service.save_uploaded_pdf(job, uploaded.name, uploaded.getvalue())
        st.success(f"保存しました: {saved.name}")

    try:
        pdf = service.find_pdf(job)
        st.write(f"現在のPDF: **{pdf.name}**")
    except FileNotFoundError:
        st.warning("まだPDFがありません。上からアップロードしてください。")
        return

    if st.button("PDFをチェックする", type="primary"):
        result = service.check_job(job)
        st.metric("ページ数", result["pages"])
        if result["selectable"]:
            st.success(result["messages"][0])
        else:
            st.error(result["messages"][0])
        for msg in result["messages"][1:]:
            st.warning(msg)
        st.session_state["last_check"] = result

    cols = st.columns(2)
    with cols[0]:
        if st.button("← 戻る"):
            st.session_state.step = 0
            st.rerun()
    with cols[1]:
        if st.button("次へ：列の設定 →", type="primary", use_container_width=True):
            st.session_state.step = 2
            st.rerun()


def step_columns() -> None:
    job = _current_job()
    if job is None:
        st.warning("先に案件を選んでください")
        return

    st.header("③ 依頼された列を設定する")
    st.write("お客様が欲しい列名を `納品名` に、PDF側の見出し候補を `PDFの見出し` に書きます。")

    data = service.load_columns_yaml(job)
    pages_val = data.get("pages")
    pages_text = "" if pages_val in (None, "null") else ",".join(str(p) for p in pages_val)
    pages_text = st.text_input(
        "対象ページ（例: 1,2,3 / 空欄=全部）",
        value=pages_text,
        help="基本料金は5ページまで",
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
        column_config={
            "種類": st.column_config.SelectboxColumn(
                options=["text", "number", "date"],
                required=True,
            )
        },
    )

    if st.button("列設定を保存", type="primary"):
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
        pages: list[int] | None
        if pages_text.strip():
            try:
                pages = [int(p.strip()) for p in pages_text.split(",") if p.strip()]
            except ValueError:
                st.error("ページは数字をカンマ区切りで入力してください")
                return
        else:
            pages = None
        service.save_columns_yaml(job, {"pages": pages, "columns": new_cols})
        st.success("保存しました")

    cols = st.columns(2)
    with cols[0]:
        if st.button("← 戻る"):
            st.session_state.step = 1
            st.rerun()
    with cols[1]:
        if st.button("次へ：抽出プレビュー →", type="primary", use_container_width=True):
            st.session_state.step = 3
            st.rerun()


def step_extract() -> None:
    job = _current_job()
    if job is None:
        st.warning("先に案件を選んでください")
        return

    st.header("④ 表を抜き出して確認する")
    if st.button("抽出する", type="primary"):
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
    if result:
        st.subheader("見つかった表一覧")
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
            )

    cols = st.columns(2)
    with cols[0]:
        if st.button("← 戻る"):
            st.session_state.step = 2
            st.rerun()
    with cols[1]:
        if st.button("次へ：納品作成 →", type="primary", use_container_width=True):
            st.session_state.step = 4
            st.rerun()


def step_deliver() -> None:
    job = _current_job()
    if job is None:
        st.warning("先に案件を選んでください")
        return

    st.header("⑤ 納品ファイルを作る")
    st.info("作ったあと、必ず先頭・末尾と金額を元PDFと目視で突合してください。")

    if st.button("成果物をつくる", type="primary"):
        try:
            result = service.deliver_job(job)
            st.session_state["deliver_result"] = result
            st.success(f"作成完了: {result['rows']}行 / 要確認 {result['review_rows']}件")
        except Exception as exc:  # noqa: BLE001
            st.error(f"作成に失敗しました: {exc}")

    result = st.session_state.get("deliver_result")
    if result:
        st.subheader("data（納品本体）")
        show = result["data"].drop(columns=[c for c in result["data"].columns if str(c).startswith("_")], errors="ignore")
        st.dataframe(show, use_container_width=True)
        st.subheader("review（要確認）")
        st.dataframe(result["review"], use_container_width=True)
        st.subheader("log（作業メモ）")
        st.dataframe(result["log"], use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Excelをダウンロード",
                data=Path(result["xlsx"]).read_bytes(),
                file_name=Path(result["xlsx"]).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "CSVをダウンロード",
                data=Path(result["csv"]).read_bytes(),
                file_name=Path(result["csv"]).name,
                mime="text/csv",
                use_container_width=True,
            )

        st.markdown("### お客様への定型文")
        st.code(
            "Excelの「review」シートは、読み取りや型変換で確認が必要だった箇所です。\n"
            "空欄にしてごまかしていません。元PDFと突合してください。",
            language=None,
        )

    if st.button("← 戻る"):
        st.session_state.step = 3
        st.rerun()


def main() -> None:
    _ensure_state()
    render_sidebar()
    step = st.session_state.step
    if step == 0:
        step_job()
    elif step == 1:
        step_pdf()
    elif step == 2:
        step_columns()
    elif step == 3:
        step_extract()
    else:
        step_deliver()


main()
