# Sutta — ฐานบาลีในเครื่องสำหรับระบบอื่น

เก็บบาลี Mahāsaṅgīti เป็นต้นฉบับ คำแปลอังกฤษมนุษย์หนึ่งฉบับต่อเอกสารช่วยค้น และสร้างคำแปลไทยเฉพาะช่วงที่เรียกดู โครงการนี้เป็น API ในเครื่อง ไม่มีหน้าแชตและยังไม่ควรเปิดรับอินเทอร์เน็ตโดยตรง

อ่านผลตรวจจริงที่ [docs/VALIDATION.md](docs/VALIDATION.md) สถานะต้นฉบับ การค้น และการแปลแยกกัน การผ่าน tests ไม่ได้รับรองความหมายของคำแปล

## เปิดใช้งานบน Windows

ต้องมี Git, Python 3.13 และ [uv](https://docs.astral.sh/uv/getting-started/installation/) เปิด PowerShell ในโฟลเดอร์ `C:\Code\setup\sutta` ทุกคำสั่งด้านล่างรันจากโฟลเดอร์นี้ ถ้า clone ไว้ที่อื่นให้เปลี่ยนตำแหน่ง

```powershell
Set-Location C:\Code\setup\sutta
uv sync --locked
uv run sutta doctor
uv run sutta fetch
uv run sutta ingest
uv run sutta verify
uv run sutta download-model
```

`doctor` ต้องรายงาน FTS5=true และ sqlite-vec version; `ingest` ต้องได้ 7,288 เอกสารและไม่มี manifest `failed`; `verify` ต้อง exit 0 พร้อม `lossless=true` โมเดลใช้ CPU ไม่ต้องมี GPU ดาวน์โหลดโมเดลครั้งแรกต้องใช้อินเทอร์เน็ต

ทดลองดัชนีและเปรียบเทียบสามวิธีก่อน:

```powershell
uv run sutta index --mode pali --texts-file evaluation/pilot-texts.json --output data/pali-pilot.sqlite
uv run sutta index --texts-file evaluation/pilot-texts.json --output data/index.sqlite
uv run sutta evaluate
uv run sutta storage-report
```

ชุดคำถามใน `evaluation/search-cases.json` เป็น **ร่างให้มนุษย์ตรวจ** คำตอบอ้างอิงที่เลือกด้วย keyword ยังไม่ใช่ gold set ที่รับรองแล้ว ห้ามตั้ง `human_verified=true` เพื่อทำให้ผลผ่านโดยไม่มีการตรวจจริง การวัดบน pilot ยังไม่ใช่คุณภาพทั้งคลัง

สร้างดัชนีเต็มหลังเลือกวิธีจากผลประเมิน:

```powershell
uv run sutta index
uv run sutta search "อริยสัจ"
uv run sutta serve
```

ดัชนีเต็มใช้เวลา CPU มากกว่าการนำเข้าอย่างชัดเจน คำสั่งสร้างไฟล์ `.building.sqlite` ก่อน แล้วเปลี่ยนดัชนีเมื่อทำเสร็จ ดัชนีเก่ายังใช้ได้หากการสร้างใหม่หยุดกลางทาง อย่ารัน `index` สองคำสั่งที่ใช้ output เดียวกันพร้อมกัน ค่าเริ่มต้น float32; ยังไม่เปิด int8 เพราะยังไม่มีผลประเมินที่มนุษย์รับรอง

เปิด [API docs](http://127.0.0.1:8000/docs) ในเบราว์เซอร์ `/health` รายงานแต่ละส่วน และ `/v1/corpus` รายงาน revision กับ coverage ถ้าพอร์ต 8000 ชน ใช้ `uv run sutta serve --port 8001` แล้วเปลี่ยน URL ในตัวอย่าง

## เรียกจาก PowerShell

เปิด PowerShell อีกหน้าต่างในโฟลเดอร์โปรเจกต์ ขณะที่ server ทำงาน:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/v1/corpus
Invoke-RestMethod 'http://127.0.0.1:8000/v1/texts/sn56.11?companion=true'
./examples/client.ps1
```

ตัวอย่าง JavaScript ใช้ Node.js >=18:

```powershell
node examples/client.mjs
```

API:

| Endpoint | Input / output |
|---|---|
| `GET /health` | สถานะฐาน ดัชนี โมเดล และบริการแปลแยกกัน |
| `GET /v1/corpus` | จำนวนเอกสาร/segment หมวด coverage manifest และ revision |
| `GET /v1/texts/{text_id}?companion=true` | บาลีตามลำดับต้นทาง พร้อมอังกฤษถ้าขอ |
| `POST /v1/search` | `{query,top_k:5,category:null,method:"hybrid"}`; top_k สูงสุด 20 |
| `POST /v1/translate` | `{text_id,segment_ids,provider:"ollama"}` |

ค้นรหัสตรง เช่น `sn56.11`, `sn56.11:1.1`, `an1.1:1.1` ได้แม้โมเดลหรือดัชนียังไม่พร้อม รหัสรวมช่วง เช่น `an1.1-10` กับรหัสย่อยจะย้อนกลับไฟล์ต้นทางเดียวกันได้ ผลค้นแสดงรหัส segment บาลีจริง URL revision ภาษาที่ใช้ค้น coverage และบริบทข้างเคียง คะแนนเป็นค่าจัดอันดับ ไม่ใช่ความถูกต้องทางหลักธรรม

การค้นภาษาไทยผ่านเวกเตอร์อังกฤษ; chunks ที่ไม่มีอังกฤษใช้เวกเตอร์บาลีและแสดงสถานะทดลอง รวม FTS5 ด้วย RRF และ glossary ที่มีที่มา ไม่ใช้ LLM แปลคำค้นทุกครั้ง การค้นแบบ `lexical` ใช้ได้โดยไม่โหลด embedding model

## การแปล

ค่าเริ่มต้นใช้ Ollama ในเครื่องกับ `qwen2.5:3b` ซึ่งพบว่าติดตั้งอยู่แล้ว เปลี่ยนโมเดลด้วย `$env:SUTTA_OLLAMA_MODEL='qwen3.5:4b'` ต้องเปิด Ollama และตรวจว่าโมเดลมีอยู่ก่อนเรียก

เลือก segment ต่อเนื่องตามลำดับต้นทาง ความยาวบาลี+อังกฤษรวมไม่เกิน 6,000 ตัวอักษร หากคำแปลอังกฤษขาดแม้หนึ่ง segment จะคืน `translation_unavailable` การแปลผ่านอังกฤษแสดง `via_language=en`, `automatic_translation=true`, `human_review=pending` และแยกจากต้นฉบับเสมอ ผลเก็บ cache ตามเนื้อหา revision provider model และ prompt version

ไม่มี fallback ไปบริการอื่นเงียบ ๆ ผู้เรียกต้องเลือก provider เอง Gemini และ Azure ปิดไว้จนยืนยันบัญชีและราคา อ่าน [docs/PROVIDERS.md](docs/PROVIDERS.md) ก่อนตั้งค่า ห้ามใส่ API key ใน Git, ตัวอย่าง, รายงาน หรือข้อความโจทย์ให้ agent

## ตรวจรับและนำไปต่อ

```powershell
uv run sutta verify
uv run sutta storage-report
git diff --check
git status --short
```

CI ใช้ fixture ที่สร้างเอง ไม่โหลดทั้งพระไตรปิฎกหรือเรียก API เสียเงิน รันทั้ง Windows และ Linux เพิ่มรายงานที่มนุษย์ตรวจแล้วและ commit ที่ตรวจใน PR ดู [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)

ข้อมูล โมเดล และ `.venv` ไม่ commit ใช้ `uv.lock` ติดตั้งซ้ำ เก็บข้อมูลที่ `data/`; ตั้ง `$env:SUTTA_DATA='D:\sutta-data'` เพื่อเปลี่ยนตำแหน่ง และ `$env:SUTTA_MODEL_DIR='D:\sutta-models\e5-small'` เพื่อย้ายโมเดล รายงานพื้นที่แยกฐาน โมเดล dependencies source checkout และ shared cache ของ uv/Hugging Face ส่วน shared cache อาจมีข้อมูลจากโปรเจกต์อื่น จึงไม่ถือว่าทั้งหมดเกิดจาก sutta

## เมื่อไม่ผ่าน

| อาการ | วิธีแก้ |
|---|---|
| Python รุ่นผิด | `uv python install 3.13` แล้ว `uv sync --locked --python 3.13` |
| หา uv ไม่พบ | ติดตั้ง uv จากเอกสารทางการแล้วเปิด PowerShell ใหม่ |
| Windows บอกไฟล์ exe ถูกใช้งาน | หยุด process ของโปรเจกต์ก่อน `uv sync`; ระหว่างรันงานใช้ `uv run --no-sync` เมื่อ lock/environment ตรงกันแล้ว |
| โหลด sqlite extension ไม่ได้ | ใช้ CPython ตามคู่มือ ตรวจ `doctor`; อย่าแทนที่ DLL แบบเดา |
| source revision ผิดหรือมี local changes | ตรวจ `git -C data/upstream status`; รักษางานที่แก้ไว้ แล้วใช้โฟลเดอร์ SUTTA_DATA ใหม่ |
| manifest failed | อ่าน error จากฐาน แก้สาเหตุ และรัน ingest ซ้ำ อย่าข้ามไฟล์เงียบ ๆ |
| ไม่มีดัชนีหรือโมเดล | `download-model` และ `index`; อ่านต้นฉบับและค้นรหัสได้ระหว่างนี้ |
| ค้นไทยไม่ตรง | ตรวจ scope pilot/full และ coverage; เพิ่มคำถามให้ผู้เชี่ยวชาญตรวจ ห้ามเปลี่ยนเฉลยให้ยอมรับคำตอบผิด |
| แปลได้ 503 | เปิด Ollama ตรวจ `/api/tags`; การค้นและอ่านยังใช้งานได้ |
| required checks ไม่ปรากฏ | push workflow และเปิด PR ให้รันอย่างน้อยครั้งหนึ่งก่อนตั้ง branch protection; ต้องมีสิทธิ์ดูแล repo |

แหล่งและสิทธิ์: [docs/SOURCES.md](docs/SOURCES.md) เวอร์ชัน dependencies ที่ติดตั้งจริงอยู่ใน `uv.lock` ตรวจเมื่อ 2026-10-11 ข้อมูลต้นทางตรึง snapshot วันที่ 2026-10-10
