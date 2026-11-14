# Kế hoạch bổ sung Single Mode cho Auto Quests

## 1. Mục tiêu

Bổ sung hai chế độ chạy quest cho từng người dùng:

- `multi`: giữ nguyên cơ chế hiện tại, nhiều quest được chạy đồng thời.
- `single`: mỗi thời điểm chỉ chạy một quest; sau khi quest hiện tại kết thúc hoặc thất bại, bot chờ 10 giây rồi chạy quest tiếp theo.

Thiết lập mode được lưu lâu dài và áp dụng cho các lần chạy quest sau đó.

Trong tài liệu này, “10 giây” được hiểu là khoảng nghỉ giữa hai quest. Đây không phải thời gian tối đa của một quest; các quest video/heartbeat hiện tại có thể cần chạy nhiều phút.

## 2. Hiện trạng cần giữ nguyên

`QuestEngine` hiện tạo task cho tất cả quest cần xử lý rồi chờ chúng hoàn tất. Semaphore `MAX_PARALLEL_PLAY` quyết định số quest có thể chạy đồng thời.

Các đường chạy đang tạo `QuestEngine` gồm:

- Lần chạy ngay sau khi lưu token và lệnh `/autoquests-run` trong `bot/cogs/autoquests.py`.
- Scheduler định kỳ trong `bot/services/scheduler.py`.
- Startup auto-run trong `bot/services/scheduler.py`.
- Lệnh chạy một lần `/quests` trong `bot/cogs/quests.py`.

`TaskManager` vẫn chịu trách nhiệm giới hạn một run trên mỗi token và giới hạn số run toàn hệ thống. Single mode chỉ thay đổi cách các quest bên trong một run được lập lịch; không thay đổi các giới hạn cấp run.

Mode mặc định phải là `multi` để các user và database hiện tại tiếp tục hoạt động như trước.

## 3. Phạm vi cấu hình

Mode được lưu theo `discord_uid`, không lưu theo từng token. Một user có nhiều token sẽ dùng cùng một mode cho các token đó.

Đề xuất áp dụng mode cho mọi đường chạy sử dụng `QuestEngine`, gồm cả `/quests`, để câu “mọi lần chạy quests về sau” có cùng một ý nghĩa. Nếu chỉ muốn áp dụng cho autoquests lưu token, cần loại trừ `/quests` ở bước wiring.

Khi một run đã bắt đầu, mode được chụp lại cho run đó. Việc đổi mode trong lúc run đang hoạt động chỉ ảnh hưởng đến run kế tiếp; bot không tự hủy run hiện tại.

## 4. Thay đổi database

### Schema

Thêm cột vào bảng `user_interactions`:

```sql
quest_mode TEXT NOT NULL DEFAULT 'multi'
```

Database cũ cần migration idempotent bằng cách kiểm tra `PRAGMA table_info(user_interactions)` trước khi chạy `ALTER TABLE`.

### API database

Thêm các method:

```text
get_user_quest_mode(discord_uid) -> "multi" | "single"
set_user_quest_mode(discord_uid, mode)
```

`get_user_quest_mode` phải fallback về `multi` nếu user chưa có bản ghi hoặc dữ liệu không hợp lệ. `set_user_quest_mode` chỉ chấp nhận hai giá trị `single` và `multi`.

Lệnh mode phải tạo bản ghi user nếu user chưa từng lưu token hoặc chưa từng dùng bot.

## 5. Thay đổi QuestEngine

### Constructor

Thêm tham số execution mode, ví dụ:

```python
QuestEngine(api=api, run_mode="multi", ...)
```

Có thể thêm cấu hình:

```text
SINGLE_MODE_DELAY_SECONDS=10
```

Giá trị mặc định là 10 giây và không cần cho user thay đổi qua slash command.

### Multi mode

Giữ nguyên logic hiện tại:

1. Fetch và auto-accept quest.
2. Lọc actionable quest.
3. Tạo task cho toàn bộ actionable quest.
4. Chờ toàn bộ task hoàn tất.

Không thêm delay trong mode này.

### Single mode

Luồng xử lý:

