#!/usr/bin/env python3
"""
phan_loai.py - gán nhãn nguồn gốc tự động từ dump Wiktionary (định dạng JSONL, kiểu kaikki.org).

Chạy:  python phan_loai.py tep1.jsonl [tep2.jsonl ...] [Unihan_Readings.txt]
Ra:    entries.json (nạp vào trang tra từ), bao_cao.txt (thống kê, danh mục hay gặp, mục cần rà)

Tự nhận dạng từng dòng:
  - Wiktionary TIẾNG ANH (có etymology_templates): đầy đủ nhất, cho Vietic, Nam Á, từ vay, Hán Việt.
  - Wiktionary TIẾNG VIỆT (có etymology_texts + categories): cho Hán Việt, từ vay, từ ghép, từ láy.
Đưa cả hai tệp vào một lần chạy thì kết quả được gộp, nguồn nào có bằng chứng mạnh hơn thì thắng,
hai nguồn bất đồng thì gắn cờ cần rà. Chỉ dùng thư viện chuẩn. Dữ liệu Wiktionary: CC BY-SA.
Máy chỉ chuyển lại điều nguồn đã khẳng định, không tự suy đoán. Mức tin cậy tự động tối đa là 2
("Có khả năng"); 3 ("Chắc chắn") chỉ khi Wiktionary và Unihan kVietnamese cùng khớp (từ Hán Việt).
"""
import collections, itertools, json, os, re, sys, unicodedata

AA = {"km", "mnw", "kjg", "bdq", "cmo", "kdt", "sat", "pac", "kha", "bru", "sti", "ktv", "hre"}   # mã ngôn ngữ Nam Á (bản tiếng Anh); mở rộng nếu cần
AA_PREFIX = ("aav-", "mkh-pro")
LATE_ZH = {"yue", "nan", "hak", "cmn", "wuu", "cdo", "hsn", "gan"}
OLD_ZH = {"zh", "ltc", "och"}
TAI = {"th", "lo", "tts", "nod", "za", "pcc", "blt", "tyz", "shn"}
MALAY = {"cjm", "ms", "id", "jv", "km"}
EURO = {"fr", "en", "ru", "de", "es", "pt", "it", "la", "nl", "pl"}
SKIP_POS = {"name", "character", "romanization", "phrase", "proverb", "symbol", "hard-redirect"}
COMPOUND = {"compound", "com", "com+", "affix", "af", "af+"}
INH = {"inh", "inh+", "der", "der+"}
BORK = {"bor", "bor+", "lbor", "slb", "cal", "calque", "clq", "pclq"}
HANT = {"vi-etym-sino", "der", "bor", "cal", "calque"}   # mẫu có thể chứa chữ Hán gốc trong phần expansion
RX_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+")
VIETIC = {"mtq", "scb", "tou", "aem", "thm"}   # mã Wiktionary của Mường, Chứt; mở rộng nếu cần
HAN, MUON, TAYTHAI, CHAM, AU, KHAC = ("han", "Vay Hán (chưa rõ tầng)"), ("han", "Vay Hán muộn"), ("vay", "Tày–Thái"), \
    ("vay", "Chăm, Mã Lai, Khmer"), ("vay", "Châu Âu và khác"), ("vay", "Ngôn ngữ khác")
LANG_VI = {  # tên ngôn ngữ trong từ nguyên tiếng Việt -> (nhóm, nhãn con); mở rộng nếu cần
    **{k: HAN for k in ("Hán", "Trung Quốc", "Quan Thoại")},
    **{k: MUON for k in ("Quảng Đông", "Triều Châu", "Phúc Kiến", "Khách Gia", "Hẹ")},
    **{k: TAYTHAI for k in ("Thái", "Lào", "Tày", "Nùng")},
    **{k: CHAM for k in ("Chăm", "Khmer", "Mã Lai", "Indonesia", "Java")},
    **{k: AU for k in ("Anh", "Pháp", "Nga", "Đức", "Latinh", "Tây Ban Nha", "Bồ Đào Nha", "Ý", "Hà Lan", "Ba Lan", "Hy Lạp")},
    **{k: KHAC for k in ("Nhật", "Triều Tiên", "Hàn", "Ả Rập", "Ba Tư", "Phạn", "Hindi", "Thổ Nhĩ Kỳ", "Mông Cổ")},
    "Việt-Mường nguyên thủy": ("kt", "Việt–Mường"), "Môn-Khmer nguyên thủy": ("kt", "Nam Á"), "Nam Á nguyên thủy": ("kt", "Nam Á")}
