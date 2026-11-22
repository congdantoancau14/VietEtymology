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
SKIP_POS = {"name", "character", "romanization", "symbol", "hard-redirect"}
COMPOUND = {"compound", "com", "com+", "affix", "af", "af+", "prefix", "pre", "suffix", "suf", "confix", "con"}
INH = {"inh", "inh+", "der", "der+"}
BORK = {"bor", "bor+", "lbor", "slb", "cal", "calque", "clq", "pclq"}
HANT = {"vi-etym-sino", "der", "bor", "cal", "calque"}   # mẫu có thể chứa chữ Hán gốc trong phần expansion
RX_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]+")
VIETIC = {"mtq", "scb", "tou", "aem", "thm"}   # mã Wiktionary của Mường, Chứt; mở rộng nếu cần
HAN, MUON, TAYTHAI, CHAM, AU, KHAC = ("han", "Vay Hán (chưa rõ tầng)"), ("han", "Vay Hán muộn"), ("vay", "Tày–Thái"), \
    ("vay", "Chăm, Mã Lai, Khmer"), ("vay", "Châu Âu khác"), ("vay", "Ngôn ngữ khác")
PHAP, ANH, NGA, AN, NHK, CHUARO = ("vay", "Tiếng Pháp"), ("vay", "Tiếng Anh"), ("vay", "Tiếng Nga"), \
    ("vay", "Phạn, Pali, Ấn Độ"), ("vay", "Nhật, Triều Tiên"), ("vay", "Chưa rõ ngôn ngữ nguồn")
LANG_VI = {  # tên ngôn ngữ trong từ nguyên tiếng Việt -> (nhóm, nhãn con); mở rộng nếu cần
    **{k: HAN for k in ("Hán", "Hán thượng cổ", "Hán trung cổ", "Hán cổ", "Trung Quốc", "Quan Thoại")},
    **{k: MUON for k in ("Quảng Đông", "Triều Châu", "Phúc Kiến", "Khách Gia", "Hẹ")},
    **{k: TAYTHAI for k in ("Thái", "Lào", "Tày", "Nùng")},
    **{k: CHAM for k in ("Chăm", "Khmer", "Mã Lai", "Indonesia", "Java")},
    "Pháp": PHAP, "Anh": ANH, "Nga": NGA,
    **{k: AU for k in ("Đức", "Latinh", "Tây Ban Nha", "Bồ Đào Nha", "Ý", "Hà Lan", "Ba Lan", "Hy Lạp")},
    **{k: AN for k in ("Phạn", "Pali", "Hindi", "Tamil")},
    **{k: NHK for k in ("Nhật", "Triều Tiên", "Hàn")},
    **{k: KHAC for k in ("Ả Rập", "Ba Tư", "Thổ Nhĩ Kỳ", "Mông Cổ")},
    "Việt-Mường nguyên thủy": ("kt", "Việt–Mường"), "Môn-Khmer nguyên thủy": ("kt", "Nam Á"), "Nam Á nguyên thủy": ("kt", "Nam Á")}
LANG_L = {k.lower(): v for k, v in LANG_VI.items()}
RX_CAT = re.compile(r"^Từ (vay mượn|dẫn xuất|kế thừa) từ tiếng (.+) tiếng Việt$")
RX_BOR = re.compile(r"^(?:[Tt]ừ|[Mm]ượn từ|[Vv]ay từ|[Pp]hiên âm từ|[Pp]hiên âm)\s+(?:tiếng\s+)?(" +
                    "|".join(re.escape(k) for k in sorted(LANG_VI, key=len, reverse=True)) + r")(?=[\s,:;.]|$)")
