#!/usr/bin/env python3
"""
sap_xep.py - xếp các tệp trong thư mục dự án vào cấu trúc thư mục có hệ thống.

Chạy ở thư mục gốc dự án (hoặc dùng --goc):
    python sap_xep.py                  # CHỈ XEM kế hoạch, chưa di chuyển gì
    python sap_xep.py --thuc-hien      # di chuyển thật
Không xoá tệp nào. Nếu nơi đến đã có tệp trùng tên thì giữ nguyên tệp nguồn và báo cho bạn.
Sau khi xếp xong, chạy:  python scripts/phan_loai.py
"""
import os, re, shutil, sys

RULES = [  # (mẫu trên tên tệp chữ thường, thư mục đích, ý nghĩa); mẫu đầu tiên khớp thì thắng
    (r"^sap_xep\.py$", "", "công cụ xếp tệp (giữ ở gốc)"),
    (r"^(phan_loai|trich_thanh_ngu)\.py$", "scripts", "mã chạy"),
    (r"\.jsonl$", "data/raw/wiktionary", "Wiktionary (đầu vào chính)"),
    (r"^(unihan|phienam|chinese-hanviet|ktraditionalvariant|cedict)", "data/raw/han_viet", "dữ liệu âm Hán Việt, chữ Hán"),
    (r"^sidwell", "data/raw/nam_a", "đồng nguyên Nam Á"),
    (r"^opensubs", "data/raw/tan_suat", "tần suất"),
    (r"^thanhngu-dau-muc", "data/derived", "danh sách đầu mục thành ngữ (sinh ra từ PDF)"),
    (r"thanh.?ngu|ca.?dao|tuc.?ngu", "data/raw/thanh_ngu", "nguồn thành ngữ, tục ngữ"),
    (r"^vietnamese-etymology", "data/raw/tham_khao", "chỉ tham khảo, không dùng làm đầu vào"),
    (r"^(entries\.json|bao_cao.*\.txt|mau_chua_xac_dinh.*\.txt|ung_vien_han_viet.*\.txt)$", "output", "kết quả chạy"),
    (r"\.html$", "web", "trang web đã tải về"),
    (r"^list_files", "khac", "tệp phụ"),
]
GIU_NGUYEN = {".gitignore", "readme.md", ".git"}
THU_MUC = ["scripts", "data/raw/wiktionary", "data/raw/han_viet", "data/raw/nam_a", "data/raw/tan_suat",
           "data/raw/thanh_ngu", "data/raw/tham_khao", "data/derived", "output", "web", "khac"]
NGUON = """# Nguồn dữ liệu

| Thư mục | Tệp | Vai trò | Giấy phép / ghi chú (cần tự kiểm tra) |
|---|---|---|---|
| data/raw/wiktionary | kaikki.org-dictionary-Vietnamese.jsonl | Wiktionary tiếng Anh, mục tiếng Việt, qua kaikki.org | CC BY-SA, phải ghi nguồn |
| data/raw/wiktionary | vi-extract.jsonl | Wiktionary tiếng Việt | CC BY-SA, phải ghi nguồn |
| data/raw/han_viet | Unihan_Readings.txt | âm đọc chữ Hán (kVietnamese lẫn cả âm chữ Nôm) | điều khoản của Unicode |
| data/raw/han_viet | cedict_ts.u8 | CC-CEDICT, từ điển Hán–Anh | CC BY-SA (kiểm tra phiên bản) |
| data/raw/han_viet | phienam.txt, chinese-hanviet-cognates.tsv, kTraditionalVariant.json | âm Hán Việt từng chữ, danh sách từ Hán Việt, giản–phồn | ghi rõ nguồn gốc từng tệp |
| data/raw/nam_a | Sidwell-Austroasiatic_phylogenetic-dataset-2015.xlsm | đồng nguyên Nam Á cho 200 nghĩa cơ bản | trích dẫn: Sidwell (2015) |
| data/raw/tan_suat | opensubs-freq.txt | tần suất từ trong phụ đề phim | kiểm tra điều khoản OpenSubtitles |
| data/raw/thanh_ngu | tudienthanhngu.pdf | từ điển thành ngữ, tục ngữ | CÓ BẢN QUYỀN: chỉ dùng cục bộ, không công bố |
| data/derived | thanhngu-dau-muc.txt | đầu mục trích từ PDF trên | không công bố |
| data/raw/tham_khao | vietnamese-etymology.pdf | tài liệu tham khảo | không dùng làm đầu vào |
"""


def plan(root):
    out = []
    for f in sorted(os.listdir(root)):
        p = os.path.join(root, f)
        if not os.path.isfile(p) or f.lower() in GIU_NGUYEN: continue
        for pat, dest, why in RULES:
            if re.search(pat, f.lower()): out.append((f, dest, why)); break
        else: out.append((f, None, "không nhận ra, giữ nguyên"))
    return out


def main(argv):
    root = os.getcwd()
    if "--goc" in argv: root = argv[argv.index("--goc") + 1]
    run = "--thuc-hien" in argv
    P = plan(root)
    print(f"Thư mục gốc: {root}\n{'THỰC HIỆN' if run else 'CHỈ XEM (thêm --thuc-hien để di chuyển)'}\n")
    for f, d, why in P:
        dest = "(giữ nguyên)" if d is None else ("(giữ ở gốc)" if d == "" else d + "/")
        print(f"  {f:62} -> {dest}   [{why}]")
    if not run: return
    for d in THU_MUC: os.makedirs(os.path.join(root, d), exist_ok=True)
    moved = clash = 0
    for f, d, _ in P:
        if not d: continue
        dst = os.path.join(root, d, f)
        if os.path.exists(dst): print("  TRÙNG, giữ nguyên:", f); clash += 1; continue
        shutil.move(os.path.join(root, f), dst); moved += 1
    nguon = os.path.join(root, "data", "NGUON_DU_LIEU.md")
    if not os.path.exists(nguon): open(nguon, "w", encoding="utf8").write(NGUON)
    print(f"\nĐã di chuyển {moved} tệp, {clash} tệp trùng. Đã tạo data/NGUON_DU_LIEU.md (nếu chưa có).")
    print("Gợi ý .gitignore (dữ liệu nguồn lớn và có bản quyền không nên đưa lên git):\n  data/raw/\n  data/derived/\n  output/")
    print("\nBước tiếp theo:  python scripts/phan_loai.py")


if __name__ == "__main__":
    main(sys.argv[1:])
