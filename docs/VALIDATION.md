# ผลตรวจรับ Sutta

ตรวจบน Windows / PowerShell ระหว่าง 2026-10-10 ถึง 2026-10-11 Code commit ที่ตรวจ: `c29622bd313ab000b9e3ecdc1efd39e1c4cb9350` เอกสารและรายงานฉบับส่งมอบ commit เพิ่มหลังจากนี้โดยไม่เปลี่ยน implementation

**พร้อมใช้เป็นฐานอ่านบาลีในเครื่องและระบบทดลอง API การค้นไทยและคำแปลยังไม่ผ่านการรับรองใช้งานจริง**

| ส่วน | สถานะ | หลักฐาน |
|---|---|---|
| ต้นฉบับ | ผ่านการตรวจข้อมูลครบ snapshot ที่กำหนด | 7,288 เอกสาร / 447,071 segments; raw bytes ตรง Git blobs |
| คำแปลมนุษย์ประกอบ | นำเข้าและจับคู่แล้ว พร้อม coverage | 4,693 เอกสารมีอังกฤษ; 208,627 segments จับคู่ได้ |
| อ่านและค้นรหัส | ใช้งานได้ | Unit tests และ HTTP smoke รวมรหัสย่อยในไฟล์ช่วงรวม |
| ค้นไทยเชิงความหมาย | ทดลอง ยังต่ำกว่าเป้าหมาย | มี E5 และ BGE-M3 pilot; ยังไม่ใช้ gold set ที่มนุษย์ตรวจ |
| แปลไทยตามคำขอ | ทดลอง รอผู้ตรวจภาษา | Ollama ตอบครบ 30 ช่วง; ไม่มีผลตรวจความหมายโดยมนุษย์ |
| Gemini / Azure | เตรียม adapters; ยังไม่ทดสอบบัญชีจริง | HTTP mocks ผ่าน; ไม่มีการเรียก API เสียเงิน |
| CI | เตรียม workflow; ยังไม่รันบน GitHub | GitHub CLI ยังไม่ได้เข้าสู่ระบบ; repository ยังไม่ push |

## A — ความถูกต้องของต้นฉบับ

Revision `83589dcd2b23ed6b5fcb02361d958f5b8a9ef057`:

- พระสูตร 5,764 เอกสาร พระวินัย 422 และพระอภิธรรม 1,102 รวม 7,288
- Manifest imported 7,288 / failed 0
- Coverage ระดับเอกสาร: complete 683 / partial 4,010 / none 2,595
- Coverage ระดับ segment: 208,627 จาก 447,071 (รวมชื่อเรื่องและหัวข้อด้วย)
- อ่าน bytes จาก Git commit โดยตรง ป้องกัน LF/CRLF conversion บน Windows
- เทียบบาลี 7,288 ไฟล์และคำแปล 4,693 ไฟล์กับ Git blobs ตรงทั้งหมด
- Import ซ้ำไม่เพิ่มเอกสาร รักษาลำดับ JSON และ Unicode/ช่องว่างในค่า segment

ดู [corpus-report.json](corpus-report.json) และ [git-provenance-report.json](git-provenance-report.json)

## B — การค้น

ชุดใหญ่ของการทดลองเริ่มต้นมี 24 เอกสาร / 30 คำถามที่ยังไม่ได้ตรวจเฉลยโดยมนุษย์ ส่วนที่มีอังกฤษ 28 คำถาม: E5 Pali 3.6%, E5 companion 25.0%, E5 hybrid 28.6% ส่วนไม่มีอังกฤษ 2 คำถามได้ 0% ทั้งสามวิธี ตัวเลขเป็นผลบน candidate anchors ไม่ใช่ความแม่นยำทางหลักธรรม ดู [search-results.json](search-results.json)

ชุดเปรียบเทียบโมเดลขนาดเล็กใช้ทั้งเอกสาร 10 ฉบับ ครอบคลุมทุกหมวด และคำถามเดียวกัน 13 ข้อทุกวิธี ส่วนมีอังกฤษ 11 ข้อ ส่วนไม่มีอังกฤษ 2 ข้อ:

| วิธี | Recall@10 มีอังกฤษ | ไม่มีอังกฤษ |
|---|---:|---:|
| E5 Pali | 18.2% | 0% |
| E5 companion | 54.5% | 0% |
| E5 companion + FTS/glossary | 72.7% | 0% |
| BGE-M3 companion | 72.7% | 50% |
| BGE-M3 companion + FTS/glossary | 63.6% | 50% |

**ไม่มีวิธีที่ผ่าน 85% และเฉลยยังไม่ human-verified** จึงยังไม่เลือกโมเดลสำหรับ production ไม่สร้างดัชนีเวกเตอร์ครบทั้งคลัง และไม่เปิด int8 ดัชนีที่ API ใช้ขณะส่งมอบคือ E5 pilot 24 เอกสาร อ่านและค้นรหัสได้ทั้งคลัง แต่ semantic search ครอบคลุมเฉพาะ pilot

ห้ามเปรียบเทียบคะแนนของชุด 24 เอกสารกับชุด 10 เอกสารโดยตรง ไม่ใช้คะแนนชุดเล็กแทน full corpus และไม่เปลี่ยน relevant_segments ให้ยอมรับผลผิดเพื่อทำคะแนนผ่าน ต้องตรวจเฉลย เพิ่ม held-out cases และปรับการค้นตามข้อผิดพลาดที่ตรวจแล้วก่อนเลือกโมเดล