LANG_L = {k.lower(): v for k, v in LANG_VI.items()}
RX_CAT = re.compile(r"^Từ (vay mượn|dẫn xuất|kế thừa) từ tiếng (.+) tiếng Việt$")
RX_BOR = re.compile(r"^(?:Từ|Mượn từ|Vay từ|Phiên âm từ|Phiên âm)\s+(?:tiếng\s+)?(" +
                    "|".join(re.escape(k) for k in sorted(LANG_VI, key=len, reverse=True)) + r")(?=[\s,:;.]|$)", re.I)
HVSYL = set()          # mọi âm Hán Việt trong Unihan (điền khi chạy)
ALIAS = {}            # từ Latin -> {"han": [...], "cjk": [...]} lấy từ các mục "Dạng chữ Hán/Nôm của X"
SKIPPED = collections.Counter()
RX_ALIAS = re.compile(r"^dạng (chữ hán|nôm) của (.+)$", re.I)
TONES = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}
ONS = sorted(["ngh", "ng", "nh", "ph", "th", "tr", "ch", "kh", "gh", "gi", "qu", "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "q", "r", "s", "t", "v", "x"], key=len, reverse=True)
SCORE = {"R1c": 4, "R1e": 4, "R1f": 4, "R4c": 1, "R2a": 6, "R2b": 6, "R1a+U": 6, "R1a": 5, "R1b": 5, "R2c": 4, "R2d": 3, "R2e": 2, "R2f": 6, "R3d": 4, "R3": 4, "R4a": 3, "R4b": 3, "R5": 2, "R5b": 1, "R0": 0}
STOP = {"the", "and", "for", "with", "one", "who", "that", "are", "was", "his", "her", "its", "used", "from", "into", "not",
        "of", "to", "or", "in", "as", "be", "an", "như", "của", "là", "một", "các", "có", "và", "để", "trong", "được",
        "những", "cái", "người", "thì", "với", "khi", "này", "đó", "nói", "chung", "hoặc", "cho", "không", "bị", "đã", "sẽ", "rất"}


def slug(w):
    s = unicodedata.normalize("NFD", w.lower().replace("đ", "d"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "muc"


def arg(t, k):
    return (t.get("args") or {}).get(k, "")


def new_r():
    return dict(g="cr", sub="Chưa xác định", conf=0, rule="R0", recon="", review=False, decomp=True,
                hvsyl=False, note="", dbl=[], cog=[])


def hv_ok(w, hv):
    return False   # khớp âm tiết với Unihan không phân biệt được đồng âm (ai, mặc...), nên không dùng làm bằng chứng


def all_hv(w):
    return bool(HVSYL) and all(unicodedata.normalize("NFC", x.lower()) in HVSYL for x in w.split())


def char_ok(w, han, hv):
    """Mỗi chữ Hán trong từ nguyên có âm Hán Việt (Unihan) đúng bằng âm tiết tương ứng của từ."""
    sy = [unicodedata.normalize("NFC", x.lower()) for x in w.split()]
    return any(len(run) == len(sy) and all(sy[i] in hv.get(run[i], ()) for i in range(len(sy))) for run in RX_HAN.findall(han or ""))


def split_syl(x):
    x = unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", x.lower()) if c not in TONES))
    for o in ONS:
        if x.startswith(o) and len(x) > len(o): return o, x[len(o):]
    return "", x


def is_lay(w):
    """Láy theo định nghĩa ngữ âm: hai âm tiết trùng âm đầu (c=k=q) hoặc trùng vần."""
    p = w.split()
    if len(p) != 2: return False
    (o1, r1), (o2, r2) = split_syl(p[0]), split_syl(p[1])
    eq = {"c": "k", "q": "k", "gh": "g", "ngh": "ng"}
    o1, o2 = eq.get(o1, o1), eq.get(o2, o2)
    return bool(o1 and o1 == o2) or r1 == r2


def load_cedict(path, hv):
    """CC-CEDICT: từ Hán nhiều chữ -> chuỗi âm Hán Việt có thể có (qua Unihan)."""
    ced, rx = {}, re.compile(r"^(\S+) (\S+) \[")
    for l in open(path, encoding="utf8"):
        m = rx.match(l)
        if l.startswith("#") or not m: continue
        for word in set(m.groups()):
            if len(word) < 2 or not all(c in hv for c in word): continue
            n = 1
            for c in word: n *= len(hv[c])
            if n > 32: continue
            for cb in itertools.product(*[sorted(hv[c]) for c in word]):
                ced.setdefault(" ".join(cb), word)
    return ced


def bor_label(c):
    if c in LATE_ZH: return "han", "Vay Hán muộn"
    if c in OLD_ZH: return "han", "Vay Hán (chưa rõ tầng)"
    if c in TAI or c.startswith(("tai-", "kra-", "tw-")): return "vay", "Tày–Thái"
    if c in MALAY: return "vay", "Chăm, Mã Lai, Khmer"
    if c.split("-")[0] in EURO: return "vay", "Châu Âu và khác"
    return "vay", "Ngôn ngữ khác"


def cog_str(t, links):
    """Đồng nguyên dạng 'Muong băl'. Mẫu cog có thể để trống từ ('-'); khi đó lấy từ etymology_links."""
    lang, term = t.get("expansion") or arg(t, "1"), arg(t, "2")
    if term in ("", "-"):
        term = next((a for a, b in links if b.endswith("#" + lang)), "")
    return f"{lang} {term}".strip()


def classify_en(e, w, hv):
    T = e.get("etymology_templates") or []
    txt = e.get("etymology_text") or ""
    names = [t.get("name") for t in T]
    r = new_r()
    links = e.get("etymology_links") or []
    r["cog"] = [cog_str(t, links) for t in T if t.get("name") == "cog" and arg(t, "1") != "vi"][:8]
    r["dbl"] = [arg(t, "2") for t in T if t.get("name") == "doublet" and arg(t, "2")]
    if "vi-etym-sino" in names:
        if "Non-Sino-Vietnamese" in txt:
            r.update(g="han", sub="Hán Việt cổ", conf=2, rule="R1b", review=True, decomp=False,
                     note="Wiktionary: đọc ngoài hệ Hán Việt chuẩn. Gán “Hán Việt cổ” theo quy ước dự án, cần người rà.")
        else:
            ok = hv_ok(w, hv)
            r.update(g="han", sub="Hán Việt", conf=3 if ok else 2, rule="R1a+U" if ok else "R1a", hvsyl=True,
                 note="Wiktionary và Unihan (kVietnamese) cùng xác nhận là âm Hán Việt." if ok else "Wiktionary ghi là âm Hán Việt; chưa có nguồn thứ hai để đối chiếu.")
        return r
    inh = [(arg(t, "2"), arg(t, "3")) for t in T if t.get("name") in INH and arg(t, "1") == "vi"]
    codes = {c for c, _ in inh} | {arg(t, "1") for t in T if t.get("name") == "cog"}
    is_aa = lambda c: c in AA or (c.startswith(("aav-", "mkh-")) and not c.startswith("mkh-vie"))
    vietic = [x for c, x in inh if c.startswith("mkh-vie")]
    pro_aa = [x for c, x in inh if is_aa(c)]
    if pro_aa:
        r.update(g="kt", sub="Nam Á", conf=2, rule="R2a", recon=pro_aa[0], decomp=False)
    elif vietic:
        if any(c in AA for c in codes):
            r.update(g="kt", sub="Nam Á", conf=2, rule="R2b", review=True, recon=vietic[0], decomp=False,
                     note="Có tái lập Vietic và đối ứng Nam Á ngoài Vietic; cần xác nhận không phải vay Khmer/Mon.")
        else:
            r.update(g="kt", sub="Vietic", conf=2, rule="R2b", recon=vietic[0], decomp=False)
    elif any(is_aa(c) for c in codes):
        r.update(g="kt", sub="Nam Á", conf=2, rule="R2c", review=True, decomp=False,
                 note="Chỉ có đối ứng Nam Á liệt kê; chưa có tái lập. Cần rà.")
    elif codes & VIETIC:
        sub = "Việt–Mường" if "mtq" in codes and not codes & (VIETIC - {"mtq"}) else "Vietic"
        r.update(g="kt", sub=sub, conf=2, rule="R2d", review=True, decomp=False,
                 note="Có đồng nguyên trong nhóm Vietic (theo Wiktionary), chưa thấy đối ứng ngoài nhóm. Cần rà: có thể là vay từ tiếng Việt sang Mường.")
    elif codes & TAI:
        r.update(g="vay", sub="Tày–Thái", conf=1, rule="R2e", review=True, decomp=False,
                 note="Có đồng nguyên Tày–Thái; hướng vay hoặc gốc chung chưa rõ. Cần rà.")
    else:
        for t in T:
            if (t.get("name") in BORK or (t.get("name") in ("der", "der+") and not arg(t, "2").endswith("-pro"))) and arg(t, "1") == "vi":
                g, sub = bor_label(arg(t, "2"))
                r.update(g=g, sub=sub, conf=2, rule="R3", decomp=False, review=g == "han",
                         note=("Calque từ " if "cal" in t.get("name") or "clq" in t.get("name") else "Vay từ ") + arg(t, "2") + (": " + arg(t, "3") if arg(t, "3") else ""))
                break
        else:
            if re.search(r"onomatopoe", txt, re.I):
                r.update(g="tt", sub="Tượng thanh", conf=2, rule="R4a", decomp=False)
            elif re.search(r"reduplicat", txt, re.I) or {"vi-etym-redup", "rdp"} & set(names):
                r.update(g="ns", sub="Từ láy", conf=2, rule="R4b", decomp=False)
            elif COMPOUND & set(names):
                if len(w.split()) > 1: r.update(g="ns", sub="Từ ghép", conf=2, rule="R5")
                else: r.update(g="ns", sub="Phụ tố cổ", conf=1, rule="R5b", review=True, decomp=False)
    return r


def classify_vi(e, w, hv):
    txt = " ".join(e.get("etymology_texts") or []).replace("__NOEDITSECTION__", "").strip()
    cj = " | ".join(e.get("categories") or []).lower()   # LƯU Ý: danh mục là của CẢ TRANG, không riêng mục này
    r, multi = new_r(), len(w.split()) > 1
    if re.search(r"âm hán[- ]việt|^phiên âm từ chữ hán", txt, re.I):        # bằng chứng của riêng mục này
        r.update(g="han", sub="Hán Việt", conf=2, rule="R1a", hvsyl=True, note="Wiktionary ghi là âm Hán Việt.")
        return r
    k = re.match(r"^\s*([^\W\d_]+)\s*:", txt)
    if multi and k and k.group(1).lower() in [x.lower() for x in w.split()] and all_hv(w):
        r.update(g="han", sub="Hán Việt", conf=2, rule="R1e", hvsyl=True,
                 note="Từ nguyên giải nghĩa từng thành tố; mọi âm tiết đều có âm Hán Việt trong Unihan.")
        return r
    for c in e.get("categories") or []:
        mc = RX_CAT.match(c)
        if mc:
            hit, unk = LANG_L.get(mc.group(2).strip().lower()), False
            if hit is None and mc.group(1) != "kế thừa": hit, unk = KHAC, True
            if hit:
                r.update(g=hit[0], sub=hit[1], conf=2, rule="R2f" if hit[0] == "kt" else "R3d", decomp=False,
                         review=hit[0] == "han" or unk or not multi, note="Wiktionary tiếng Việt (danh mục của trang): " + c)
                return r
    m = RX_BOR.match(txt)
    if m:
        g, sub = LANG_L[m.group(1).lower()]
        r.update(g=g, sub=sub, conf=2, rule="R2f" if g == "kt" else "R3", decomp=False, review=g == "han",
                 note="Vay từ " + m.group(1) + " (theo Wiktionary tiếng Việt).")
    elif "tượng thanh" in cj:
        r.update(g="tt", sub="Tượng thanh", conf=2, rule="R4a", decomp=False, review=not multi)
    elif "tượng hình" in cj:
        r.update(g="tt", sub="Tượng hình", conf=2, rule="R4a", decomp=False, review=not multi)
    elif "láy" in cj and multi:
        r.update(g="ns", sub="Từ láy", conf=2, rule="R4b", decomp=False)
    elif multi and "mục từ hán-việt" in cj and all_hv(w):
        r.update(g="han", sub="Hán Việt", conf=2, rule="R1c", hvsyl=True,
                 note="Trang có mục Hán Việt và mọi âm tiết đều có âm Hán Việt trong Unihan.")
    elif ("từ ghép" in cj or " + " in txt) and multi:
        r.update(g="ns", sub="Từ ghép", conf=2, rule="R5")
    return r


def classify(e, w, hv):
    return classify_vi(e, w, hv) if is_vi(e) else classify_en(e, w, hv)


def is_vi(e):
    return "etymology_texts" in e or e.get("lang") == "Tiếng Việt"


def gloss_tokens(e):
    return {t for s in e.get("senses", []) for g in s.get("glosses", [])
            for t in re.findall(r"[^\W\d_]+", g.lower()) if len(t) > 1 and t not in STOP}


def compositional(w, gl):
    """Xấp xỉ 'bẻ ra vẫn giữ nghĩa': nghĩa của từ ghép trùng ít nhất một từ khoá với một thành tố
    (nhà cửa ~ nhà). Thiếu dữ liệu nghĩa thì không bẻ: bẻ nhầm mất thông tin, giữ nhầm chỉ thêm việc."""
    ps = w.split()
    return bool(gl.get(w)) and all(gl.get(p) for p in ps) and any(gl[w] & gl[p] for p in ps)


def merge(a, b):
    hi, lo = (a, b) if SCORE[a["rule"]] >= SCORE[b["rule"]] else (b, a)
    if lo["rule"] != "R0" and (lo["g"], lo["sub"]) != (hi["g"], hi["sub"]):
        hi["review"] = True
        hi["note"] = (hi["note"] + " " if hi["note"] else "") + "Nguồn khác cho nhãn khác: " + lo["sub"] + "."
    for k in ("recon", "cog", "dbl"):
        if not hi[k] and lo[k]: hi[k] = lo[k]
    for k, v in lo["meta"].items():
        if not hi["meta"].get(k) and v: hi["meta"][k] = v
    return hi


def peek(e):
    g = ((e.get("senses") or [{}])[0].get("glosses") or [""])[0][:70]
    t = (e.get("etymology_text") or " ".join(e.get("etymology_texts") or [])).replace("\n", " ")[:90]
    c = ", ".join(x for x in (e.get("categories") or []) if isinstance(x, str) and not re.search(r"Mục từ|Trang có|Wiktionary cũ|bản dịch|tiếng Việt$", x))[:90]
    return g, t, c


def meta_of(e, r):
    """Thông tin phụ lấy từ dữ liệu: nghĩa gợi ý, phát âm Hà Nội, dạng viết CJK (Nôm/Hán), chữ Hán gốc từ từ nguyên."""
    S = (e.get("senses") or [{}])[0]
    gloss = ((S.get("glosses") or [""])[0])[:80]
    ipa = ""
    for sd in e.get("sounds") or []:
        if sd.get("ipa"):
            if "Hà-Nội" in (sd.get("tags") or []): ipa = sd["ipa"]; break
            ipa = ipa or sd["ipa"]
    cjk = [f["form"] for f in e.get("forms") or [] if RX_HAN.fullmatch(f.get("form", "")) and set(f.get("tags") or []) & {"CJK", "romanization"}]
    han = ""
    if r["g"] == "han":
        src = " ".join([e.get("etymology_text") or "", " ".join(e.get("etymology_texts") or [])]
                       + [l[0] for l in e.get("etymology_links") or [] if l]
                       + [t.get("expansion", "") for t in e.get("etymology_templates") or [] if t.get("name") in HANT])
        han = " ".join(dict.fromkeys(RX_HAN.findall(src)))
    return dict(gloss=gloss, ipa=ipa, cjk=cjk, han=han)


def read_file(path):
    seen, out, fmt, cats, tm = collections.defaultdict(list), {}, collections.Counter(), collections.Counter(), collections.Counter()
    for l in open(path, encoding="utf8"):
        try: e = json.loads(l)
        except ValueError: continue
        if e.get("lang_code") != "vi" or e.get("pos") in SKIP_POS or not e.get("word"): continue
        w0 = e["word"]
        if RX_HAN.fullmatch(w0):                       # mục viết bằng chữ Hán/Nôm: gắn vào từ Latin tương ứng
            mm = RX_ALIAS.match(((e.get("senses") or [{}])[0].get("glosses") or [""])[0].strip())
            if mm: ALIAS.setdefault(mm.group(2).strip().rstrip("."), {"han": [], "cjk": []})["han" if "hán" in mm.group(1).lower() else "cjk"].append(w0)
            SKIPPED["mục chữ Hán/Nôm"] += 1; continue
        if w0[:1].isupper() or w0.startswith("tiếng "):
            SKIPPED["tên riêng"] += 1; continue
        vi = is_vi(e)
        fmt["tiếng Việt" if vi else "tiếng Anh"] += 1
        if vi: cats.update(e.get("categories") or [])
        else:
            for t in e.get("etymology_templates") or []:
                nm = t.get("name"); lg = arg(t, "2") if nm in INH | BORK else arg(t, "1") if nm == "cog" else ""
                tm[nm + (" " + lg if lg else "")] += 1
        w = e["word"]
        if "etymology_number" in e:
            try: n = int(e["etymology_number"])
            except (TypeError, ValueError): n = 1
        else:
            t = " ".join(e.get("etymology_texts") or []) if vi else e.get("etymology_text", "")
            if t not in seen[w]: seen[w].append(t)
            n = seen[w].index(t) + 1
        out.setdefault((w, n), e)
    return out, fmt, cats, tm


def main(paths, unihan=None, cedict=None):
    hv = {}
    if unihan:
        for l in open(unihan, encoding="utf8"):
            p = l.rstrip("\n").split("\t")
            if len(p) == 3 and p[1] == "kVietnamese":
                hv.setdefault(chr(int(p[0][2:], 16)), set()).update(unicodedata.normalize("NFC", x.lower()) for x in p[2].split())
        HVSYL.update(x for v in hv.values() for x in v)
    CED = load_cedict(cedict, hv) if cedict and hv else {}
    per, gl, fmt, cats, tmpl = [], collections.defaultdict(set), collections.Counter(), collections.Counter(), collections.Counter()
    pk = {}
    for p in paths:
        d, f, c, tm = read_file(p)
        fmt.update(f); cats.update(c); tmpl.update(tm); per.append(d)
        for (w, n), e in d.items():
            gl[w] |= gloss_tokens(e); pk.setdefault((w, n), peek(e))
    cls = {}
    for d in per:
        for k, e in d.items():
            r = classify(e, k[0], hv)
            r["meta"] = meta_of(e, r)
            if r["rule"] == "R1a" and hv and char_ok(k[0], r["meta"]["han"], hv):
                r.update(conf=3, rule="R1a+U", note="Mỗi chữ Hán trong từ nguyên có âm Hán Việt khớp Unihan (kVietnamese).")
            cls[k] = merge(cls[k], r) if k in cls else r

    for k, r in cls.items():                           # gắn chữ Hán/Nôm từ các mục "Dạng chữ Hán/Nôm của X"
        a = ALIAS.get(k[0])
        if not a: continue
        m = r["meta"]
        for h in a["han"]:
            if h not in m["han"].split(): m["han"] = (m["han"] + " " + h).strip()
        for c in a["cjk"]:
            if c not in m["cjk"]: m["cjk"].append(c)
        if r["rule"] == "R0" and hv and char_ok(k[0], " ".join(a["han"] + a["cjk"]), hv):
            m["han"] = " ".join(a["han"] + a["cjk"])
            r.update(g="han", sub="Hán Việt", conf=3, rule="R1g", hvsyl=True,
                     note="Wiktionary có mục chữ Hán của từ này và mỗi chữ có âm Hán Việt khớp Unihan.")
    atoms, stubs = {}, collections.defaultdict(list)
    for (w, n), r in cls.items():
        if r["rule"] == "R0" and len(w.split()) > 1 and CED:
            key = " ".join(unicodedata.normalize("NFC", x.lower()) for x in w.split())
            if key in CED:
                r.update(g="han", sub="Hán Việt", conf=2, rule="R1f", hvsyl=True, note="Khớp từ Hán trong CC-CEDICT: " + CED[key])
                r["meta"]["han"] = r["meta"]["han"] or CED[key]
        if r["rule"] == "R0" and HVSYL and is_lay(w) and not all_hv(w):
            r.update(g="ns", sub="Từ láy", conf=1, rule="R4c", review=True, decomp=False,
                     note="Suy từ cấu trúc ngữ âm (trùng âm đầu hoặc vần), không phải Wiktionary khẳng định. Cần rà.")
        if len(w.split()) > 1:
            if r["decomp"] and compositional(w, gl):
                for s in w.split(): stubs[s].append((w, r))
                continue
            r["parts"] = w.split()
            if r["rule"] == "R0":
                r["note"] = "Có thể là từ ghép; nghĩa không suy ra trực tiếp từ thành tố nên giữ làm mục riêng."
        atoms[(w, n)] = r
    have = {w for w, _ in atoms}
    for s, lst in stubs.items():
        if s in have: continue
        hvall = all(r["hvsyl"] for _, r in lst)
        hz = []                                    # gán chữ Hán theo vị trí khi số chữ bằng số âm tiết
        for w0, r0 in lst:
            runs, sy = RX_HAN.findall(r0["meta"].get("han", "")), w0.split()
            if len(runs) == 1 and len(runs[0]) == len(sy):
                hz += [runs[0][i] for i, x in enumerate(sy) if x == s and runs[0][i] not in hz]
        atoms[(s, 1)] = dict(g="han" if hvall else "cr", sub="Hán Việt" if hvall else "Chưa xác định",
                             conf=2 if hvall else 0, rule="S1" if hvall else "S0", recon="", cog=[], dbl=[],
                             review=hvall, hvsyl=hvall, meta=dict(gloss="", ipa="", cjk=[], han=" ".join(hz) if hvall else ""), note="Tách từ: " + ", ".join(dict.fromkeys(w for w, _ in lst))[:120])
    out, used, first, todo_pk = [], set(), {}, []
    for (w, n) in sorted(atoms):
        r = atoms[(w, n)]
        base = slug(w); id_ = base; k = 1
        while id_ in used:
            k += 1; id_ = f"{base}-{k}"
        used.add(id_); first.setdefault(w, id_)
        d = {"id": id_, "w": w, "gloss": r["meta"]["gloss"], "han": r["meta"]["han"], "cjk": r["meta"]["cjk"], "ipa": r["meta"]["ipa"], "L": [[r["g"], r["sub"]]], "conf": r["conf"], "recon": r["recon"],
             "cog": "; ".join(r["cog"]), "doublets": r["dbl"], "note": r["note"],
             "src": "Wiktionary (kaikki.org), CC BY-SA", "rule": r["rule"], "review": r["review"], "parts": r.get("parts", [])}
        if r["g"] == "cr": d["todo"] = 1; todo_pk.append((w, pk.get((w, n))))
        out.append(d)
    for d in out:
        d["doublets"] = [first[x] for x in d["doublets"] if x in first]
        d["parts"] = [first[x] for x in d["parts"] if x in first]
    json.dump(out, open("entries.json", "w", encoding="utf8"), ensure_ascii=False)

    c = collections.Counter(d["L"][0][1] for d in out)
    todo = sum(1 for d in out if d.get("todo"))
    rep = [f"Tổng số mục: {len(out)}", f"Số dòng đọc được theo định dạng: {dict(fmt)}", f"Bỏ qua: {dict(SKIPPED)}", ""]
    if "tiếng Anh" not in fmt: rep += ["LƯU Ý: chưa có tệp Wiktionary TIẾNG ANH trong lần chạy này, nên thiếu Vietic/Nam Á và nhiều từ Hán Việt.", ""]
    if not hv: rep += ["LƯU Ý: chưa có Unihan_Readings.txt: tắt các quy tắc R1c, R1e, R1g, R4c và nâng bậc Chắc chắn.", ""]
    if not CED: rep += ["LƯU Ý: chưa có CC-CEDICT (tệp cedict_ts.u8): tắt quy tắc R1f.", ""] + [f"{k}: {v}" for k, v in c.most_common()]
    rep += ["", "Theo quy tắc: " + ", ".join(f"{k}={v}" for k, v in collections.Counter(d["rule"] for d in out).items()),
            f"Cần người rà: {sum(d['review'] for d in out)}", f"Chờ điền: {todo}"]
    multi = sum(1 for w, _ in todo_pk if " " in w)
    rep += [f"Trong số chờ điền: {multi} mục nhiều âm tiết (giữ nguyên vì không bẻ được), {todo - multi} mục một âm tiết."]
    if out and todo / len(out) > 0.5:
        rep += ["", "CẢNH BÁO: hơn một nửa số mục chưa có nhãn. Wiktionary tiếng Việt hiếm khi ghi gốc Vietic/Nam Á;",
                "hãy thêm tệp Wiktionary TIẾNG ANH (kaikki.org/dictionary/Vietnamese) vào cùng lần chạy."]
    if cats:
        rep += ["", "Danh mục hay gặp trong Wiktionary tiếng Việt (để bổ sung quy tắc):"] + [f"{n:>7}  {k}" for k, n in cats.most_common(80)]
    if tmpl:
        rep += ["", "Mẫu từ nguyên hay gặp trong Wiktionary tiếng Anh, kèm mã ngôn ngữ (để bổ sung quy tắc):"] + [f"{n:>7}  {k}" for k, n in tmpl.most_common(60)]
    open("bao_cao.txt", "w", encoding="utf8").write("\n".join(rep))
    import random; random.seed(1)
    with open("mau_chua_xac_dinh.txt", "w", encoding="utf8") as f:
        for w, pp in random.sample(todo_pk, min(150, len(todo_pk))): f.write(w + " | " + (" | ".join(pp) if pp else "") + "\n")
    print("\n".join(rep[:30]))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    miss = [x for x in a if not os.path.exists(x)]
    if miss: sys.exit("Không tìm thấy tệp: " + ", ".join(miss) + "\nKiểm tra tên tệp và thư mục đang đứng khi chạy lệnh.")
    uni = [x for x in a if os.path.basename(x).lower().startswith("unihan")]
    ced = [x for x in a if os.path.basename(x).lower().startswith("cedict")]
    main([x for x in a if x not in uni + ced], uni[0] if uni else None, ced[0] if ced else None)
