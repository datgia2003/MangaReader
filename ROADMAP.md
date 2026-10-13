# Roadmap: từ link manga đến video theo từng panel

## Khả thi không?

Có. Quy trình có thể phát triển thành: nhập link chương → lấy ảnh trang → nhận diện và sắp thứ tự panel → rà/chỉnh panel → tạo timeline → dựng video. Phần tách panel đã có bản thử nghiệm chạy trên ảnh cục bộ. Phần lấy ảnh từ website và dựng video chưa được triển khai.

Muốn hỗ trợ link web ổn định, cần bổ sung bộ đọc trang theo từng website. Các trang khác nhau lưu chương bằng HTML, API, ảnh ghép hoặc trình xem riêng; một bộ tải chung không thể bảo đảm hoạt động với mọi URL. Bản đầu nên hỗ trợ các trang người dùng có quyền truy cập và có giao diện tải ảnh hợp lệ, rồi bổ sung từng nguồn cụ thể.

## Các bước đề xuất

### 1. Nạp chương từ URL

- Người dùng dán URL chương và chọn nguồn đã hỗ trợ.
- Bộ nạp lấy danh sách trang theo thứ tự, tải ảnh về thư mục dự án và hiển thị trạng thái.
- Lưu URL nguồn và thứ tự trang để có thể mở lại dự án.
- Tôn trọng giới hạn truy cập, quyền của website và quyền sử dụng nội dung; không tìm cách vượt cơ chế đăng nhập, paywall hay chống tải.

### 2. Tách và duyệt panel

- Chạy bộ nhận diện hiện tại trên từng trang.
- Hiển thị các panel theo thứ tự đọc phải sang trái, trên xuống dưới.
- Cho phép sửa đường viền, thứ tự, bỏ panel hoặc tách/gộp trước khi dựng.
- Giữ bước duyệt tay vì trang đặc biệt và chữ hiệu ứng có thể khiến nhận diện sai.

### 3. Dựng video theo khung

- Mỗi panel trở thành một cảnh trên timeline, có thời lượng, crop và điểm lấy nét.
- Thêm chuyển động máy quay 2.5D như pan, zoom, parallax nhẹ, rung theo nhịp và chuyển cảnh.
- Đồng bộ nhịp cảnh với nhạc; cho phép chọn đoạn nhạc, độ dài video và preset dọc/ngang.
- Xuất bản xem trước để sửa timeline trước khi render cuối.

Các hiệu ứng pan/zoom và parallax tạo cảm giác chuyển động từ ảnh tĩnh; chúng không tự làm nhân vật diễn hoạt như anime. Muốn nhân vật chuyển động thực sự cần thêm dịch vụ hoặc mô hình image-to-video, cùng bước kiểm tra chất lượng từng cảnh. Đây là phần riêng và có thể tốn thời gian/chi phí xử lý.

### 4. Mở rộng sau bản đầu

- Nhận diện bong bóng thoại và vùng chữ để tùy chọn giữ, che hoặc thay nội dung.
- Tạo chú thích/voice-over nếu người dùng chọn.
- Hàng đợi xử lý nhiều chương, lưu preset và tiếp tục dự án dở dang.

## Phạm vi bản hiện tại

| Hạng mục | Trạng thái |
| --- | --- |
| Nhập ảnh từ máy | Có |
| Tự nhận diện panel đa giác | Có, cần rà lại với trang khó |
| Sửa panel và thứ tự đọc | Có |
| Xuất từng panel | Có |
| Tải chương từ URL | Chưa có |
| Timeline và render video | Chưa có |
| Chuyển động nhân vật kiểu anime | Chưa có |