HVSYL = set()          # mọi âm Hán Việt trong Unihan (điền khi chạy)
VARIANTS = collections.defaultdict(list)   # từ lemma -> các biến thể chính tả/phương ngữ
RX_VAR = [(re.compile(x, re.I), sb) for x, sb in (
    (r"^(?:common )?misspelling of (.+?)\.?$", "Sai chính tả"),
    (r"^traditional tone placement spelling of (.+?)\.?$", "Bỏ dấu kiểu cũ"),
    (r"^modern tone placement spelling of (.+?)\.?$", "Dạng viết khác"),
    (r"^(?:alternative|alternate|obsolete|dated|nonstandard)(?: letter-case)? (?:spelling|form|letter-case form|variant) of (.+?)(?: \(.*)?\.?$", "Dạng viết khác"),
    (r"^(?:central|northern|southern)[a-z ]* form of (.+?)(?: \(.*)?\.?$", "Phương ngữ"),
    (r"^dạng (?:nam việt nam|bắc việt nam|miền [^ ]+) của (.+?)\.?$", "Phương ngữ"),
    (r"^dạng viết khác của (.+?)\.?$", "Dạng viết khác"),
    (r"^(?:từ |dạng )?sai chính tả của (.+?)\.?$", "Sai chính tả"),
    (r"^censored spelling of (.+?)\.?$", "Dạng viết khác"),
    (r"^eye dialect spelling of ([^,]+?)(?:,.*)?\.?$", "Phương ngữ"),
    (r"^[a-z ]*vietnam[a-z ]* form of (.+?)(?: \(.*)?\.?$", "Phương ngữ"))]
VIET_HOA = {"gương": "鏡", "về": "回", "goá": "寡", "vẹn": "完", "cầu": "橋", "vợ": "婦", "giường": "床", "sức": "力",
            "đền": "殿", "cướp": "劫", "giống": "種", "trồng": "種", "giồng": "種", "thuê": "稅"}   # bảng tham chiếu từ Wikipedia tiếng Việt, cần đối chiếu nguồn học thuật
LANGNAME = {"fr": "Pháp", "en": "Anh", "ru": "Nga", "de": "Đức", "ja": "Nhật", "ko": "Triều Tiên", "zh": "Trung Quốc", "yue": "Quảng Đông",
            "cmn": "Quan thoại", "hak": "Khách Gia", "nan": "Mân Nam", "nan-hbl": "Mân Nam (Hokkien)", "nan-tws": "Triều Châu",
            "och": "Hán thượng cổ", "ltc": "Hán trung cổ giai đoạn cuối", "sa": "Phạn", "pi": "Pali", "hi": "Hindi", "la": "Latinh",
            "es": "Tây Ban Nha", "pt": "Bồ Đào Nha", "it": "Ý", "nl": "Hà Lan", "th": "Thái", "lo": "Lào", "km": "Khmer", "cjm": "Chăm",
            "ms": "Mã Lai", "id": "Indonesia", "mtq": "Mường", "ar": "Ả Rập", "fa": "Ba Tư", "tr": "Thổ Nhĩ Kỳ"}
