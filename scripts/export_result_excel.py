# -*- coding: utf-8 -*-
"""把连跑稳定性报告（.stability/stability_report.json）导出为 Excel。

用法：python export_result_excel.py
输出：reports/stability_result.xlsx
"""

import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from util.env import get_env  # noqa: E402

REPORT_JSON = os.path.join(ROOT, ".stability", "stability_report.json")
OUT_XLSX = os.path.join(ROOT, "reports", "stability_result.xlsx")


def status_fill(color):
    from openpyxl.styles import PatternFill
    return PatternFill("solid", fgColor=color)


def main():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side

    with open(REPORT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    wb = Workbook()
    thin = Side(style="thin", color="D0D3D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_font = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    ok_fill = status_fill("EAF3DE")
    bad_fill = status_fill("FCEBEB")
    mid_fill = status_fill("FAEEDA")

    # ---------- 表1：逐用例连跑结果 ----------
    ws = wb.active
    ws.title = "连跑结果"
    count = data["count"]
    headers = ["用例标识", "判定"] + ["第%d轮" % i for i in range(1, count + 1)] \
        + ["通过", "失败", "跳过", "失败分类", "建议"]
    ws.append(headers)
    for c in data["cases"]:
        row = [c["nodeid"], c["verdict"]] + c["statuses"] \
            + [c["passed"], c["failed"], c["skipped"], c.get("category", ""), c.get("advice", "")]
        ws.append(row)
    for row in ws.iter_rows(min_row=2):
        verdict = row[1].value
        fill = ok_fill if verdict == "STABLE" else (bad_fill if verdict in ("FLAKY", "BROKEN") else mid_fill)
        for cell in row:
            cell.border = border
            cell.alignment = center
        row[1].fill = fill
    for cell in ws[1]:
        cell.font = head_font
        cell.border = border
        cell.alignment = center
    widths = [58, 10] + [10] * count + [8, 8, 8, 14, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = w

    # ---------- 表2：轮次汇总 ----------
    ws2 = wb.create_sheet("轮次汇总")
    ws2.append(["轮次", "用例数", "通过", "失败", "跳过", "退出码", "结论"])
    for r in data["runs"]:
        verdict = "通过" if r["failed"] == 0 else "存在失败"
        ws2.append([r["index"], r["cases"], r["passed"], r["failed"], r["skipped"], r["returncode"], verdict])
    for row in ws2.iter_rows(min_row=2):
        for cell in row:
            cell.border = border
            cell.alignment = center
    for cell in ws2[1]:
        cell.font = head_font
        cell.border = border
        cell.alignment = center

    # ---------- 表3：验收信息 ----------
    ws3 = wb.create_sheet("验收信息")
    counts = data["counts"]
    passed = counts["flaky"] == 0 and counts["broken"] == 0
    info = [
        ["验收时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["目标", data["target"]],
        ["连跑次数", count],
        ["STABLE", counts["stable"]],
        ["FLAKY", counts["flaky"]],
        ["BROKEN", counts["broken"]],
        ["浏览器引擎", get_env("BROWSER_ENGINE")],
        ["被测地址", get_env("BASE_URL")],
        ["验收标准", "FLAKY=0 且 BROKEN=0"],
        ["验收结论", "通过" if passed else "未通过"],
    ]
    for row in info:
        ws3.append(row)
    for row in ws3.iter_rows():
        for cell in row:
            cell.border = border
    ws3.column_dimensions["A"].width = 16
    ws3.column_dimensions["B"].width = 44

    wb.save(OUT_XLSX)
    print("已输出：%s" % OUT_XLSX)


if __name__ == "__main__":
    main()
