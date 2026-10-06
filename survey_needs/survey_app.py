"""医療職向けニーズ調査の回答分析アプリ。 起動: streamlit run survey_app.py"""
import io

import numpy as np
import pandas as pd
import streamlit as st

import analysis as an

st.set_page_config(page_title="ニーズ調査 分析", page_icon="📊", layout="wide")
st.title("📊 現場の雑務ニーズ調査 分析")
st.caption("Google フォーム等の回答CSVを読み込み、需要の大きい雑務・価格帯・購入意向を集計します。"
           "質問の作り方は questionnaire.md を参照してください。")

up = st.sidebar.file_uploader("回答CSV", type=["csv"])
use_sample = st.sidebar.checkbox("ダミーデータで試す", value=up is None)
if up is not None:
    raw = up.getvalue()
    for enc in ("utf-8-sig", "cp932"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=enc)
            break
        except UnicodeDecodeError:
            continue
elif use_sample:
    df = pd.read_csv("sample_responses.csv")
    st.info("表示中はダミーデータです(実際の回答ではありません)。")
else:
    st.stop()

cols = an.detect_columns(df)
burden, desire = an.grid_columns(df, "負担度"), an.grid_columns(df, "解決意欲")
st.sidebar.metric("回答数", len(df))
with st.sidebar.expander("列の割り当て(自動認識の確認)"):
    options = [None] + list(df.columns)
    for key in cols:
        cols[key] = st.selectbox(key, options, index=options.index(cols[key]) if cols[key] in options else 0, key=f"map_{key}")

t1, t2, t3, t4, t5 = st.tabs(["回答者", "需要の大きい雑務", "価格感度", "購入意向", "自由記述"])

with t1:
    for key, label in (("role", "職種"), ("experience", "経験年数"), ("facility", "施設種別"), ("authority", "購入の決定権")):
        if cols.get(key):
            st.subheader(label)
            st.bar_chart(an.counts(df[cols[key]]))

with t2:
    if cols.get("chore_pick") and (not burden or not desire):
        st.caption("簡易版: 負担が大きい雑務として選ばれた回数です(多いほど需要の大きい候補)。")
        picks = an.multi_choice_counts(df, cols["chore_pick"])
        st.dataframe(pd.DataFrame({"選択数": picks, "選択率(%)": (picks / len(df) * 100).round(1)}), width="stretch")
        st.bar_chart(picks)
        for gkey, glabel in (("position", "立場別(若手/中堅/管理職)"), ("role", "職種別")):
            if cols.get(gkey):
                st.subheader(f"{glabel}の選択率(%)")
                st.dataframe(an.pick_by_group(df, cols["chore_pick"], cols[gkey]), width="stretch")
    elif not burden or not desire:
        st.warning("「負担度」「解決意欲」のグリッド列、または「負担が大きい雑務」の列が見つかりません。")
    else:
        sc = an.chore_scores(df, burden, desire)
        st.caption("需要スコア = 平均負担度 × 平均解決意欲(最大25)。上位ほど「負担が大きく、お金を払ってでも解決したい」雑務です。")
        st.dataframe(sc, hide_index=True, width="stretch")
        st.bar_chart(sc.set_index("雑務")["需要スコア"])
        if cols.get("role"):
            st.subheader("職種別の解決意欲(平均)")
            min_n = st.slider("表示する最小回答数", 1, 30, 5)
            st.dataframe(an.chore_by_group(df, cols["role"], desire, min_n), width="stretch")
            st.caption("回答数が少ない職種は偏りが大きいので、参考程度に見てください。")

with t3:
    vw = an.van_westendorp(df, cols)
    if not vw and cols.get("price_band"):
        st.caption("簡易版: 「払ってもよい買い切り価格」の選択結果です。")
        pb = an.price_band_counts(df, cols["price_band"])
        st.dataframe(pb, width="stretch")
        st.bar_chart(pb["回答数"])
    elif not vw:
        st.warning("価格の4質問(安すぎて/安い/高い/高すぎて)の列が見つかりません。列の割り当てを確認してください。")
    elif "grid" not in vw:
        st.warning(f"有効な回答が少なすぎます(n={vw['n']})。")
    else:
        c = st.columns(4)
        for i, k in enumerate(["PMC(許容下限)", "OPP(最適価格)", "IPP(無差別価格)", "PME(許容上限)"]):
            c[i].metric(k, f"{vw[k]:,.0f}円" if not np.isnan(vw[k]) else "-")
        st.line_chart(pd.DataFrame(vw["curves"], index=vw["grid"].round(0)), x_label="価格(円)", y_label="累積割合")
        st.caption(f"有効回答 n={vw['n']}(価格の大小関係が矛盾する回答は除外)。"
                   "許容範囲は PMC〜PME。販売価格はこの範囲内で、OPP〜IPP付近を目安にします。"
                   "SNS回答は価格を低く答えがちなので、先行販売の申込みで検証してください。")

with t4:
    if cols.get("intent"):
        st.subheader("購入意向")
        st.dataframe(an.intent_summary(df, cols["intent"]), width="stretch")
        positive = df[cols["intent"]].astype(str).str.contains("ぜひ|条件次第")
        st.metric("購入に前向き(ぜひ+条件次第)", f"{positive.mean() * 100:.1f}%")
        if cols.get("role"):
            st.subheader("職種別: 前向きな割合(%)")
            g = positive.groupby(df[cols["role"]]).agg(["mean", "size"])
            g["mean"] = (g["mean"] * 100).round(1)
            st.dataframe(g.rename(columns={"mean": "前向き(%)", "size": "回答数"}), width="stretch")
    if cols.get("payer"):
        st.subheader("支払う人")
        st.bar_chart(an.counts(df[cols["payer"]]))
    if cols.get("form"):
        st.subheader("希望する提供形態(複数選択)")
        st.bar_chart(an.multi_choice_counts(df, cols["form"]))

with t5:
    for key, label in (("free_pain", "現場で困っていること"), ("free_wish", "あったらいいソフト・道具")):
        if cols.get(key):
            st.subheader(label)
            kw = st.text_input(f"{label}: 数えたいキーワード(カンマ区切り)", "勤務表,記録,申し送り,在庫,連絡", key=f"kw_{key}")
            st.dataframe(an.keyword_counts(df[cols[key]], [k.strip() for k in kw.split(",")]), hide_index=True)
            with st.expander("回答の一覧"):
                st.write(df[cols[key]].dropna().loc[lambda s: s.astype(str).str.strip() != ""].reset_index(drop=True))
