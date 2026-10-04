"""放射線科 勤務表 自動作成・管理アプリ (Streamlit)。 起動: streamlit run app.py"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import db_manager as db
import exporter
import scheduler as sc

st.set_page_config(page_title="放射線科 勤務表", page_icon="🩻", layout="wide")
db.init_db()

RED = "background-color:#FF4B4B;color:white;font-weight:bold"


def _stretch() -> dict:
    """Streamlit のバージョン差(use_container_width → width="stretch")を吸収する。"""
    try:
        major, minor = (int(x) for x in st.__version__.split(".")[:2])
    except ValueError:
        return {"use_container_width": True}
    return {"width": "stretch"} if (major, minor) >= (1, 49) else {"use_container_width": True}


STRETCH = _stretch()


# ------------------------------------------------------------------ データ読み込み
def load_input(year: int, month: int) -> sc.ScheduleInput:
    ym = db.ym_str(year, month)
    staff_df = db.get_staff()
    staff = staff_df.to_dict("records")
    shifts = {r["code"]: r for r in db.get_shift_types().to_dict("records")}
    reqs = {}
    for r in db.get_requirements().itertuples():
        mx = None if pd.isna(r.max_count) else int(r.max_count)
        reqs[(r.day_type, r.shift_code)] = (int(r.min_count), mx)
    rules = db.get_rules()
    special = {}
    for r in db.get_special_days().itertuples():
        special[dt.date.fromisoformat(r.date)] = (r.name, bool(r.is_holiday))
    cal = sc.build_calendar(year, month, special, rules)
    target = db.get_monthly_holidays(ym)
    if target is None:  # 未設定なら 土日祝の日数 を既定値とする
        target = sum(1 for d in cal if d.weekday >= 5 or d.is_holiday)
    return sc.ScheduleInput(year, month, staff, shifts, reqs, rules, target,
                            db.get_requests(year, month), db.get_prev_tail(year, month), cal)


def col_labels(inp: sc.ScheduleInput) -> list[str]:
    return [f"{d.day}({sc.WEEKDAY_JA[d.weekday]}{'祝' if d.is_holiday and d.weekday != 6 else ''})" for d in inp.calendar]


def roster_to_df(inp: sc.ScheduleInput, roster: dict[int, dict[int, str]]) -> pd.DataFrame:
    rows = [[roster.get(s["id"], {}).get(d, "") for d in range(1, inp.n_days + 1)] for s in inp.staff]
    return pd.DataFrame(rows, index=[s["name"] for s in inp.staff], columns=col_labels(inp))


def df_to_roster(inp: sc.ScheduleInput, df: pd.DataFrame) -> dict[int, dict[int, str]]:
    out = {}
    for i, s in enumerate(inp.staff):
        out[s["id"]] = {d: ("" if pd.isna(v := df.iat[i, d - 1]) else str(v)) for d in range(1, inp.n_days + 1)}
    return out


# ------------------------------------------------------------------ 表示用スタイル
def style_roster(df: pd.DataFrame, inp: sc.ScheduleInput, vio_cells: set) -> "pd.io.formats.style.Styler":
    def fn(data):
        out = pd.DataFrame("", index=data.index, columns=data.columns)
        for i, s in enumerate(inp.staff):
            for d in range(1, inp.n_days + 1):
                code = data.iat[i, d - 1]
                color = inp.shifts.get(code, {}).get("color", "")
                css = f"background-color:{color};color:#000" if color and color.upper() != "#FFFFFF" else "color:#000"
                if (s["id"], d) in vio_cells:
                    css = RED
                out.iat[i, d - 1] = css
        return out
    return df.style.apply(fn, axis=None)


def daily_counts(inp: sc.ScheduleInput, roster) -> pd.DataFrame:
    rows = {inp.name_of(c): [sum(1 for s in inp.staff if roster.get(s["id"], {}).get(d.day) == c)
                              for d in inp.calendar] for c in sc.COUNTED_CODES}
    return pd.DataFrame(rows, index=col_labels(inp)).T


def style_counts(df: pd.DataFrame, inp: sc.ScheduleInput):
    def fn(data):
        out = pd.DataFrame("", index=data.index, columns=data.columns)
        for r, code in enumerate(sc.COUNTED_CODES):
            for c, di in enumerate(inp.calendar):
                mn, mx = inp.req(di.day_type, code)
                v = data.iat[r, c]
                if v < mn or (mx is not None and v > mx):
                    out.iat[r, c] = RED
        return out
    return df.style.apply(fn, axis=None)


def style_summary(df: pd.DataFrame):
    return df.style.apply(lambda d: pd.DataFrame(
        [[RED if (c == "公休" and r["公休"] != r["規定公休"]) else "" for c in d.columns] for _, r in d.iterrows()],
        index=d.index, columns=d.columns), axis=None)


# ------------------------------------------------------------------ ページ: 勤務表
def page_roster(year: int, month: int) -> None:
    inp = load_input(year, month)
    ym = db.ym_str(year, month)
    st.header(f"📅 勤務表  {year}年{month}月")
    if not inp.staff:
        st.warning("スタッフが未登録です。「マスタ設定」→「スタッフ」で登録してください。")
        return

    base_key, ver_key, res_key = f"base_{ym}", f"ver_{ym}", f"result_{ym}"
    if base_key not in st.session_state:
        st.session_state[base_key] = db.get_roster(year, month)
        st.session_state[ver_key] = 0
    st.caption(
        f"規定公休: {inp.target_holidays}日 / 連続勤務の上限: {inp.rules.get('max_consecutive_days', 6)}日 / "
        f"祝日: {', '.join(f'{d.day}日({d.holiday_name})' for d in inp.calendar if d.is_holiday) or 'なし'} / "
        f"第3日曜: {next((str(d.day) + '日' for d in inp.calendar if d.is_third_sun), '-')}")

    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 2])
    with c5:
        time_limit = st.slider("計算の制限時間(秒)", 10, 300, 30, step=10)
    if c1.button("⚙ 自動生成", type="primary"):
        with st.spinner("最適化計算中…（制限時間まで最大数十秒かかります）"):
            res = sc.solve(inp, time_limit)
        st.session_state[res_key] = res
        if res.roster:
            st.session_state[base_key] = res.roster
            st.session_state[ver_key] += 1
        st.rerun()
    if c2.button("🔄 保存済みを読込"):
        st.session_state[base_key] = db.get_roster(year, month)
        st.session_state[ver_key] += 1
        st.session_state.pop(res_key, None)
        st.rerun()
    if c3.button("🧹 空にする"):
        st.session_state[base_key] = {}
        st.session_state[ver_key] += 1
        st.session_state.pop(res_key, None)
        st.rerun()

    res = st.session_state.get(res_key)
    if res:
        for w in res.warnings:
            st.warning("事前チェック: " + w)
        if res.status in ("optimal", "feasible"):
            st.success(res.message)
        elif res.status == "relaxed":
            st.error(res.message)
            with st.expander("競合している制約(原因候補)", expanded=True):
                for c in res.conflicts:
                    st.write("・" + c)
        else:
            st.error(res.message)

    status_box = st.container()

    # 編集グリッド(未入力セルには登録済みの希望休等を初期表示)
    roster0 = {sid: dict(days) for sid, days in st.session_state[base_key].items()}
    for (sid, d), code in inp.requests.items():
        roster0.setdefault(sid, {}).setdefault(d, code)
    codes = [c for c in inp.shifts]
    st.subheader("勤務表(セルを直接変更できます)")
    edited = st.data_editor(
        roster_to_df(inp, roster0), key=f"ed_{ym}_{st.session_state[ver_key]}",
        column_config={lbl: st.column_config.SelectboxColumn(lbl, options=codes, width=55) for lbl in col_labels(inp)},
        **STRETCH)
    roster = df_to_roster(inp, edited)

    vios = sc.check_roster(inp, roster)
    vio_cells = {(sid, d) for v in vios for sid, d in v.cells if sid is not None and d is not None}
    with status_box:
        if vios:
            st.error(f"制約違反が {len(vios)} 件あります(下の表で赤色表示)")
            with st.expander("違反の詳細", expanded=False):
                for v in vios:
                    st.write("・" + v.message)
        elif any(roster[s["id"]].get(1) for s in inp.staff):
            st.success("すべての制約を満たしています")

    if c4.button("💾 保存"):
        db.save_roster(year, month, roster)
        st.session_state[base_key] = roster
        st.success("保存しました")

    st.subheader("チェック表示(赤 = 制約違反)")
    st.dataframe(style_roster(roster_to_df(inp, roster), inp, vio_cells), **STRETCH)
    st.caption("凡例: " + " / ".join(f"{c}={v['name']}" for c, v in inp.shifts.items()))
    st.subheader("日別人数(赤 = 必要人数の過不足)")
    st.dataframe(style_counts(daily_counts(inp, roster), inp), **STRETCH)
    st.subheader("個人別集計")
    st.dataframe(style_summary(pd.DataFrame(sc.roster_summary(inp, roster)).set_index("技師")), **STRETCH)


# ------------------------------------------------------------------ ページ: 希望休・個別予定
def page_requests(year: int, month: int) -> None:
    inp = load_input(year, month)
    ym = db.ym_str(year, month)
    st.header(f"🙋 希望休・個別予定  {year}年{month}月")
    if not inp.staff:
        st.warning("スタッフが未登録です。")
        return
    req_codes = [c for c, v in inp.shifts.items() if v["is_request"]]
    st.caption("事前に決まっている予定を入力します。自動生成時にこの内容は固定されます。 "
               "選択肢: " + " / ".join(f"{c}={inp.name_of(c)}" for c in req_codes))
    rows = [[inp.requests.get((s["id"], d), "") for d in range(1, inp.n_days + 1)] for s in inp.staff]
    base = pd.DataFrame(rows, index=[s["name"] for s in inp.staff], columns=col_labels(inp))
    edited = st.data_editor(
        base, key=f"req_{ym}",
        column_config={l: st.column_config.SelectboxColumn(l, options=req_codes, width=55) for l in col_labels(inp)},
        **STRETCH)
    if st.button("💾 保存", type="primary"):
        reqs = {}
        for i, s in enumerate(inp.staff):
            for d in range(1, inp.n_days + 1):
                v = edited.iat[i, d - 1]
                if isinstance(v, str) and v:
                    reqs[(s["id"], d)] = v
        db.save_requests(year, month, reqs)
        st.success(f"{len(reqs)} 件保存しました。勤務表を再生成すると反映されます。")
    summary = pd.DataFrame({"希望休等の件数": [sum(1 for v in edited.iloc[i] if isinstance(v, str) and v)
                                          for i in range(len(inp.staff))]}, index=edited.index)
    st.dataframe(summary.T, **STRETCH)


# ------------------------------------------------------------------ ページ: マスタ設定
def page_master(year: int, month: int) -> None:
    st.header("⚙ マスタ設定")
    t_staff, t_shift, t_req, t_rule, t_month, t_special = st.tabs(
        ["スタッフ", "シフト種別", "必要人数", "ルール", "月別公休数", "特別日(祝日)"])

    with t_staff:
        df = db.get_staff(active_only=False)
        if df.empty and st.button("サンプルスタッフ12名を登録"):
            db.add_sample_staff()
            st.rerun()
        st.caption("行の追加/削除ができます(表の下端で追加、行を選択して Delete で削除)。表示順が勤務表の並び順になります。"
                   "PB担当者は「早番可」も必要です(PB翌日は早番のため)。「公休調整」は個人別の公休日数の加減(例: 非常勤 -2)。")
        edited = st.data_editor(
            df, num_rows="dynamic", key="staff_ed", hide_index=True, **STRETCH,
            column_config={
                "id": None, "sort_order": None,
                "name": st.column_config.TextColumn("氏名", required=True),
                "employment": st.column_config.TextColumn("雇用形態"),
                "can_pb": st.column_config.CheckboxColumn("PB可"),
                "can_early": st.column_config.CheckboxColumn("早番可"),
                "can_ha": st.column_config.CheckboxColumn("ハ番可"),
                "holiday_adjust": st.column_config.NumberColumn("公休調整", step=1),
                "active": st.column_config.CheckboxColumn("有効"),
            })
        if st.button("💾 スタッフを保存", type="primary"):
            try:
                db.save_staff(edited)
                st.success("保存しました")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with t_shift:
        st.caption(f"基本シフト({', '.join(db.CORE_CODES)})は略称の変更・削除ができません。"
                   "独自のシフト(例: 年休)は行追加で登録でき、希望休入力と手動編集で使えます。"
                   "「公休扱い」=月間公休日数にカウントし連続勤務を途切れさせます。「予定入力用」=希望休入力画面の選択肢に出ます。")
        edited = st.data_editor(
            db.get_shift_types(), num_rows="dynamic", key="shift_ed", hide_index=True, **STRETCH,
            column_config={
                "code": st.column_config.TextColumn("略称", required=True),
                "name": st.column_config.TextColumn("名称"),
                "start_time": st.column_config.TextColumn("始業時間"),
                "unit": st.column_config.SelectboxColumn("カウント単位", options=["全日", "半日", "休"]),
                "is_off": st.column_config.CheckboxColumn("公休扱い"),
                "is_request": st.column_config.CheckboxColumn("予定入力用"),
                "auto_assign": st.column_config.CheckboxColumn("自動配置可"),
                "color": st.column_config.TextColumn("色(#RRGGBB)"),
                "sort_order": None,
            })
        if st.button("💾 シフト種別を保存", type="primary"):
            try:
                db.save_shift_types(edited)
                st.success("保存しました")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with t_req:
        st.caption("曜日・祝日・第3日曜ごとの各シフト必要人数。最大が空欄=上限なし。"
                   "優先順位: 第3日曜(特別) > 祝日(日曜以外) > 曜日。")
        cur = {(r.day_type, r.shift_code): (r.min_count, r.max_count) for r in db.get_requirements().itertuples()}
        keys = [(t, c) for t in db.DAY_TYPES for c in sc.COUNTED_CODES]
        view = pd.DataFrame({
            "区分": [db.DAY_TYPE_LABELS[t] for t, _ in keys],
            "シフト": [c for _, c in keys],
            "最小": [int(cur.get(k, (0, None))[0]) for k in keys],
            "最大(空=上限なし)": [None if pd.isna(cur.get(k, (0, None))[1]) else int(cur[k][1]) for k in keys],
        })
        edited = st.data_editor(view, hide_index=True, key="req_ed", disabled=["区分", "シフト"], height=600,
                                column_config={"最小": st.column_config.NumberColumn(min_value=0, step=1),
                                               "最大(空=上限なし)": st.column_config.NumberColumn(min_value=0, step=1)},
                                **STRETCH)
        if st.button("💾 必要人数を保存", type="primary"):
            out = pd.DataFrame({
                "day_type": [t for t, _ in keys], "shift_code": [c for _, c in keys],
                "min_count": edited["最小"].fillna(0).astype(int), "max_count": edited["最大(空=上限なし)"]})
            db.save_requirements(out)
            st.success("保存しました")

    with t_rule:
        rules = db.get_rules_df()
        new = {}
        for r in rules.itertuples():
            if r.key == "max_consecutive_days":
                new[r.key] = st.number_input(r.description, 1, 31, int(r.value), key=f"rule_{r.key}")
            else:
                new[r.key] = int(st.checkbox(r.description, bool(r.value), key=f"rule_{r.key}"))
        if st.button("💾 ルールを保存", type="primary"):
            for k, v in new.items():
                db.set_rule(k, v)
            st.success("保存しました")

    with t_month:
        ym = db.ym_str(year, month)
        inp = load_input(year, month)
        saved = db.get_monthly_holidays(ym)
        st.write(f"**{year}年{month}月** の規定公休日数（未設定の場合は土日祝の日数 {inp.target_holidays} 日を使用）")
        val = st.number_input("公休日数", 0, 31, int(inp.target_holidays), key=f"mh_{ym}")
        if st.button("💾 この月の公休日数を保存", type="primary"):
            db.set_monthly_holidays(ym, int(val))
            st.success("保存しました")
            st.rerun()
        if saved is None:
            st.info("この月は未設定(既定値を使用中)です。")
        st.dataframe(db.get_all_monthly_holidays().rename(columns={"ym": "年月", "holidays": "公休日数"}), hide_index=True)

    with t_special:
        st.caption("年末年始など、ライブラリの祝日に無い休診日を追加できます。「祝日扱い」のチェックを外すと、"
                   "その日を祝日として扱わなくなります(祝日の自動判定は jpholiday を使用)。")
        sd = db.get_special_days()
        sd["date"] = pd.to_datetime(sd["date"])
        edited = st.data_editor(sd, num_rows="dynamic", key="sp_ed", hide_index=True, **STRETCH, column_config={
            "date": st.column_config.DateColumn("日付", required=True),
            "name": st.column_config.TextColumn("名称"),
            "is_holiday": st.column_config.CheckboxColumn("祝日扱い", default=True)})
        if st.button("💾 特別日を保存", type="primary"):
            db.save_special_days(edited)
            st.success("保存しました")


# ------------------------------------------------------------------ ページ: 出力
def page_export(year: int, month: int) -> None:
    inp = load_input(year, month)
    st.header(f"📤 Excel / PDF 出力  {year}年{month}月")
    if not db.roster_exists(year, month):
        st.info("保存済みの勤務表がありません。「勤務表」ページで作成し、保存してください。")
        return
    roster = db.get_roster(year, month)
    vios = sc.check_roster(inp, roster)
    if vios:
        st.warning(f"制約違反が {len(vios)} 件残っています(出力は可能です)。")
    c1, c2 = st.columns(2)
    c1.download_button("📊 Excel (.xlsx) をダウンロード", exporter.export_excel(inp, roster),
                       file_name=f"勤務表_{year}{month:02d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button("🖨 印刷用 PDF をダウンロード", exporter.export_pdf(inp, roster),
                       file_name=f"勤務表_{year}{month:02d}.pdf", mime="application/pdf")
    st.caption("どちらも A4 横 1 ページに収まる設定です。Excel は「ファイル→印刷」でそのまま印刷できます。")
    st.dataframe(style_roster(roster_to_df(inp, roster), inp, set()), **STRETCH)


# ------------------------------------------------------------------ main
def main() -> None:
    today = dt.date.today()
    nxt = (today.replace(day=1) + dt.timedelta(days=32)).replace(day=1)  # 既定は翌月
    with st.sidebar:
        st.title("🩻 放射線科 勤務表")
        year = st.number_input("年", 2020, 2100, nxt.year, step=1)
        month = st.selectbox("月", list(range(1, 13)), index=nxt.month - 1)
        page = st.radio("メニュー", ["勤務表", "希望休・個別予定", "マスタ設定", "Excel/PDF出力"])
        st.caption("データは duty_roster.db に保存されます(バックアップはこのファイルをコピー)。")
    year, month = int(year), int(month)
    {"勤務表": page_roster, "希望休・個別予定": page_requests,
     "マスタ設定": page_master, "Excel/PDF出力": page_export}[page](year, month)


main()