1. Fetch, auto-accept và lọc actionable quest như hiện tại.
2. Giữ nguyên thứ tự quest do Discord trả về.
3. Chạy quest đầu tiên và chờ task kết thúc.
4. Nếu còn quest và engine chưa bị hủy, chờ 10 giây.
5. Chạy quest tiếp theo.
6. Kết thúc khi hết quest hoặc run bị hủy.

Các điều kiện cần bảo đảm:

- Một engine single mode không có quá một quest đang chạy.
- Không chờ thêm sau quest cuối cùng.
- Quest thất bại vẫn nhường lượt cho quest tiếp theo sau khoảng nghỉ.
- Hủy run không bắt đầu quest mới và không để lại task trong `_running_tasks`.
- `completed_ids`, progress callback và summary vẫn hoạt động như mode multi.

## 6. Truyền mode vào các đường chạy

Các nơi tạo `QuestEngine` phải đọc mode của user và truyền vào constructor:

- `AutoQuestsCog._run_token()`.
- Scheduler định kỳ.
- Scheduler startup.
- `/quests` nếu áp dụng mode cho mọi loại run.

Admin force-run gọi lại `_run_token()`, nên sẽ tự dùng cùng mode của user đó.

Nên tạo helper dùng chung để đọc mode và khởi tạo engine, tránh việc scheduler hoặc một command mới quên truyền mode.

## 7. Thiết kế slash command

### Cú pháp yêu cầu

```text
/autoquests mode single
/autoquests mode multi
```

Discord không cho phép một command vừa nhận option token trực tiếp vừa có subcommand. Vì vậy, để có đúng cú pháp trên, `/autoquests` hiện tại cần chuyển thành command group.

Đề xuất command sau khi chuyển đổi:

```text
/autoquests save <token> [label]
/autoquests mode <single|multi>
```

Các command đang là top-level như `/autoquests-run`, `/autoquests-status`, `/autoquests-list` có thể giữ nguyên.

Nếu bắt buộc giữ cú pháp cũ `/autoquests <token> [label]`, phương án thay thế là thêm `/autoquests-mode <single|multi>`. Phương án này giữ compatibility tốt hơn nhưng không đáp ứng chính xác cú pháp nested command yêu cầu.

Command mode cần:

- Dùng Discord choices chỉ gồm `single` và `multi`.
- Phản hồi ephemeral.
- Hiển thị mode mới và thông báo mode sẽ áp dụng cho các run tiếp theo.
- Báo mode hiện tại nếu user chọn lại cùng giá trị.

## 8. Progress, status và localization

Single mode có thể làm các quest chờ bị hiển thị như đang chạy nếu giữ nguyên progress callback hiện tại. Nên bổ sung trạng thái `queued` hoặc callback bắt đầu quest để progress message phân biệt:

- Quest đang chờ.
- Quest đang chạy.
- Quest đã hoàn thành.
- Quest thất bại/chưa hoàn thành.

Thêm bản dịch tiếng Anh và tiếng Việt cho:

- Mode hiện tại.
- Lưu mode thành công.
- Mô tả single mode và multi mode.
- Trạng thái queued nếu giao diện progress sử dụng trạng thái này.

Nên hiển thị mode hiện tại trong `/autoquests-status` hoặc `/autoquests-info` để user dễ kiểm tra cấu hình.

## 9. Tài liệu cần cập nhật

- `README.md`: command mới, hành vi hai mode và ví dụ sử dụng.
- `/help`: thêm hướng dẫn chọn mode.
- `.env.example`: thêm `SINGLE_MODE_DELAY_SECONDS` nếu cho phép cấu hình deployment.
- Mô tả concurrency cần thống nhất với giá trị thực tế của `MAX_PARALLEL_PLAY`; hiện README và `.env.example` ghi 6 trong khi môi trường hiện tại có thể dùng 10.

## 10. Kế hoạch kiểm thử

### Database

- Database mới trả về `multi` mặc định.
- Database cũ được migration đúng một lần.
- Đọc/ghi mode cho từng user.
- Giá trị không hợp lệ bị từ chối.

### QuestEngine

- Multi mode vẫn khởi chạy nhiều quest đồng thời như trước.
- Single mode chỉ có một quest hoạt động tại mỗi thời điểm.
- Single mode giữ đúng thứ tự quest.
- Có khoảng nghỉ 10 giây giữa hai quest, nhưng không có delay sau quest cuối.
- Quest thất bại không chặn các quest sau.
- Cancel/timeout không để lại task treo.

