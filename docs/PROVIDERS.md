# ผู้ให้บริการแปลและงบ

ค่าเริ่มต้นเป็น local Ollama ที่ `127.0.0.1:11434` ไม่มีการติดตั้งหรือ pull โมเดลเพิ่มอัตโนมัติ ไม่มีการ retry HTTP อัตโนมัติ ผู้ใช้ที่ retry คำขอจะผ่านการจองงบใหม่ก่อนทุกครั้ง ผลที่ล้มเหลวไม่ถูก cache

## Gemini

ตรวจ free tier ของ project และโมเดลใน [ราคาทางการ](https://ai.google.dev/gemini-api/docs/pricing) ก่อนตั้ง environment ใน PowerShell ที่เปิด API server:

```powershell
$env:SUTTA_GEMINI_FREE_CONFIRMED='1'
$env:GEMINI_API_KEY='<key ที่ไม่บันทึกใน Git>'
$env:SUTTA_GEMINI_MODEL='<model ที่ตรวจแล้วว่ามี free tier>'
uv run sutta serve
```

เลือก `provider=gemini` ใน request Adapter ใช้ generateContent REST API ตรวจ finishReason; ยังไม่มีการทดสอบบัญชีจริง ห้ามตีความว่า flag นี้ตรวจ billing ให้เอง

## Azure

ตรวจเครดิต $40 ว่าใช้กับ deployment ได้จริง ตรวจ endpoint และราคา input/output ของโมเดลจากบัญชีของคุณก่อนตั้งค่า Adapter รับ **chat completions endpoint เต็ม** ที่ deployment รองรับ `model`, `max_tokens`, `api-key` โดยต้องเป็นโมเดลที่คิดราคาตาม input/output tokens ที่กำหนด หากมี reasoning tokens หรือค่าใช้จ่ายอื่น ให้คงปิดไว้จนประเมินราคาและขอบเขต tokens ได้

```powershell
$env:SUTTA_AZURE_CONFIRMED='1'
$env:SUTTA_AZURE_ENDPOINT='https://<resource>.openai.azure.com/openai/v1/chat/completions'
$env:SUTTA_AZURE_KEY='<key>'
$env:SUTTA_AZURE_MODEL='<deployment name>'
$env:SUTTA_AZURE_INPUT_USD_PER_MILLION='<ราคาที่ตรวจจากบัญชีจริง>'
$env:SUTTA_AZURE_OUTPUT_USD_PER_MILLION='<ราคาที่ตรวจจากบัญชีจริง>'
uv run sutta serve
```

จำนวนในราคาเป็น USD ต่อหนึ่งล้าน tokens ไม่ใช่ต่อหนึ่งพัน ตั้งราคาไม่ทราบ/ศูนย์ไม่ได้ ใช้ SQLite `BEGIN IMMEDIATE` จองงบถาวรก่อนส่งคำขอ พร้อมเพดานตลอดอายุ ledger **$35** และเหลือสำรอง $5 จาก $40 ประมาณ input ด้วย UTF-8 bytes + allowance และ output ด้วย max_tokens ต้องยืนยันว่าการคิดราคาของ deployment มีขอบเขตตามนี้ ไม่ใช้กับโมเดลที่มีค่าใช้จ่ายเพิ่มเติมนอกขอบเขต

หาก provider ส่ง usage ที่ครบจะ settle ตามราคาที่ตั้ง หาก timeout/error หรือไม่ส่ง usage จะรักษายอดจอง ไม่ลดงบโดยคาดเดาว่าไม่มีค่าใช้จ่าย บัญชีใช้จ่ายจากบริการอื่นไม่อยู่ในการควบคุมของ API นี้ อย่าลบฐาน/ledger เพื่อรีเซ็ตวงเงินขณะที่ยังใช้บัญชีเดิม

[Azure budget alerts](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets) ช่วยแจ้งเตือนแต่ไม่ได้หยุดค่าใช้จ่าย โครงการไม่สร้าง infrastructure คลาวด์หรือเปิด provider เสียเงินให้เอง

ทดสอบ adapters ผ่าน HTTP mocks ใน CI ก่อน บัญชี Gemini/Azure จริงยังต้องทดสอบหลังตั้งค่า ไม่มีการอ้างว่าผ่านโดยใช้ mock เพียงอย่างเดียว
