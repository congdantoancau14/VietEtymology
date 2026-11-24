#!/usr/bin/env python3
"""
trich_thanh_ngu.py - trích danh sách ĐẦU MỤC từ PDF "Từ điển thành ngữ & tục ngữ Việt Nam" (2 cột, đầu mục nằm sát lề trái).

Chạy:  python trich_thanh_ngu.py tu-dien-thanh-ngu.pdf [trang_dau] [trang_cuoi]
Ra:    thanhngu-dau-muc.txt   (mỗi dòng một đầu mục; đưa tệp này vào phan_loai.py, tên tệp phải bắt đầu bằng "thanhngu")

Cần poppler (lệnh pdftotext). Chỉ rút các câu đầu mục để đối chiếu, không rút phần giải nghĩa.
Lưu ý bản quyền: từ điển này là tác phẩm có bản quyền; chỉ dùng danh sách đầu mục cục bộ để đối chiếu, đừng công bố lại.
"""
import html, re, subprocess, sys


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def page_entries(pdf, p):
    x = run("pdftotext", "-bbox-layout", "-f", str(p), "-l", str(p), pdf, "-")
    w = float(re.search(r'<page width="([\d.]+)"', x).group(1)) if '<page width=' in x else 1000
    lines = []
    for m in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">(.*?)</line>', x, re.S):
        txt = " ".join(html.unescape(t) for t in re.findall(r">([^<>]+)</word>", m.group(3)))
        lines.append((float(m.group(1)), float(m.group(2)), txt))
    out = []
    for col in (lambda l: l[0] < w / 2, lambda l: l[0] >= w / 2):
        L = sorted((l for l in lines if col(l) and not re.search(r"Từ điển thành ngữ|Vũ Dung|Vũ Thuý|Vũ Quang", l[2])), key=lambda l: l[1])
        if not L: continue
        xs = sorted(l[0] for l in L); left = xs[max(0, len(xs) // 10)]
        cur = None
        for xm, ym, t in L:
            if xm <= left + 4:
                if cur: out.append(cur)
                cur = t
            elif cur: cur += " " + t
        if cur: out.append(cur)
    return out


def headwords(entry):
    m = re.match(r"^(.+?)(?:\. |\.$|[?!] |\? |$)", entry)
    h = m.group(1) if m else entry
    h = re.sub(r"\s*[(\[].*$", "", h).strip(" ,;:\"“”'")
    out = [x.strip(" ,;:\"“”'") for x in h.split(";")]
    for v in re.findall(r"\[([^\]]+?)\.?\]", entry[:200]): out.append(v.strip(" ,;:\"“”'."))
    return [x for x in out if 3 <= len(x.split()) <= 12 and not re.search(r"\d|từ điển|ừ điển", x, re.I)]


def main(pdf, first=1, last=None, out="thanhngu-dau-muc.txt"):
    last = last or int(re.search(r"Pages:\s+(\d+)", run("pdfinfo", pdf)).group(1))
    seen = set()
    for p in range(first, last + 1):
        for e in page_entries(pdf, p):
            for h in headwords(e): seen.add(h.lower())
        if p % 50 == 0: print("trang", p, "- đầu mục:", len(seen), flush=True)
    open(out, "w", encoding="utf8").write("\n".join(sorted(seen)))
    print("Xong:", len(seen), "đầu mục ->", out)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1, int(sys.argv[3]) if len(sys.argv) > 3 else None)
