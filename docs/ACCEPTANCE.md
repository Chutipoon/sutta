# ตรวจรับและงานที่ต้องมีผู้ตรวจภาษา

คำสั่งทั้งหมดรันจากโฟลเดอร์ repository `C:\Code\setup\sutta` เปลี่ยนตำแหน่งหาก clone ไว้ที่อื่น

## A: ต้นฉบับ

`uv run sutta ingest` ต้องนำเข้าครบ manifest และทำซ้ำได้ `uv run sutta verify` ต้องตรวจ checksum raw bytes, รหัส segment, count alignment และ unit/API tests ผ่าน เก็บรายงาน revision กับจำนวนเอกสาร/segment และ commit code ที่ตรวจ

## B: ค้น

ตรวจ `evaluation/search-cases.json` ทีละคำถามกับบาลี/อังกฤษ ให้ผู้รู้ตรวจ relevant_segments และยืนยันด้วยชื่อผู้ตรวจแยกจากโมเดล แก้คำถามกำกวมก่อนตั้ง human_verified ไม่ใช้ผู้สร้างคำตอบให้คะแนนตัวเอง สร้างชุด held-out เพิ่มที่ไม่ใช้เลือก glossary/โมเดล และมีคำถามส่วนไม่มีอังกฤษแยกด้วย

`uv run sutta evaluate` เปรียบเทียบ Pali vectors, companion vectors, companion+FTS/glossary ใช้ chunk relevance ระดับ segment ไม่ให้แค่ตรงเอกสารเป็นผลผ่าน เกณฑ์ Recall@10 >=85% เฉพาะชุดไทยที่มีเฉลยตรวจแล้ว รายงานส่วนไม่มีอังกฤษต่างหาก ผล pilot ไม่แทน full-corpus benchmark

ถ้า E5-small ไม่ผ่าน ต้องเทียบ [BGE-M3](https://huggingface.co/BAAI/bge-m3) บนคำถามและ corpus เดียวกันก่อนเลือกโมเดล ใช้ harness ที่ให้ผล API เหมือนเดิม และเปลี่ยน dimension/index metadata ตามโมเดล ห้ามเอาเวกเตอร์ต่างโมเดลมาอยู่ดัชนีเดียวกัน รุ่นนี้ยังใช้ E5-small เป็น implementation ตัวแรกและยังไม่รับรอง model selection

```powershell
uv run sutta download-model --embedding bge
uv run sutta index --embedding bge --texts-file evaluation/pilot-texts.json --output data/bge-pilot.sqlite
uv run sutta evaluate --bge data/bge-pilot.sqlite --output docs/model-comparison.json
```

BGE ONNX ใช้ CLS pooling + normalization 1,024 มิติ ไม่เติม E5 prefixes และใช้ chunk token ceiling เดียวกัน โมเดลเปรียบเทียบนี้กินพื้นที่มากกว่า 2 GiB ต้องนับรวมในรายงานพื้นที่ ไม่เลือก BGE เพียงเพราะใหญ่กว่า หากยังไม่ผ่านให้คงสถานะทดลองและปรับ chunk/glossary หรือชุดคำถามตามหลักฐานก่อนสร้างดัชนีเต็ม

ชุดเปรียบเทียบขนาดเล็กที่ใช้ตรวจครั้งแรกเก็บทั้งเอกสาร 10 ฉบับ ครอบคลุมทุกหมวด และมีคำถาม 13 ข้อ ใช้ corpus และคำถามเดียวกันสำหรับทุกโมเดล แยกจากชุด E5 24 เอกสาร/30 คำถาม จึงห้ามนำคะแนนต่างชุดมาเปรียบเทียบกันโดยตรง:

```powershell
uv run sutta index --mode pali --texts-file evaluation/model-texts.json --output data/model-e5-pali.sqlite
uv run sutta index --texts-file evaluation/model-texts.json --output data/model-e5-companion.sqlite
uv run sutta index --embedding bge --texts-file evaluation/model-texts.json --output data/model-bge.sqlite
uv run sutta evaluate --cases evaluation/model-cases.json --pali data/model-e5-pali.sqlite --companion data/model-e5-companion.sqlite --bge data/model-bge.sqlite --output docs/model-comparison.json
```

หากดาวน์โหลด BGE ไฟล์ใหญ่ค้าง ให้ลอง `$env:HF_HUB_DISABLE_XET='1'` และ `$env:SUTTA_RANGE_DOWNLOAD='1'` ก่อน `download-model --embedding bge` ตัวเลือกแบ่งช่วงนี้ตรวจ SHA-256 ก่อนเปิดใช้และทำต่อจากส่วนที่บันทึกได้

ไม่เปิด int8 จนมีผล baseline และ candidate บน gold set เดียวกัน: ลด Recall@10 <=2 จุดเปอร์เซ็นต์และยัง >=85% บันทึกความเร็ว พื้นที่ รุ่นโมเดล และ scope ของดัชนีทุกครั้ง

## C: แปล

`evaluation/translation-cases.json` มี 30 ช่วงสำหรับผู้ตรวจ เติม expected_thai, reviewer และผลตรวจ negation/ศัพท์/รายการ/บริบทก่อนประกาศผ่าน ใช้ local model แปลแล้วให้มนุษย์เทียบกับแหล่งที่มา ไม่ให้โมเดลเดียวกันสร้างเฉลยแล้วให้คะแนน

เปิด Ollama แล้วรัน `uv run sutta evaluate-translation` จากโฟลเดอร์โปรเจกต์เพื่อเก็บผล 30 ช่วงที่ `docs/translation-results.json` แต่ละผลยังเป็น `human_review=pending` คำสั่งนี้ไม่มีการให้คะแนนความหมายเอง ไม่มีการสลับ provider และค่าเริ่มต้นเรียกเฉพาะ local model

ตรวจ API ด้วย `examples/client.ps1` และ `examples/client.mjs` พร้อม server จริง ทดสอบ provider ล่มแล้ว `/v1/texts` และค้นรหัสยังใช้ได้ HTTP mocks ใช้พิสูจน์ cache, ความต่อเนื่องของ segment และ budget ไม่ใช่หลักฐานว่าคำแปลถูกความหมาย

## PR

รัน `uv run sutta verify`, `git diff --check`; บันทึก commit, revision ต้นทาง, คำสั่ง, ผล และสิ่งที่ยังไม่ตรวจ ไม่ commit ฐาน โมเดล keys หรือข้อมูล billing เริ่ม PR ผ่านหน้า GitHub หลัง push branch CI เป็นของ sutta ใช้ fixture ไม่เรียก provider จริง ไม่มี automerge

CI ต้องรันบน GitHub อย่างน้อยครั้งหนึ่งก่อนตั้ง required checks ตามสิทธิ์ repository ถ้าไม่สามารถ push ได้ ให้รายงานว่า workflow เตรียมไว้และยังไม่ผ่านการตรวจบน GitHub
