# MangaReader

MangaReader là công cụ thử nghiệm để nhận diện và cắt các khung truyện manga từ ảnh trang, sau đó xuất từng khung thành ảnh riêng để đưa vào quy trình dựng video.

## Hiện có

- Mở một hoặc nhiều ảnh trang manga.
- Tự tìm đường viền, khoảng trắng giữa khung và khung chéo để đề xuất vùng panel dạng đa giác.
- Xem và chỉnh đường cắt: kéo góc, vẽ panel, chia panel bằng đường cắt, gộp hoặc đổi thứ tự đọc.
- Sắp thứ tự đọc theo hướng từ trên xuống dưới, phải sang trái; có thể sửa tay khi trang có bố cục đặc biệt.
- Xuất ảnh JPG và PNG alpha theo từng panel, ảnh xem đường cắt và dữ liệu tọa độ JSON.
- Lưu và mở lại phiên chỉnh sửa.

> Nhận diện tự động là bước đề xuất. Viền mờ, chữ hiệu ứng nối qua nhiều khung hoặc bố cục phá cách có thể cần chỉnh tay. Tool hiện nhận ảnh từ máy; chưa tải chương từ URL và chưa dựng video.

## Chạy trên Windows

1. Cài Python 3.10 trở lên.
2. Mở Terminal tại thư mục dự án và chạy `python -m pip install -r requirements.txt`.
3. Nhấp đúp `Mo_Panel_Cutter.cmd`.

Chọn ảnh hoặc thư mục ảnh trong giao diện. Sau khi rà lại đường cắt, chọn **Xuất tất cả**. JPG trong thư mục `Flow_JPG` có thể tải thủ công lên công cụ dựng video như Google Flow.

## Cấu trúc

- `panel_cutter.pyw`: giao diện Windows.
- `detector.py`: phát hiện panel, thứ tự đọc và xuất ảnh.
- `requirements.txt`: thư viện cần cài.
- `Mo_Panel_Cutter.cmd`: khởi chạy giao diện.
- [ROADMAP.md](ROADMAP.md): hướng phát triển nhập URL và dựng video theo từng panel.

Ảnh được xử lý cục bộ bởi chương trình này. Việc tải ảnh lên dịch vụ dựng video bên ngoài là thao tác riêng.