เวลา index ที่วัดบนเครื่องนี้ (ไม่ใช่ SLA): E5 Pali 10 เอกสาร/153 chunks 43.10 วินาที; E5 companion 10 เอกสาร/139 chunks 39.54 วินาที; BGE-M3 companion 10 เอกสาร/139 chunks 428.88 วินาที BGE ใช้พื้นที่โมเดลมากกว่า 2 GiB ผลทดลองยังไม่ให้เหตุผลเพียงพอเลือกโมเดลใหญ่

ดู [model-comparison.json](model-comparison.json) คำสั่งทำซ้ำอยู่ใน [ACCEPTANCE.md](ACCEPTANCE.md)

## C — การแปลและการเชื่อมต่อ

`uv run sutta evaluate-translation` ใช้ Ollama `qwen2.5:3b` ในเครื่อง ตอบครบ 30 ช่วงที่ต่างกัน เก็บผลและ provenance ที่ [translation-results.json](translation-results.json) ทุกผลเป็น automatic / experimental / human_review=pending / via_language=en

ผู้ตรวจต้องเติมเฉลยและผลตรวจศัพท์ ปฏิเสธ รายการธรรม และบริบทก่อนรับรอง การตอบได้ครบไม่ใช่การแปลถูกครบ บาลีที่ไม่มีอังกฤษคืน `translation_unavailable` ตามขอบเขตที่กำหนด

PowerShell และ JavaScript clients ผ่านการเรียก HTTP จริง ทั้งห้า endpoints ผ่าน smoke tests รวมค้น unknown ID แล้วได้รายการว่าง ไม่มีการสร้างอ้างอิงจากโมเดล ดู [api-smoke.json](api-smoke.json)

Tests ตรวจบริการแปลล่ม/ตอบผิดรูปแบบแล้วอ่านและค้นรหัสยังได้, cache, ช่วง segment ต่อเนื่อง, เงื่อนไขเปิด cloud adapters, reserve งบก่อนเรียก, retry หลัง timeout, usage settlement และคำขอจองงบพร้อมกัน การทดสอบ cloud ทั้งหมดใช้ mocks ไม่ยืนยันเครดิต ราคา หรือ deployment จริง

## สภาพแวดล้อมและการตรวจอัตโนมัติ

Python 3.13.14, SQLite 3.50.4, sqlite-vec 0.1.9, uv 0.11.24 ใช้ ONNX CPU เวอร์ชัน dependencies ทั้งหมดอยู่ใน `uv.lock`

จากโฟลเดอร์ `C:\Code\setup\sutta`:

```powershell
uv sync --locked
uv run sutta doctor
uv run sutta ingest
uv run sutta verify
git diff --check
```

Lint ผ่าน, tests 28 ผ่าน และ verify ต้นฉบับ 7,288 เอกสารแบบ lossless รวมเทียบ Git blobs ผ่าน เพิ่ม test ที่พิสูจน์ว่าอ่าน canonical LF bytes ได้แม้ working tree เป็น CRLF

ติดตั้งใหม่ด้วย `uv sync --locked` ใน `data/fresh-install` แล้วตรวจซ้ำ tests 28 ผ่านบน Windows โฟลเดอร์นี้ใช้เฉพาะ fixture ไม่มี corpus/model ของจริง มีการจำลอง unused import เพื่อยืนยัน `verify` exit 1 แล้วเอา probe ออกและตรวจกลับสู่สถานะผ่าน

CI Windows/Linux เตรียมไว้ แต่ไม่มีการอ้างว่ารันบน GitHub แล้ว และยังไม่ได้ตั้ง required checks ไม่มี automerge

## พื้นที่และข้อที่ต้องทำต่อ

ดู [storage-report.json](storage-report.json): แยก corpus, ดัชนีแต่ละชุด, E5/BGE models, dependencies, upstream checkout, validation folder และ shared caches ตัวเลขเป็น logical file bytes; hardlinks อาจใช้พื้นที่กายภาพร่วมกัน ไม่บวก shared cache ทั้งหมดเป็นพื้นที่ใหม่ของโปรเจกต์

โมเดล BGE เป็นโมเดลเปรียบเทียบที่เก็บไว้ทำซ้ำ ไม่ใช่โมเดลที่ประกาศผ่านคุณภาพ ต้นฉบับถูกบีบอัดแบบไม่สูญเสียและไม่เก็บ decoded text ซ้ำใน chunk table

งานที่เหลือก่อนรับรองระบบค้นไทย: ตรวจ gold set โดยมนุษย์ ปรับวิธีค้นให้ผ่าน 85% บนข้อมูลที่ตรวจแล้ว เลือกโมเดล สร้าง/ตรวจดัชนีเต็ม และตรวจคำแปล 30 ช่วงด้านความหมาย ก่อนใช้ cloud ต้องยืนยันบัญชีและราคาจริง ก่อน push/ตรวจ CI ต้องเข้าสู่ระบบ GitHub

ระบบตรวจอนุมัติอัตโนมัติปฏิเสธการลบ `data/fresh-install` โดยแจ้งเพียง “blocked by policy” จึงเก็บโฟลเดอร์ทดสอบไว้ใน data ที่ไม่ commit และรวมขนาดในรายงานพื้นที่
