# ที่มาและขอบเขต

ต้นทาง [Bilara published ณ commit ที่ตรึง](https://github.com/suttacentral/bilara-data/tree/83589dcd2b23ed6b5fcb02361d958f5b8a9ef057) ใช้ `root/pli/ms/` ทั้งหมด ชื่อฉบับใน `_author.json` คือ Mahāsaṅgīti Tipiṭaka Buddhavasse 2500 ไม่อ้างว่าเป็นฉบับที่ถูกที่สุดทุกประเพณี

SuttaCentral ระบุฐาน Pali source เป็น public domain ใน [pali repository](https://github.com/suttacentral/pali) ซึ่งเป็นหลักฐานคนละส่วนกับคำแปล ส่วน [Bilara LICENSE](https://github.com/suttacentral/bilara-data/blob/83589dcd2b23ed6b5fcb02361d958f5b8a9ef057/LICENSE.md) อุทิศคำแปลที่สร้างใน Bilara และสนับสนุนโดย SuttaCentral เป็น CC0 ไม่ใช้ข้อความนี้อ้างสิทธิ์แทนบาลีทั้งหมด อ่าน [นโยบาย licensing](https://suttacentral.net/licensing) หากนำข้อมูลออกเผยแพร่ร่วมกับเนื้อหาอื่น

เลือกคำแปล published ลำดับ Sujato → Brahmali → Kelly → Soma → Suddhaso → Kovilo หนึ่งฉบับต่อไฟล์ ลำดับเป็นความสม่ำเสมอ ไม่ใช่คะแนนผู้แปล เก็บ raw bytes บีบอัดเพียงครั้งเดียวต่อฉบับ SHA-256 ของ bytes และ revision คำแปลทั้งหมดคงอยู่ใน raw source แต่ API companion คืนเฉพาะ segment ที่จับคู่กับบาลีได้และไม่ว่าง

ไฟล์ช่วงรวมและช่วงย่อยตรวจขอบเขตตัวเลข ไม่ผูกชื่อไฟล์กับ prefix ของ segment แบบเท่ากันอย่างเดียว รักษา JSON insertion order ไม่เรียง segment แบบ string ต้นฉบับไม่ normalize; ใช้ NFC เฉพาะดัชนี FTS

Coverage นับทุก segment รวมชื่อเรื่องและหัวข้อ หากไม่มีคำแปลหัวข้อบางส่วนจะเป็น partial แม้เนื้อความหลักแปลครบ รายงานทั้งจำนวนเอกสารและจำนวน segment ไม่ใช้เปอร์เซ็นต์ระดับไฟล์แทนคุณภาพค้นไทย

Glossary เริ่มต้น: ทุกข์/dukkha/suffering, อริยสัจ/ariyasacca/noble truth, มรรค/magga/path อ้าง [SN56.11](https://suttacentral.net/sn56.11/en/sujato); อนัตตา/anattā/not-self อ้าง [SN22.59](https://suttacentral.net/sn22.59/en/sujato) เป็นคำช่วยค้น ต้องตรวจคำถามจริงและเพิ่มคำพร้อมที่มาก่อนขยาย

Embedding [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) ใช้ ONNX CPU, prefix `query:`/`passage:`, attention-mask mean pooling และ L2 normalization 384 มิติ Chunk จำกัด 384 tokens รวม prefix โดยใช้ tokenizer เดียวกับโมเดล ไม่มี overlap; segment ยาวแบ่งพร้อม character offsets ในภาษาที่ใช้ค้น ผล API คืนบาลีเต็ม segment ที่อ้างไว้ ไม่อ้าง offsets อังกฤษว่าเป็น offsets บาลี

โมเดลใช้ MIT ตาม model card ส่วน code ของโครงการใช้ MIT คำแปลไทยอัตโนมัติไม่ใช่ต้นฉบับและไม่ใช่คำแปลที่ SuttaCentral รับรอง