### Integration

- `/autoquests mode` lưu được mode và tồn tại sau khi bot restart.
- `/autoquests save`, `/autoquests-run`, scheduler và startup run dùng đúng mode.
- `/quests` dùng đúng mode nếu được đưa vào phạm vi.
- Đổi mode khi một run đang chạy không làm thay đổi run hiện tại.

### Total quests

- Tạo fixture có quest đã hoàn thành, quest actionable và quest không được xử lý để kiểm tra từng loại tổng số.
- Kiểm tra số hiển thị trong progress message, summary của run, thống kê cá nhân và public stats API.
- Chạy lại cùng một quest để xác nhận không làm tăng tổng số completion duy nhất.
- Xác nhận số liệu sau một run mới được phản ánh trong khoảng thời gian freshness đã thống nhất, không bị giữ bởi cache cũ.

## 11. Tiêu chí nghiệm thu

- User mới và user hiện tại mặc định chạy `multi`.
- User có thể đổi giữa `single` và `multi` bằng command đã thống nhất.
- Single mode không chạy đồng thời nhiều quest trong cùng một token.
- Multi mode không bị xóa và không có thêm delay ngoài logic hiện tại.
- Cấu hình được giữ sau restart bot.
- Tất cả đường chạy được xác định trong mục 6 đều dùng cùng một mode.
- Progress, summary, statistics và cleanup token hiện tại không bị phá vỡ.
- Giá trị `Total quests` không bị tăng sai hoặc lệch giữa progress message, summary, `/autoquests-info` và website.

## 12. Điểm cần chốt trước khi triển khai

1. Xác nhận “10 giây” là khoảng nghỉ giữa hai quest, không phải giới hạn thời gian chạy một quest.
2. Xác nhận chấp nhận chuyển command lưu token từ `/autoquests <token>` sang `/autoquests save <token>` để dùng đúng `/autoquests mode single/multi`.
3. Xác nhận mode có áp dụng cho cả `/quests` chạy một lần hay chỉ cho các autoquest token đã lưu.

## 13. Khắc phục lỗi hiển thị “Total quests”

### Vấn đề cần xử lý

Sau mỗi lần chạy quest, giá trị “Total quests” có thể không phản ánh đúng số quest của run hoặc tổng số quest đã hoàn thành của người dùng. Hiện tại có nhiều khái niệm đang được dùng gần giống nhau:

- Tổng quest Discord trả về trong lần fetch.
- Tổng quest actionable được đưa vào run.
- Số quest hoàn thành trong run hiện tại.
- Tổng quest đã hoàn thành duy nhất của một user.
- Tổng quest hoàn thành được hiển thị trên public website.

Plan phải tách riêng các giá trị này, tránh dùng một field `total` cho nhiều mục đích.

### Điều tra nguồn sai lệch

Kiểm tra các điểm sau trước khi chọn cách sửa:

- `QuestEngine.run_once()` đang gán `summary["total"]` theo số quest fetch được, trong khi progress message chỉ khởi tạo danh sách từ actionable quest.
- `completed_now` phải chỉ đếm quest mới hoàn thành trong run hiện tại.
- `quest_stats` đang là dữ liệu chi tiết theo user/quest, còn `global_stats.total_quests_done` là bộ đếm tăng dần có thể lệch nếu run bị lặp hoặc ghi trùng.
- `Database.count_total_quests_done()` đang fallback sang global counter khi truy vấn deduplicated detail trả về 0; cần phân biệt “chưa có completion” với “database cũ chưa có bảng dữ liệu chi tiết”.
- Public stats API cập nhật `_stats_data` theo background loop mỗi 60 giây và endpoint còn cache 10 giây, nên số liệu website có thể chậm hơn run vừa hoàn thành.

### Thiết kế số liệu rõ ràng

Đổi summary thành các field có ý nghĩa riêng, ví dụ:

```text
fetched_total       = tổng quest Discord trả về
actionable_total    = tổng quest được đưa vào run
completed_before    = quest đã hoàn thành trước run
completed_now       = quest vừa hoàn thành trong run
completed_unique_total = tổng completion duy nhất của user
```

