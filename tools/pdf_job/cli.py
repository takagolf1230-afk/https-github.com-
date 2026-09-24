"""CLI: new / check / extract / deliver — beginner PDF job pipeline."""

from __future__ import annotations

import argparse
import sys

from . import service


def cmd_new(args: argparse.Namespace) -> int:
    folder = service.create_job(args.name)
    print(f"案件フォルダを作りました: {folder}")
    print("次: 画面なら PDF をアップロード。コマンドなら 01_input/ にPDFを入れてください。")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    job = service.resolve_job(args.job)
    result = service.check_job(job)
    print(f"PDF: {result['pdf_name']}")
    print(f"ページ数: {result['pages']}")
    for i, msg in enumerate(result["messages"]):
        prefix = "判定" if i == 0 else "注意"
        print(f"{prefix}: {msg}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    job = service.resolve_job(args.job)
    result = service.extract_job(job)
    print(f"抽出プレビュー: {result['preview_path']}")
    print("Excelで index シートと各表を見て、列設定の source を合わせてください。")
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    job = service.resolve_job(args.job)
    result = service.deliver_job(job, stem=args.stem or "成果物")
    print(f"納品Excel: {result['xlsx']}")
    print(f"納品CSV : {result['csv']}")
    print(f"データ行数: {result['rows']} / 要確認: {result['review_rows']}")
    print("必ず data の先頭・末尾と金額合計を元PDFと目視で突合してから送ってください。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.pdf_job",
        description="ココナラ受注用: PDFの表を依頼列のExcel/CSVに整える道具",
    )
    sub = p.add_subparsers(dest="command", required=True)

    n = sub.add_parser("new", help="案件フォルダを作る")
    n.add_argument("--name", required=True, help="お客様名や案件名")
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("check", help="文字選択できるPDFか・ページ数を確認")
    c.add_argument("--job", required=True, help="jobs/ 配下のフォルダ名")
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("extract", help="表を抜き出してプレビューExcelを作る")
    e.add_argument("--job", required=True)
    e.set_defaults(func=cmd_extract)

    d = sub.add_parser("deliver", help="依頼列に揃えて納品xlsx/csvを作る")
    d.add_argument("--job", required=True)
    d.add_argument("--stem", default="成果物", help="出力ファイル名（拡張子なし）")
    d.set_defaults(func=cmd_deliver)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - beginner-facing CLI
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
