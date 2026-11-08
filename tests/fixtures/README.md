# Fixtures

- `flutter_mini/` — repo Dart tối thiểu, 6 file, mỗi loại rule một vi phạm, một cycle `domain/user.dart ↔ data/ok_repository.dart`, hai file mồ côi. `rules.json` đi kèm.
- `toolchain.json` — lệnh giả bằng `echo`, `.kt` format cố tình thoát mã 3.
- `make_fake_codegraph.py` — tạo `.codegraph/codegraph.db` theo schema tối thiểu `nodes(id,path)` + `edges(source_id,target_id,kind)`, và một DB schema lạ để test fallback.