Progress message dùng `actionable_total` cho tổng quest của phiên. Summary cuối phiên hiển thị `completed_now` cho kết quả của phiên, không dùng `fetched_total` thay thế.

### Nguồn dữ liệu chuẩn

- Dùng `quest_stats` đã deduplicate theo `(discord_uid, quest_id)` làm nguồn chuẩn cho tổng completion của user và public stats.
- Không dùng global counter để ghi đè một giá trị detail query đã trả về 0. Nếu cần hỗ trợ database cũ, chỉ fallback khi bảng/column chưa tồn tại, không fallback chỉ vì count hiện tại bằng 0.
- Khi ghi một completion, bảo đảm cùng một `(discord_uid, quest_id)` không được cộng nhiều lần. Có thể dùng unique index/migration hoặc thao tác insert idempotent.
- Nếu vẫn giữ `global_stats.total_quests_done` để tương thích, coi nó là legacy/fallback và không dùng song song với detail count trong database mới.

### Đồng bộ website

Thống nhất tên và ý nghĩa field giữa database, `/v1/stats/public`, `assets/js/stats.js` và `index.html`. Sau khi một run lưu completion thành công, stats API cần có cơ chế refresh/invalidate phù hợp hoặc công khai rõ freshness tối đa. Không để UI hiển thị một số mới nhưng được tính từ nguồn khác với số trong bot.

### Tiêu chí nghiệm thu riêng

- Run không có quest hoàn thành hiển thị `completed_now = 0`, không lấy số cũ từ global counter.
- Run hoàn thành `N` quest tăng tổng completion đúng `N` lần đầu tiên.
- Chạy lại cùng quest không làm tổng completion duy nhất tăng thêm.
- Tổng quest trong progress message bằng số actionable quest của đúng run.
- Tổng completion trong `/autoquests-info`, admin info, public API và website dùng cùng một định nghĩa.
- Sau khi run kết thúc, website cập nhật trong thời gian freshness đã quy định và không hiển thị số sai do cache hoặc dữ liệu cũ.

## 14. Bổ sung giới thiệu và Q&A trên website

Phần website chỉ được cập nhật sau khi cơ chế bot đã được triển khai và kiểm thử. Mục tiêu là để người dùng hiểu rõ sự khác nhau giữa hai mode trước khi dùng lệnh cấu hình.

### Phần giới thiệu cơ chế

Trong `index.html`, thêm một section riêng, đặt sau phần Features và trước phần Guide, với nội dung:

- Giới thiệu ngắn về mục đích của hai mode.
- Card `Multi Mode`: chạy nhiều quest song song, ưu tiên tốc độ, giữ nguyên cơ chế cũ.
- Card `Single Mode`: chỉ chạy một quest tại một thời điểm, chờ 10 giây giữa hai quest.
- Giải thích rằng mode được lưu theo tài khoản và áp dụng cho các lần chạy sau.
- Hiển thị ví dụ command:

  ```text
  /autoquests mode single
  /autoquests mode multi
  ```

Thêm liên kết tới section này trong navigation nếu không làm menu quá tải. Layout phải dùng các class responsive sẵn có hoặc class riêng có breakpoint cho màn hình nhỏ.

### Bổ sung vào bảng command

Thêm một dòng cho `/autoquests mode <single|multi>` với mô tả ngắn và ví dụ chọn `single`.

Nội dung website phải thống nhất với command cuối cùng được triển khai. Nếu quyết định giữ command cũ `/autoquests <token>`, phần web phải dùng command thay thế đã chọn thay vì quảng bá cú pháp không tồn tại.

### Q&A trong FAQ

Mở rộng FAQ hiện có trong `index.html` bằng các câu hỏi về execution mode:

1. Single Mode là gì?
2. Multi Mode khác Single Mode như thế nào?
3. Đổi mode bằng command nào?
4. 10 giây là khoảng nghỉ giữa hai quest hay timeout của một quest?
5. Đổi mode có ảnh hưởng đến phiên đang chạy không?

Các câu trả lời cần nêu rõ:

