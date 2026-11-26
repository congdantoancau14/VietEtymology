# Tra từ nguyên

Công cụ tra cứu và phân loại từ nguyên tiếng Việt chạy **offline**, kết hợp dữ liệu từ Wiktionary và các nguồn ngữ liệu bổ trợ để xuất ra `entries.json` và xem trực tiếp trên giao diện web tĩnh.

- **Phiên bản hiện tại:** Offline using[cite: 1, 2, 3]
- **Liên hệ:** phuongtranlangit@gmail.com
- **Ủng hộ dự án:** https://buymeacoffee.com/phuongtranlangit

---

## Cấu trúc thư mục gợi ý

```text
<thư mục gốc>/
├── data/               # Nguồn dữ liệu đầu vào (tự nhận diện theo tên tệp)
├── output/             # entries.json, bao_cao.txt và các tệp xuất ra
├── scripts/
│   └── phan_loai.py    # Script phân loại từ nguyên và sinh entries.json
└── web/
    ├── Tra từ nguyên.html
    └── Chú giải nguồn gốc từ.html
```
[cite: 1, 2, 3]

---

## Hướng dẫn sử dụng

### 1. Tạo dữ liệu `entries.json` (tùy chọn nếu đã có sẵn tệp)

Đặt dữ liệu nguồn vào thư mục `data/` (có thể chạy `sap_xep.py` để sắp xếp trước), sau đó chạy:

```bash
python scripts/phan_loai.py
```

Hoặc chỉ định thư mục gốc / thư mục đầu ra / danh sách tệp cụ thể:

```bash
python scripts/phan_loai.py --goc <thư mục gốc> --out <thư mục đầu ra>
python scripts/phan_loai.py tep1.jsonl tep2.jsonl Unihan_Readings.txt
```

Các nguồn dữ liệu được tự động nhận diện theo tiền tố/tên tệp (không phân biệt chữ hoa/thường):
- `*.jsonl`: dữ liệu Wiktionary (kaikki.org hoặc `vi-extract`)
- `Unihan*`, `cedict*`, `phienam*`, `chinese-hanviet*`, `kTraditionalVariant*`
- `opensubs*`, `Sidwell*`, `thanhngu*` (hoặc tự trích từ PDF qua `trich_thanh_ngu.py` nếu có `pdftotext`)[cite: 3]

Sau khi chạy, kết quả được ghi vào thư mục `output/`, trong đó có `output/entries.json` và `output/bao_cao.txt`[cite: 3].

### 2. Mở giao diện web và nạp dữ liệu

1. **Webpage:** Tải tệp `web\Tra từ nguyên.html` và mở trực tiếp bằng trình duyệt.
2. **Data:** Tải tệp `output\entries.json` và nạp vào trang web tại mục **"Nạp dữ liệu (biên tập viên)"** ở cột trái phía dưới trang (có thể chọn gộp với dữ liệu hiện có nếu cần).[cite: 1]

---

## Hệ thống phân loại & tài liệu chú giải

Giao diện web chia mục từ theo các nhóm nguồn gốc lớn và nhãn con chi tiết, đi kèm mức độ tin cậy (từ *Chưa xác định* đến *Chắc chắn*) và hỗ trợ lọc theo nhóm, nhãn con, mức tin cậy, thẻ, thành tố vay hoặc xuất dữ liệu ra CSV / JSON[cite: 1, 2].

Bạn có thể mở tệp `web\Chú giải nguồn gốc từ.html` để xem giải thích chi tiết về:
- Các nhóm nguồn gốc (*Kế thừa*, *Vay Hán*, *Vay khác và tiếp xúc*, *Nội sinh*, *Tượng thanh, tượng hình*, *Chưa xác định*) và các nhãn con tương ứng
- Góc nhìn về khái niệm *"Thuần Việt"*
- Thang mức độ tin cậy và các ký hiệu ngữ âm / từ nguyên học[cite: 2]

---

## Lưu ý & bản quyền

- Dữ liệu từ Wiktionary áp dụng giấy phép **CC BY-SA** và cần ghi nguồn khi sử dụng[cite: 3].
- Phân loại tự động dựa trên quy tắc và nguồn tham chiếu hiện có; các mục cần kiểm chứng thêm được đánh dấu để người dùng hoặc biên tập viên rà soát[cite: 2, 3].
- Nếu không nạp dữ liệu mới, trang web vẫn hoạt động với bộ dữ liệu mẫu tích hợp sẵn và lưu dữ liệu nạp/đóng góp cục bộ trong trình duyệt[cite: 1].

---

## Liên hệ & đóng góp

- **Email:** phuongtranlangit@gmail.com
- **Buy Me a Coffee:** https://buymeacoffee.com/phuongtranlangit