ALIAS = {}            # từ Latin -> {"han": [...], "cjk": [...]} lấy từ các mục "Dạng chữ Hán/Nôm của X"
SKIPPED = collections.Counter()
RX_ALIAS = re.compile(r"^dạng (chữ hán|nôm) của (.+)$", re.I)
TONE_ID = {"\u0300": "1", "\u0301": "2", "\u0309": "3", "\u0303": "4", "\u0323": "5"}
TONES = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}
ONS = sorted(["ngh", "ng", "nh", "ph", "th", "tr", "ch", "kh", "gh", "gi", "qu", "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "q", "r", "s", "t", "v", "x"], key=len, reverse=True)
SCORE = {"R1h": 5, "R1k": 4, "R3f": 1, "R1i": 1, "R1j": 1, "R6": 2, "R6r": 1, "R6o": 2, "R4f": 2, "R4g": 1, "R5c": 1, "R2g": 1, "T1": 4, "R1c": 4, "R1e": 4, "R1f": 4, "R4c": 1, "R4d": 3, "R4e": 1, "R2a": 6, "R2b": 6, "R1a+U": 6, "R1a": 5, "R1b": 5, "R2c": 4, "R2d": 3, "R2e": 2, "R2f": 6, "R3d": 4, "R3": 4, "R4a": 3, "R4b": 3, "R5": 2, "R5b": 1, "R0": 0}
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


def canon(x, tone=True):
    """Âm tiết -> dạng chuẩn: bỏ khác biệt vị trí dấu thanh (hoá/hóa) và i/y (kì/kỳ, qui/quy); giữ thanh nếu tone=True."""
    t, out = "", []
    for c in unicodedata.normalize("NFD", x.lower()):
        if c in TONE_ID: t = TONE_ID[c]
        else: out.append(c)
    b = unicodedata.normalize("NFC", "".join(out))
    b = re.sub(r"^qui", "quy", re.sub(r"(?<=[^aăâeêioôơuưy])y$", "i", b))
    return b + (t if tone else "")


def all_hv(w):
    return bool(HVSYL) and all(canon(x) in HVSYL for x in w.split())


def char_ok(w, han, hv):
    """Mỗi chữ Hán trong từ nguyên có âm Hán Việt (Unihan) đúng bằng âm tiết tương ứng của từ."""
    sy = [canon(x) for x in w.split()]
    return any(len(run) == len(sy) and all(sy[i] in hv.get(run[i], ()) for i in range(len(sy))) for run in RX_HAN.findall(han or ""))


def split_syl(x):
    x = unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", x.lower()) if c not in TONES))
    for o in ONS:
        if x.startswith(o) and len(x) > len(o): return o, x[len(o):]
    return "", x


def lay_pair(a, b):
    (o1, r1), (o2, r2) = split_syl(a), split_syl(b)
    eq = {"c": "k", "q": "k", "gh": "g", "ngh": "ng"}
    o1, o2 = eq.get(o1, o1), eq.get(o2, o2)
    return bool(o1 and o1 == o2) or r1 == r2


def is_lay(w):
    """Láy theo định nghĩa ngữ âm: trùng âm đầu (c=k=q) hoặc trùng vần giữa các âm tiết liền kề (2-4 âm tiết)."""
    p = w.split()
    if len(p) == 2: return lay_pair(*p)
    if len(p) == 3: return lay_pair(p[0], p[1]) or lay_pair(p[1], p[2])
    if len(p) == 4: return (lay_pair(p[0], p[1]) and lay_pair(p[2], p[3])) or (lay_pair(p[0], p[2]) and lay_pair(p[1], p[3]))
    return False


RX_SYL = re.compile(r"^(?:ngh|ng|nh|ph|th|tr|ch|kh|gh|gi|qu|[bcdđghklmnpqrstvx])?[aăâeêioôơuưy]{1,3}(?:ng|nh|ch|[cmnpt])?$")


def foreign_form(w):
    """Có âm tiết không hợp cấu trúc âm tiết tiếng Việt (vd. amiant, ampli): dấu hiệu từ vay."""
    toks = re.split(r"[\s-]+", w)
    if not all(re.fullmatch(r"[^\W\d_]+", t) for t in toks): return False
    return any(not RX_SYL.match(canon(t, False)) for t in toks)


def is_old_tone(w):
    """Dấu thanh kiểu cũ trên nguyên âm đầu của oa, oe, uy (hóa, khỏe, thủy)."""
    return bool(re.search(r"(?:[óòỏõọ][ae]|(?<!q)[úùủũụ]y)", unicodedata.normalize("NFC", w.lower())))


def build_hvlex(phienam, tsv, tvar, uni):
    """Âm Hán Việt SẠCH. Unihan kVietnamese lẫn cả âm chữ Nôm (vd. tuệch), nên chỉ giữ âm của Unihan khi âm đó
    có trong kho âm Hán Việt lấy từ phienam.txt và chinese-hanviet-cognates.tsv."""
    base, clean, words = {}, set(), {}
    if phienam:
        for l in open(phienam, encoding="utf8"):
            if "=" in l:
                c, v = l.rstrip("\n").split("=", 1)
                if c and re.fullmatch(r"[^\W\d_]+", v.strip()): base.setdefault(c, set()).add(canon(v.strip()))
        clean = {x for v in base.values() for x in v}
    if tsv:
        for i, l in enumerate(open(tsv, encoding="utf8")):
            p = l.rstrip("\n").split("\t")
            if i == 0 or len(p) < 6 or not p[5].strip(): continue
            hvw = p[5].strip().lower()
            clean.update(canon(x) for x in hvw.split())
            words.setdefault(" ".join(canon(x) for x in hvw.split()), p[3] or p[2])
    out = {c: set(base.get(c, ())) | {u for u in uni.get(c, ()) if (u in clean or not phienam)} for c in set(base) | set(uni)}
    var = json.load(open(tvar, encoding="utf8")) if tvar else {}
    for sm, ts in var.items():
        for t in ts:
            m = out.get(sm, set()) | out.get(t, set())
            if m: out[sm] = out[t] = m
    return out, words, clean


def load_cedict(path, hv):
    """CC-CEDICT -> (chuỗi âm Hán Việt khả dĩ -> từ Hán, bản không dấu thanh, từ Hán -> nghĩa tiếng Anh)."""
    ced, nt, gloss, rx = {}, {}, {}, re.compile(r"^(\S+) (\S+) \[[^\]]*\] /(.*)/\s*$")
    for l in open(path, encoding="utf8"):
        m = rx.match(l)
        if l.startswith("#") or not m: continue
        for word in {m.group(1), m.group(2)}:
            gloss.setdefault(word, m.group(3)[:300])
            if len(word) < 2 or not all(c in hv for c in word): continue
            n = 1
            for c in word: n *= len(hv[c])
            if n > 32: continue
            for cb in itertools.product(*[sorted(hv[c]) for c in word]):
                ced.setdefault(" ".join(cb), word)
                nt.setdefault(" ".join(re.sub(r"[1-5]$", "", y) for y in cb), word)
    return ced, nt, gloss


def lname(c):
    return f"{LANGNAME[c]} ({c})" if c in LANGNAME else c


def bor_label(c):
    if c in LATE_ZH or c.split("-")[0] in LATE_ZH: return "han", "Vay Hán muộn"
    if c in OLD_ZH: return "han", "Vay Hán (chưa rõ tầng)"
    if c in TAI or c.startswith(("tai-", "kra-", "tw-")): return "vay", "Tày–Thái"
    if c in MALAY: return "vay", "Chăm, Mã Lai, Khmer"
    b = c.split("-")[0]
    if b == "fr": return PHAP
    if b == "en": return ANH
    if b == "ru": return NGA
    if b in {"sa", "pi", "hi", "ur", "bn", "ta", "te", "pra"}: return AN
    if b in {"ja", "ko"}: return NHK
    if b in EURO | {"grc", "el", "sv", "da", "cs"}: return AU
    return KHAC


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
                         note=("Calque từ " if "cal" in t.get("name") or "clq" in t.get("name") else "Vay từ ") + lname(arg(t, "2")) + (": " + arg(t, "3") if arg(t, "3") not in ("", "-") else ""))
                break
        else:
            if re.search(r"onomatopoe", txt, re.I):
                r.update(g="tt", sub="Tượng thanh", conf=2, rule="R4a", decomp=False)
            elif re.search(r"reduplicat", txt, re.I) or {"vi-etym-redup", "rdp"} & set(names):
                r.update(g="ns", sub="Từ láy", conf=2, rule="R4b", decomp=False)
            elif COMPOUND & set(names):
                if len(w.split()) > 1: r.update(g="ns", sub="Từ ghép", conf=2, rule="R5")
                else: r.update(g="ns", sub="Từ ghép", conf=2, rule="R5b", decomp=False, note="Ghép từ các yếu tố có sẵn, viết liền hoặc nối bằng gạch nối.")
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
    mx = re.search(r"\*\s*(fra|eng|rus|deu|ita|spa|lat|zho|cmn|jpn|kor)\s*:", txt)
    if mx:
        g, sub = {"zho": HAN, "cmn": HAN, "jpn": NHK, "kor": NHK, "fra": PHAP, "eng": ANH, "rus": NGA}.get(mx.group(1), AU)
        r.update(g=g, sub=sub, conf=2, rule="R3", decomp=False, review=g == "han", note="Từ nguyên ghi gốc " + mx.group(1) + " (Wiktionary tiếng Việt).")
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
    elif multi and re.search(r"tục ngữ tiếng việt|thành ngữ tiếng việt|thành ngữ hán-việt", cj):
        r.update(g="ns", sub="Thành ngữ, tục ngữ", conf=2, rule="R5c", decomp=False,
                 alt=[("han", "Hán Việt")] if "thành ngữ hán-việt" in cj else [], note="Wiktionary tiếng Việt xếp là thành ngữ/tục ngữ (danh mục của trang).")
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
    gloss = ((S.get("glosses") or [""])[0])[:400]
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
    return dict(gloss=gloss, ipa=ipa, cjk=cjk, han=han, pos=e.get("pos", ""))


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
        g0 = ((e.get("senses") or [{}])[0].get("glosses") or [""])[0].strip()
        vm = next(((m, sb) for x, sb in RX_VAR for m in [x.match(g0)] if m), None)
        if vm and vm[0].group(1).strip() != w0:
            e["_var"] = (vm[1], vm[0].group(1).strip())
            VARIANTS[vm[0].group(1).strip()].append(w0 + (" (sai chính tả)" if vm[1] == "Sai chính tả" else ""))
            SKIPPED["biến thể (thành mục riêng, có liên kết)"] += 1
        if any(t[:1].isupper() for t in w0.split()) or w0.startswith("tiếng "):
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


def main(paths, unihan=None, cedict=None, phienam=None, tsv=None, tvar=None, freq=None):
    hv = {}
    if unihan:
        for l in open(unihan, encoding="utf8"):
            p = l.rstrip("\n").split("\t")
            if len(p) == 3 and p[1] == "kVietnamese":
                hv.setdefault(chr(int(p[0][2:], 16)), set()).update(canon(x) for x in p[2].split())
        HVSYL.update(x for v in hv.values() for x in v)
    HVW = {}
    if phienam or tsv:
        hv, HVW, clean = build_hvlex(phienam, tsv, tvar, hv)
        HVSYL.clear(); HVSYL.update(clean if phienam else HVSYL | clean)
    FREQ = {}
    if freq:
        for l in open(freq, encoding="utf8"):
            p = l.rstrip("\n").split("\t")
            if len(p) == 2 and p[1].isdigit(): FREQ[unicodedata.normalize("NFC", p[0].lower())] = int(p[1])
    CED, CED_NT, CEDG = load_cedict(cedict, hv) if cedict else ({}, {}, {})
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
            if e.get("_var"):
                r.update(g="bt", sub=e["_var"][0], conf=2, rule="R6", decomp=False, lemma=e["_var"][1],
                         note="Biến thể của “" + e["_var"][1] + "”; nguồn gốc xem ở mục đó.")
            if r["rule"] == "R1a" and hv and char_ok(k[0], r["meta"]["han"], hv):
                r.update(conf=3, rule="R1a+U", note="Mỗi chữ Hán trong từ nguyên có âm Hán Việt khớp Unihan (kVietnamese).")
            if r["g"] == "han" and r["sub"] == "Hán Việt":
                ev = (e.get("etymology_text") or "") + " " + " ".join(CEDG.get(h, "") for h in RX_HAN.findall(r["meta"]["han"]))
                if re.search(r"\b(Sanskrit|Pali|Prakrit)\b", ev):
                    r.update(g="vay", sub=AN[1], conf=2, rule="R1h", review=True, alt=[("han", "Hán Việt")],
                             note="Gốc Phạn/Pali, phiên âm qua chữ Hán rồi đọc theo âm Hán Việt (suy từ từ nguyên hoặc nghĩa CC-CEDICT). Cần rà.")
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
        vh = VIET_HOA.get(w)
        if vh and r["rule"] in ("R0", "R1b", "R3") or (vh and r["sub"] == "Vay Hán (chưa rõ tầng)"):
            hit = vh in r["meta"]["han"] or vh in "".join(r["meta"]["cjk"])
            r.update(g="han", sub="Hán Việt Việt hoá", conf=2 if hit else 1, rule="T1", review=True, decomp=False,
                     note="Theo bảng tham chiếu (Wikipedia tiếng Việt, “Từ Hán-Việt”): âm Việt hoá của chữ " + vh + ". Phân loại cổ/Việt hoá còn khác nhau giữa các nguồn; cần đối chiếu. Đồng âm dị nghĩa có thể gán nhầm.")
            if not r["meta"]["han"]: r["meta"]["han"] = vh
        if r["rule"] == "R0" and HVW:
            kk = " ".join(canon(x) for x in w.split())
            if kk in HVW:
                r.update(g="han", sub="Hán Việt", conf=2, rule="R1k", hvsyl=True, note="Khớp danh sách từ Hán–Việt (chinese-hanviet-cognates): " + HVW[kk])
                r["meta"]["han"] = r["meta"]["han"] or HVW[kk]
        if r["rule"] == "R0" and len(w.split()) > 1 and CED:
            key = " ".join(canon(x) for x in w.split())
            nk = " ".join(canon(x, False) for x in w.split())
            if key in CED:
                r.update(g="han", sub="Hán Việt", conf=2, rule="R1f", hvsyl=True, note="Khớp từ Hán trong CC-CEDICT: " + CED[key])
                r["meta"]["han"] = r["meta"]["han"] or CED[key]
        gl0 = r["meta"]["gloss"].lower()
        if r["rule"] == "R0" and re.match(r"^reduplicant of", gl0):
            r.update(g="ns", sub="Từ láy", conf=2, rule="R4d", decomp=False, note="Wiktionary ghi là thành tố láy: " + r["meta"]["gloss"])
        elif r["rule"] == "R0" and re.match(r"^từ mô phỏng|^mô phỏng (?:tiếng|âm)", gl0):
            r.update(g="tt", sub="Tượng thanh", conf=1, rule="R4e", review=True, decomp=False, note="Suy từ lời giải nghĩa (“mô phỏng…”). Cần rà.")
        elif r["rule"] == "R0" and "tượng hình" in gl0:
            r.update(g="tt", sub="Tượng hình", conf=1, rule="R4e", review=True, decomp=False, note="Lời giải nghĩa nhắc đến “tượng hình”. Cần rà.")
        if r["rule"] == "R0":
            raw = r["meta"]["gloss"].strip()
            mref = re.match(r"^(?:Xem|Như|Đồng nghĩa của|Cũng như|same as|synonym of)\s+(.+?)\.?$", re.sub(r"^\([^)]*\)\s*", "", raw), re.I)
            mdia = re.match(r"^Từ (?:miền|phương ngữ) (?:Nam|Bắc|Trung)[^ ]* chỉ (.+?)\.?$", raw)
            mabb = re.match(r"^(?:abbreviation of|clipping of|short for|viết tắt của|rút gọn của)\s+(.+?)\.?$", raw, re.I)
            if mdia: r.update(g="bt", sub="Phương ngữ", conf=2, rule="R6", decomp=False, lemma=mdia.group(1), note="Từ phương ngữ chỉ “" + mdia.group(1) + "”.")
            elif re.match(r"^\((?:phương ngữ|đphg)\b", raw, re.I): r.update(g="bt", sub="Phương ngữ", conf=1, rule="R6", decomp=False, lemma=(mref.group(1) if mref else ""), note="Giải nghĩa đánh dấu phương ngữ.")
            elif mref: r.update(g="bt", sub="Tham chiếu từ khác", conf=1, rule="R6r", decomp=False, lemma=mref.group(1), note="Wiktionary giải nghĩa bằng cách tham chiếu tới “" + mref.group(1) + "”.")
            elif mabb: r.update(g="ns", sub="Viết tắt, rút gọn", conf=2, rule="R4f", decomp=False, lemma=mabb.group(1), note="Viết tắt hoặc rút gọn của “" + mabb.group(1) + "”.")
            elif re.match(r"^\((?:từ lóng|lóng|thông tục|khẩu ngữ|slang)", raw, re.I) or re.search(r"slang", raw[:25], re.I):
                r.update(g="ns", sub="Từ lóng, khẩu ngữ", conf=1, rule="R4g", review=True, decomp=False, note="Suy từ nhãn phong cách trong giải nghĩa (lóng, thông tục, khẩu ngữ). Nhãn phong cách không phải nguồn gốc; cần rà.")
            elif r["meta"].get("pos") in ("phrase", "proverb"): r.update(g="ns", sub="Thành ngữ, tục ngữ", conf=2, rule="R5c", decomp=False, note="Wiktionary xếp là cụm từ/thành ngữ/tục ngữ.")
        if r["rule"] == "R0" and len(w.split()) == 1 and re.match(r"^(?:bl|tl|ml|kl)[aăâeêioôơuưy]{1,3}(?:ng|nh|ch|[cmnpt])?$", canon(w, False)):
            r.update(g="kt", sub="Việt–Mường", conf=1, rule="R2g", review=True, decomp=False, note="Phụ âm đầu ghép kiểu tiếng Việt cổ (bl-, tl-, ml-, kl-); giả định là từ kế thừa. Cần rà.")
        if r["rule"] == "R0" and HVSYL and is_lay(w) and not all_hv(w):
            r.update(g="ns", sub="Từ láy", conf=1, rule="R4c", review=True, decomp=False,
                     note="Suy từ cấu trúc ngữ âm (trùng âm đầu hoặc vần), không phải Wiktionary khẳng định. Cần rà.")
        if r["rule"] == "R0" and ((("-" in w) and not w.startswith("-") and not w.endswith("-") and not re.search(r"\d", w)) or re.search(r"[fjwz]", w.lower()) or foreign_form(w)):
            r.update(g=CHUARO[0], sub=CHUARO[1], conf=1, rule="R3f", review=True, decomp=False,
                     note="Hình thức chữ viết không giống âm tiết tiếng Việt (gạch nối kiểu phiên âm, chữ cái f/j/w/z, hoặc cấu trúc âm tiết lạ): nhiều khả năng vay từ ngoại ngữ, chưa rõ ngôn ngữ nguồn.")
        if len(w.split()) > 1:
            if r["decomp"] and compositional(w, gl):
                for s in w.split(): stubs[s].append((w, r))
                continue
            r["parts"] = w.split()
            if r["rule"] == "R0":
                r["note"] = "Có thể là từ ghép; nghĩa không suy ra trực tiếp từ thành tố nên giữ làm mục riêng."
        atoms[(w, n)] = r
    groups = collections.defaultdict(list)              # biến thể chính tả: bỏ dấu kiểu cũ <-> kiểu mới
    for (w, n) in atoms: groups[" ".join(canon(x) for x in w.split())].append((w, n))
    for ks in groups.values():
        olds, news = [k for k in ks if is_old_tone(k[0])], [k for k in ks if not is_old_tone(k[0])]
        if olds and news:
            for k in olds:
                if atoms[k]["g"] != "bt":
                    VARIANTS[news[0][0]].append(k[0])
                    atoms[k].update(g="bt", sub="Bỏ dấu kiểu cũ", conf=2, rule="R6o", decomp=False, lemma=news[0][0],
                                    note="Cách đặt dấu thanh kiểu cũ của “" + news[0][0] + "”; nguồn gốc xem ở mục đó.")
    NATIVE = {canon(w) for (w, n), r in atoms.items() if " " not in w and r["g"] not in ("han", "vay", "bt", "cr")}
    for (w, n), r in atoms.items():                      # suy luận Hán Việt: mọi âm tiết có âm Hán Việt, không âm tiết nào là từ bản địa đứng riêng
        if r["rule"] == "R0" and len(w.split()) > 1 and all_hv(w) and not any(canon(x) in NATIVE for x in w.split()):
            r.update(g="han", sub="Nghi là Hán Việt (suy luận)", conf=1, rule="R1i", review=True, hvsyl=True,
                     note="Mọi âm tiết đều có âm Hán Việt (Unihan) và không âm tiết nào xuất hiện như từ bản địa đứng riêng trong dữ liệu. Chưa có bằng chứng trực tiếp; không tính vào số Hán Việt.")
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
        d = {"id": id_, "w": w, "gloss": r["meta"]["gloss"], "han": r["meta"]["han"], "cjk": r["meta"]["cjk"], "ipa": r["meta"]["ipa"], "L": [[r["g"], ("Nhiều âm tiết" if (" " in w or "-" in w) else "Một âm tiết") if r["g"] == "cr" else r["sub"]]] + [list(x) for x in r.get("alt", [])], "conf": r["conf"], "recon": r["recon"],
             "cog": "; ".join(r["cog"]), "doublets": r["dbl"], "note": r["note"],
             "src": "Wiktionary (kaikki.org), CC BY-SA", "rule": r["rule"], "review": r["review"], "parts": r.get("parts", []), "variants": VARIANTS.get(w, [])[:8], "lemma": r.get("lemma", ""), "freq": FREQ.get(unicodedata.normalize("NFC", w.lower()), 0)}
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
    cand = [w for w, _ in todo_pk if " " in w and all_hv(w)]
    with open("ung_vien_han_viet.txt", "w", encoding="utf8") as f:
        f.write(f"{len(cand)} mục chờ điền nhiều âm tiết mà MỌI âm tiết đều có âm Hán Việt (chưa khớp CC-CEDICT). Mẫu 200:\n")
        for w in sorted(cand)[:: max(1, len(cand) // 200)][:200]: f.write(w + "\n")
    import random; random.seed(1)
    with open("mau_chua_xac_dinh.txt", "w", encoding="utf8") as f:
        for w, pp in random.sample(todo_pk, min(150, len(todo_pk))): f.write(w + " | " + (" | ".join(pp) if pp else "") + "\n")
    print("\n".join(rep[:30]))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    miss = [x for x in a if not os.path.exists(x)]
    if miss: sys.exit("Không tìm thấy tệp: " + ", ".join(miss) + "\nKiểm tra tên tệp và thư mục đang đứng khi chạy lệnh.")
    KEYS = {"unihan": "unihan", "cedict": "cedict", "phienam": "phienam", "chinese-hanviet": "tsv", "ktraditionalvariant": "tvar", "opensubs": "freq"}
    miss = [x for x in a if not os.path.exists(x)]
    if miss: sys.exit("Không tìm thấy tệp: " + ", ".join(miss))
    extra, files = {}, []
    for x in a:
        k = next((v for pre, v in KEYS.items() if os.path.basename(x).lower().startswith(pre)), None)
        if k: extra[k] = x
        else: files.append(x)
    main(files, **extra)