- Single Mode xử lý tuần tự và giảm số request đồng thời.
- Multi Mode vẫn tồn tại và không có delay bổ sung.
- 10 giây là khoảng nghỉ giữa hai quest, không phải thời gian tối đa của quest.
- Mode mới áp dụng cho run tiếp theo; run hiện tại giữ mode đã chọn lúc bắt đầu.

### Đa ngôn ngữ

Không hardcode toàn bộ nội dung mới chỉ bằng một ngôn ngữ. Thêm key tương ứng vào:

- `assets/locales/vi.json`
- `assets/locales/en.json`
- `assets/locales/ja.json`

Các phần HTML mới dùng `data-i18n` để hoạt động với cơ chế chuyển ngôn ngữ hiện tại. Nội dung FAQ cũng phải có đủ key câu hỏi và câu trả lời cho cả ba locale.

### Tiêu chí nghiệm thu website

- Section giới thiệu hiển thị đúng ở desktop và mobile.
- Navigation, command table và FAQ đều có thông tin về Single/Multi Mode.
- Chuyển VI/EN/JA không để lộ key i18n thô.
- Nội dung không nói rằng Single Mode giới hạn mỗi quest ở 10 giây.
- Command hiển thị trên website khớp với command thực tế sau khi bot được triển khai.

## 15. Hiển thị mode trong tin nhắn của bot

Mỗi run cần cho người dùng biết bot đang dùng `Single` hay `Multi`, để họ không phải đoán từ cách quest được xử lý. Thông tin này nên ngắn gọn và đặt ở một vị trí cố định trong progress message cũng như summary cuối run.

### Progress message

Thêm một field hoặc dòng thông tin riêng:

```text
Mode: Single (`/autoquests mode multi` để đổi)
```

hoặc:

```text
Mode: Multi (`/autoquests mode single` để đổi)
```

Không lặp lại mode trong từng quest. Các trạng thái quest chỉ dùng emoji tối thiểu theo quy ước đã thống nhất:

```text
✅ Quest A [WATCH_VIDEO] 100%
Quest B [PLAY_ACTIVITY] Waiting
```

### Summary cuối run

Summary phải giữ lại mode đã dùng trong run, kể cả khi user đổi setting sau đó:

```text
Auto-run summary

Mode: Single
Completed 2/3 quests
```

Mode phải được lấy từ snapshot của run, không đọc lại setting mới tại thời điểm gửi summary.

### Gợi ý đổi mode

Command đổi mode được đặt trong ngoặc ngay sau mode hiện tại để giữ thông tin gọn và không tạo thêm một dòng riêng:

```text
Mode: Single (`/autoquests mode multi` để đổi)
```

hoặc:

```text
Mode: Multi (`/autoquests mode single` để đổi)
```

Không cần lặp lại dòng này ở mỗi lần edit progress; chỉ hiển thị trong message khởi tạo và summary cuối run.

Nếu command cuối cùng dùng phương án compatibility khác, ví dụ `/autoquests-mode`, nội dung gợi ý phải được cập nhật theo command thực tế.

### Các thông báo liên quan khác

Khi user gọi `/autoquests-run`, response ephemeral có thể thêm mode đã chọn:

```text
⏳ Starting a quest run for default…
Mode: Single (`/autoquests mode multi` để đổi)
```

Thông báo token lỗi, token bị pause hoặc token bị xóa không bắt buộc hiển thị mode vì chúng không mô tả một quest run đang hoạt động.

### Localization

Thêm key riêng cho cả tiếng Việt và tiếng Anh, đồng thời bổ sung tiếng Nhật nếu website/bot dùng locale này:

```text
mode_label
mode_single
mode_multi
mode_change_hint
```

Không hardcode chuỗi command trong nhiều nơi. Command hint nên được tạo từ một template i18n thống nhất để tránh lệch giữa progress, summary và response ephemeral.

### Tiêu chí nghiệm thu

- Progress message luôn hiển thị đúng mode tại thời điểm run bắt đầu.
- Summary cuối run hiển thị cùng mode, kể cả khi setting đã được đổi trong lúc run.
- Gợi ý đổi mode chỉ xuất hiện ở message khởi tạo và summary, không lặp ở mỗi lần edit progress.
- Single/Multi được dịch đúng theo locale hiện tại.
- Command trong gợi ý khớp với command thực tế sau khi thiết kế slash command được chốt.
