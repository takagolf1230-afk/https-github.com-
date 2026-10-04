"""勤務表の自動生成(数理最適化: PuLP/CBC)と制約チェック。

DB には依存しない。app.py が db_manager から ScheduleInput を組み立てて渡す。
solve()        : 月間勤務表の自動生成。解なしの場合は制約を緩和して競合箇所を報告する。
check_roster() : 手動調整後の勤務表の制約違反チェック(GUI の赤字警告で使用)。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pulp

try:  # 祝日判定(オフライン動作。未導入なら特別日マスタのみ)
    import jpholiday
except ImportError:  # pragma: no cover
    jpholiday = None

CODE_DAY, CODE_PB, CODE_EARLY, CODE_HA = "日", "PB", "早", "ハ"
CODE_HALF, CODE_OFF, CODE_REQ_OFF = "半", "休", "希"
COUNTED_CODES = [CODE_PB, CODE_EARLY, CODE_HA, CODE_DAY]  # 必要人数マスタで管理するシフト
WEEKDAY_JA = "月火水木金土日"
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# 目的関数の重み(ソフト制約)
W_PB_SPREAD = 10      # PB回数の公平化
W_WEEKEND_SPREAD = 5  # 土日祝勤務回数の公平化
W_HA_SPREAD = 3       # ハ番回数の公平化
W_EARLY_SPREAD = 2    # 早番回数の公平化
W_WEEKDAY_LEVEL = 2   # 平日の出勤人数の平準化
W_LONG_RUN = 1        # 上限ちょうどの連続勤務を避ける
W_EXCESS_OFF = 100    # 規定より多く休ませない
BIG_M = 1000          # 緩和モードで制約違反1単位あたりのペナルティ


@dataclass
class DayInfo:
    day: int
    date: dt.date
    weekday: int
    is_holiday: bool
    holiday_name: str
    is_third_sun: bool
    day_type: str  # 必要人数マスタのキー

    @property
    def label(self) -> str:
        return f"{self.date.month}/{self.day}({WEEKDAY_JA[self.weekday]})"


@dataclass
class ScheduleInput:
    year: int
    month: int
    staff: list[dict]                      # id,name,can_pb,can_early,can_ha,holiday_adjust
    shifts: dict[str, dict]                # code -> {name,unit,is_off,color,...}
    reqs: dict[tuple[str, str], tuple[int, int | None]]  # (day_type, code) -> (min, max)
    rules: dict[str, int]
    target_holidays: int
    requests: dict[tuple[int, int], str] = field(default_factory=dict)  # (staff_id, day) -> code
    prev: dict[int, dict[int, str]] = field(default_factory=dict)       # staff_id -> {k: code}
    calendar: list[DayInfo] = field(default_factory=list)

    @property
    def n_days(self) -> int:
        return len(self.calendar)

    def is_off(self, code: str) -> bool:
        if code in self.shifts:
            return bool(self.shifts[code]["is_off"])
        return code in (CODE_OFF, CODE_REQ_OFF)

    def unit(self, code: str) -> float:
        u = self.shifts.get(code, {}).get("unit", "全日")
        return {"全日": 1.0, "半日": 0.5, "休": 0.0}.get(u, 1.0)

    def name_of(self, code: str) -> str:
        return self.shifts.get(code, {}).get("name", code)

    def req(self, day_type: str, code: str) -> tuple[int, int | None]:
        return self.reqs.get((day_type, code), (0, None))

    def prev_last_weekday(self) -> int:
        return (dt.date(self.year, self.month, 1) - dt.timedelta(days=1)).weekday()

    def next_code_after_pb(self, pb_weekday: int) -> str | None:
        """PB 翌日に必要なシフト。土曜PB→半休(優先)、それ以外→早番。"""
        if pb_weekday == 5 and self.rules.get("sat_pb_next_half", 1):
            return CODE_HALF
        if self.rules.get("pb_next_early", 1):
            return CODE_EARLY
        return None


@dataclass
class Violation:
    kind: str
    message: str
    cells: list[tuple[int | None, int | None]] = field(default_factory=list)  # (staff_id, day) None=行/列全体


@dataclass
class ScheduleResult:
    status: str  # "optimal" / "feasible" / "relaxed" / "error"
    roster: dict[int, dict[int, str]] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""


# ------------------------------------------------------------------ calendar
def build_calendar(year: int, month: int, special_days: dict[dt.date, tuple[str, bool]] | None = None,
                   rules: dict[str, int] | None = None) -> list[DayInfo]:
    """special_days: {date: (名称, 祝日扱いか)}。False は祝日扱いの解除。"""
    special_days = special_days or {}
    rules = rules or {}
    ndays = (dt.date(year + (month == 12), month % 12 + 1, 1) - dt.date(year, month, 1)).days
    out = []
    for d in range(1, ndays + 1):
        date = dt.date(year, month, d)
        name = jpholiday.is_holiday_name(date) if jpholiday else None
        is_hol = bool(name)
        if date in special_days:
            sname, flag = special_days[date]
            is_hol, name = flag, (sname or name or "")
        wd = date.weekday()
        third = wd == 6 and 15 <= d <= 21
        if third and rules.get("third_sunday_enabled", 1):
            dtype = "third_sun"
        elif is_hol and wd != 6 and rules.get("holiday_rule_enabled", 1):
            dtype = "holiday"  # 日曜の祝日は日曜ルールを適用
        else:
            dtype = WEEKDAY_KEYS[wd]
        out.append(DayInfo(d, date, wd, is_hol, name or "", third, dtype))
    return out


# ------------------------------------------------------------------ validation
def _allowed_by_staff(s: dict, code: str) -> bool:
    return not ((code == CODE_PB and not s["can_pb"]) or (code == CODE_EARLY and not s["can_early"])
                or (code == CODE_HA and not s["can_ha"]))


def check_roster(inp: ScheduleInput, roster: dict[int, dict[int, str]]) -> list[Violation]:
    vios: list[Violation] = []
    n = inp.n_days
    max_run = int(inp.rules.get("max_consecutive_days", 6))
    for s in inp.staff:
        sid, name = s["id"], s["name"]
        r = roster.get(sid, {})
        prev = inp.prev.get(sid, {})
        # 未入力・不明コード・資格・希望休の遵守
        for d in range(1, n + 1):
            c = r.get(d, "")
            if not c:
                vios.append(Violation("empty", f"{name} {inp.calendar[d-1].label}: 未入力", [(sid, d)]))
                continue
            if c not in inp.shifts:
                vios.append(Violation("unknown", f"{name} {inp.calendar[d-1].label}: 未定義のシフト「{c}」", [(sid, d)]))
            if not _allowed_by_staff(s, c):
                vios.append(Violation("qualify", f"{name} {inp.calendar[d-1].label}: {inp.name_of(c)}の対応可否が「不可」です", [(sid, d)]))
            req = inp.requests.get((sid, d))
            if req and req != c:
                vios.append(Violation("request", f"{name} {inp.calendar[d-1].label}: 登録済みの「{inp.name_of(req)}」が守られていません", [(sid, d)]))
        # PB 翌日ルール
        for d in range(1, n + 1):
            if r.get(d) != CODE_PB:
                continue
            want = inp.next_code_after_pb(inp.calendar[d - 1].weekday)
            if want and d < n and r.get(d + 1) != want:
                vios.append(Violation(
                    "pb_next",
                    f"{name} {inp.calendar[d-1].label}のPB翌日は「{inp.name_of(want)}」にしてください(現在: {inp.name_of(r.get(d+1, '')) or '未入力'})",
                    [(sid, d), (sid, d + 1)]))
        if prev.get(1) == CODE_PB:
            want = inp.next_code_after_pb(inp.prev_last_weekday())
            if want and r.get(1) != want:
                vios.append(Violation("pb_next", f"{name} 前月末日がPBのため{inp.calendar[0].label}は「{inp.name_of(want)}」が必要です", [(sid, 1)]))
        # 連続勤務
        run = 0
        k = 7
        while k >= 1:
            run = run + 1 if (k in prev and not inp.is_off(prev[k])) else 0
            k -= 1
        flagged: list[tuple[int | None, int | None]] = []
        for d in range(1, n + 2):
            c = r.get(d, "") if d <= n else ""
            if d <= n and c and not inp.is_off(c):
                run += 1
                if run > max_run:
                    flagged.append((sid, d))
            else:
                if flagged:
                    vios.append(Violation("streak", f"{name}: {inp.calendar[flagged[0][1]-1].label}から連続{max_run+1}日以上勤務", list(flagged)))
                    flagged = []
                run = 0
        # 月間公休日数
        off = sum(1 for d in range(1, n + 1) if r.get(d) and inp.is_off(r[d]))
        target = inp.target_holidays + int(s.get("holiday_adjust", 0))
        if off != target:
            vios.append(Violation("holidays", f"{name}: 公休日数が{off}日(規定{target}日)", [(sid, None)]))
    # 日別必要人数
    for di in inp.calendar:
        for code in COUNTED_CODES:
            cnt = sum(1 for s in inp.staff if roster.get(s["id"], {}).get(di.day) == code)
            mn, mx = inp.req(di.day_type, code)
            if cnt < mn or (mx is not None and cnt > mx):
                rng = f"{mn}名" if mx == mn else (f"{mn}名以上" if mx is None else f"{mn}〜{mx}名")
                vios.append(Violation("daily", f"{di.label} {inp.name_of(code)}: {cnt}名(必要 {rng})", [(None, di.day)]))
    return vios


def roster_summary(inp: ScheduleInput, roster: dict[int, dict[int, str]]) -> list[dict]:
    rows = []
    n = inp.n_days
    for s in inp.staff:
        r = roster.get(s["id"], {})
        codes = [r.get(d, "") for d in range(1, n + 1)]
        cnt = lambda c: sum(1 for x in codes if x == c)  # noqa: E731
        rows.append({
            "技師": s["name"],
            "公休": sum(1 for x in codes if x and inp.is_off(x)),
            "規定公休": inp.target_holidays + int(s.get("holiday_adjust", 0)),
            "PB": cnt(CODE_PB), "早番": cnt(CODE_EARLY), "ハ番": cnt(CODE_HA), "半休": cnt(CODE_HALF),
            "土日祝勤務": sum(1 for di in inp.calendar if (di.weekday >= 5 or di.is_holiday)
                         and r.get(di.day) and not inp.is_off(r[di.day])),
            "出勤日数": sum(inp.unit(x) for x in codes if x),
        })
    return rows


def precheck(inp: ScheduleInput) -> list[str]:
    """ソルバー実行前の簡易チェック(明らかな不整合を早期に警告)。"""
    warns = []
    if not inp.staff:
        return ["スタッフが登録されていません"]
    for code, flag, label in ((CODE_PB, "can_pb", "PB"), (CODE_EARLY, "can_early", "早番"), (CODE_HA, "can_ha", "ハ番")):
        need = max((inp.req(di.day_type, code)[0] for di in inp.calendar), default=0)
        have = sum(1 for s in inp.staff if s[flag])
        if need > have:
            warns.append(f"{label}の1日最大必要人数({need}名)に対し、対応可能なスタッフが{have}名しかいません")
    cap_total = 0
    need_total = 0
    for di in inp.calendar:
        avail = sum(1 for s in inp.staff if not inp.is_off(inp.requests.get((s["id"], di.day), "")))
        need = sum(inp.req(di.day_type, c)[0] for c in COUNTED_CODES)
        need_total += need
        if need > avail:
            warns.append(f"{di.label}: 必要人数の合計{need}名に対し、出勤可能なスタッフが{avail}名です")
    for s in inp.staff:
        cap_total += inp.n_days - (inp.target_holidays + int(s.get("holiday_adjust", 0)))
    if need_total > cap_total:
        warns.append(f"月間の必要延べ人数({need_total})が、規定公休後の出勤可能延べ人数({cap_total})を超えています")
    return warns


# ------------------------------------------------------------------ optimisation
def _build(inp: ScheduleInput, relax: bool):
    n = inp.n_days
    cal = inp.calendar
    prob = pulp.LpProblem("roster", pulp.LpMinimize)
    ZERO = pulp.LpVariable("ZERO", 0, 0)
    ONE = pulp.LpVariable("ONE", 1, 1)
    obj: list = []
    slacks: list[tuple[pulp.LpVariable, str]] = []
    x: dict[tuple[int, int, str], pulp.LpVariable] = {}
    fixed: dict[tuple[int, int], str] = {}
    sat_half = bool(inp.rules.get("sat_pb_next_half", 1))

    def half_allowed(s: dict, d: int) -> bool:
        if not s["can_pb"]:
            return False
        if inp.shifts.get(CODE_HALF, {}).get("auto_assign"):
            return True
        if not sat_half:
            return False
        wd_prev = cal[d - 2].weekday if d > 1 else inp.prev_last_weekday()
        return wd_prev == 5

    for s in inp.staff:
        sid = s["id"]
        for d in range(1, n + 1):
            req = inp.requests.get((sid, d))
            if req:
                fixed[(sid, d)] = req
                continue
            allowed = [CODE_DAY, CODE_OFF]
            if s["can_pb"]:
                allowed.append(CODE_PB)
            if s["can_early"]:
                allowed.append(CODE_EARLY)
            if s["can_ha"]:
                allowed.append(CODE_HA)
            if half_allowed(s, d):
                allowed.append(CODE_HALF)
            for c in allowed:
                x[(sid, d, c)] = pulp.LpVariable(f"x_{sid}_{d}_{allowed.index(c)}", cat="Binary")
            prob += pulp.lpSum(x[(sid, d, c)] for c in allowed) == 1, f"one_{sid}_{d}"

    def v(sid, d, c):
        if (sid, d) in fixed:
            return ONE if fixed[(sid, d)] == c else ZERO
        return x.get((sid, d, c), ZERO)

    def off(sid, d):
        if (sid, d) in fixed:
            return ONE if inp.is_off(fixed[(sid, d)]) else ZERO
        return x[(sid, d, CODE_OFF)]

    def work(sid, d):
        return 1 - off(sid, d)

    def add(expr, sense: str, rhs, desc: str):
        if not relax:
            prob.addConstraint({"<=": expr <= rhs, ">=": expr >= rhs, "==": expr == rhs}[sense])
            return
        if sense in ("<=", "=="):
            sv = pulp.LpVariable(f"sl_{len(slacks)}", 0)
            prob.addConstraint(expr - sv <= rhs)
            slacks.append((sv, desc))
            obj.append(BIG_M * sv)
        if sense in (">=", "=="):
            sv = pulp.LpVariable(f"sl_{len(slacks)}", 0)
            prob.addConstraint(expr + sv >= rhs)
            slacks.append((sv, desc))
            obj.append(BIG_M * sv)

    sids = [s["id"] for s in inp.staff]

    # 1) 日別必要人数
    for di in cal:
        for c in COUNTED_CODES:
            mn, mx = inp.req(di.day_type, c)
            cnt = pulp.lpSum(v(sid, di.day, c) for sid in sids)
            if mn > 0:
                add(cnt, ">=", mn, f"{di.label} {inp.name_of(c)}が{mn}名以上必要(人数・資格・希望休・PB翌日ルールとの競合)")
            if mx is not None:
                add(cnt, "<=", mx, f"{di.label} {inp.name_of(c)}が{mx}名以下になる必要(人数・他ルールとの競合)")

    # 2) PB 翌日ルール(前月末PBの引き継ぎ含む)
    for s in inp.staff:
        sid = s["id"]
        for d in range(1, n):
            want = inp.next_code_after_pb(cal[d - 1].weekday)
            if want and (sid, d, CODE_PB) in x:
                add(v(sid, d, CODE_PB) - v(sid, d + 1, want), "<=", 0,
                    f"{s['name']} {cal[d-1].label}のPB → 翌日{inp.name_of(want)}にできない(希望休・資格等と競合)")
        if inp.prev.get(sid, {}).get(1) == CODE_PB:
            want = inp.next_code_after_pb(inp.prev_last_weekday())
            if want:
                add(v(sid, 1, want), ">=", 1, f"{s['name']} 前月末PBのため1日は{inp.name_of(want)}が必要(希望休等と競合)")

    # 3) 連続勤務上限(前月末からの連続含む)
    L = int(inp.rules.get("max_consecutive_days", 6))
    for s in inp.staff:
        sid = s["id"]
        for i in range(1 - L, n - L + 1):
            terms = []
            for j in range(i, i + L + 1):
                if j >= 1:
                    terms.append(work(sid, j))
                else:
                    pc = inp.prev.get(sid, {}).get(1 - j)
                    terms.append(ONE if (pc and not inp.is_off(pc)) else ZERO)
            first = max(i, 1)
            add(pulp.lpSum(terms), "<=", L, f"{s['name']} {cal[first-1].label}付近で連続{L+1}日勤務を避けられない")

    # 4) 月間公休日数(希望休を含めて規定数。超過はペナルティ)
    for s in inp.staff:
        sid = s["id"]
        target = inp.target_holidays + int(s.get("holiday_adjust", 0))
        tot = pulp.lpSum(off(sid, d) for d in range(1, n + 1))
        add(tot, ">=", target, f"{s['name']} 公休{target}日を確保できない(希望休・必要人数との競合)")
        ex = pulp.LpVariable(f"excess_{sid}", 0)
        prob.addConstraint(ex >= tot - target)
        obj.append(W_EXCESS_OFF * ex)

    # --- ソフト制約 ---
    def spread(exprs: dict[int, pulp.LpAffineExpression], weight: int, name: str, ids: list[int]):
        if len(ids) < 2:
            return
        hi = pulp.LpVariable(f"hi_{name}", 0)
        lo = pulp.LpVariable(f"lo_{name}", 0)
        for sid in ids:
            prob.addConstraint(hi >= exprs[sid])
            prob.addConstraint(lo <= exprs[sid])
        obj.append(weight * (hi - lo))

    pb_ids = [s["id"] for s in inp.staff if s["can_pb"]]
    spread({sid: pulp.lpSum(v(sid, d, CODE_PB) for d in range(1, n + 1)) for sid in pb_ids}, W_PB_SPREAD, "pb", pb_ids)
    ha_ids = [s["id"] for s in inp.staff if s["can_ha"]]
    spread({sid: pulp.lpSum(v(sid, d, CODE_HA) for d in range(1, n + 1)) for sid in ha_ids}, W_HA_SPREAD, "ha", ha_ids)
    ea_ids = [s["id"] for s in inp.staff if s["can_early"]]
    spread({sid: pulp.lpSum(v(sid, d, CODE_EARLY) for d in range(1, n + 1)) for sid in ea_ids}, W_EARLY_SPREAD, "ea", ea_ids)
    wk_days = [di.day for di in cal if di.weekday >= 5 or di.is_holiday]
    if wk_days:
        spread({sid: pulp.lpSum(work(sid, d) for d in wk_days) for sid in sids}, W_WEEKEND_SPREAD, "wk", sids)
    wd_days = [di.day for di in cal if di.weekday < 5 and not di.is_holiday]
    if wd_days:
        zw = pulp.LpVariable("z_weekday", 0)
        for d in wd_days:
            prob.addConstraint(zw >= pulp.lpSum(work(sid, d) for sid in sids))
        obj.append(W_WEEKDAY_LEVEL * zw)
    if L >= 2:  # 上限ちょうどの連勤(L日連続)を避ける
        for s in inp.staff:
            sid = s["id"]
            for i in range(1, n - L + 2):
                y = pulp.LpVariable(f"run_{sid}_{i}", 0, 1)
                prob.addConstraint(y >= pulp.lpSum(work(sid, j) for j in range(i, i + L)) - (L - 1))
                obj.append(W_LONG_RUN * y)

    prob += pulp.lpSum(obj)
    return prob, x, fixed, slacks


def _extract(inp: ScheduleInput, x, fixed) -> dict[int, dict[int, str]]:
    roster: dict[int, dict[int, str]] = {}
    for s in inp.staff:
        sid = s["id"]
        roster[sid] = {}
        for d in range(1, inp.n_days + 1):
            if (sid, d) in fixed:
                roster[sid][d] = fixed[(sid, d)]
                continue
            best = max(((c, var.value() or 0) for (i, dd, c), var in x.items() if i == sid and dd == d),
                       key=lambda t: t[1])
            roster[sid][d] = best[0]
    return roster


def _run(prob, time_limit: int, gap: float):
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=gap)
    prob.solve(solver)
    ok = prob.status == 1 or (prob.status == 0 and getattr(prob, "sol_status", 0) in (1, 2))
    return ok, prob.status


def solve(inp: ScheduleInput, time_limit: int = 30, gap: float = 0.05) -> ScheduleResult:
    warns = precheck(inp)
    if not inp.staff:
        return ScheduleResult("error", message="スタッフが登録されていません", warnings=warns)
    prob, x, fixed, _ = _build(inp, relax=False)
    ok, status = _run(prob, time_limit, gap)
    if ok:
        roster = _extract(inp, x, fixed)
        proven = getattr(prob, "sol_status", 1) == 1
        label = "optimal" if proven else "feasible"
        msg = "最適解を得ました" if proven else "ルールをすべて満たす解を生成しました(制限時間内の最良解。さらに公平化できる余地があります)"
        return ScheduleResult(label, roster, warnings=warns, message=msg)
    if status != -1:  # 不明(時間切れで解なし等)
        return ScheduleResult("error", warnings=warns,
                              message="制限時間内に解が見つかりませんでした。時間制限を延ばすか条件を見直してください")
    # 実行不可能 → 制約を緩和して競合箇所を特定
    prob2, x2, fixed2, slacks = _build(inp, relax=True)
    ok2, _ = _run(prob2, max(30, time_limit // 2), 0.05)
    if not ok2:
        return ScheduleResult("error", warnings=warns, message="制約の緩和でも解を得られませんでした")
    conflicts = sorted({desc for sv, desc in slacks if (sv.value() or 0) > 0.5})
    roster = _extract(inp, x2, fixed2)
    return ScheduleResult(
        "relaxed", roster, conflicts, warns,
        "ルールを同時に満たす解がありません。競合している制約を緩和した暫定案を表示します(赤字箇所を手動調整してください)")
