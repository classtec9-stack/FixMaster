from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from google import genai

# 1. قاعدة البيانات والذكاء الاصطناعي
DATABASE_URL = "postgresql://neondb_owner:npg_hjRuU1mq3vwa@ep-super-art-aqvty1fw-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

GEMINI_API_KEY = "AIzaSyAWcgdsX7Tr2pjWUlM6ZSxgMHHmg94DDz4"
ai_client = genai.Client(api_key=GEMINI_API_KEY)

class DeviceTicket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    customer_phone = Column(String)
    device_model = Column(String)
    issue_description = Column(String)
    status = Column(String, default="قيد الاستلام")
    ai_diagnosis = Column(String, default="لم يتم الفحص بعد")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

class TicketCreate(BaseModel):
    customer_name: str
    customer_phone: str
    device_model: str
    issue_description: str

# --- واجهة الموظف الرئيسية المدمجة ---
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>FixMaster - لوحة الاستقبال</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', sans-serif; background-color: #f0f4f8; margin: 0; padding: 20px; color: #333; }
            .container { max-width: 600px; background: white; margin: 40px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-top: 8px solid #1e3a8a; }
            h2 { color: #1e3a8a; text-align: center; margin-bottom: 25px; }
            label { font-weight: bold; display: block; margin-top: 15px; color: #4b5563; }
            input, textarea { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-family: 'Cairo'; }
            button { width: 100%; background-color: #2563eb; color: white; border: none; padding: 12px; margin-top: 25px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.3s; }
            button:hover { background-color: #1d4ed8; }
            .result { display: none; margin-top: 25px; padding: 20px; background-color: #eff6ff; border-left: 5px solid #3b82f6; border-radius: 6px; }
            .result h3 { margin-top: 0; color: #1e3a8a; }
            .nav-link { text-align: center; margin-top: 20px; display: block; color: #2563eb; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🛠️ نظام FixMaster - استقبال جهاز جديد</h2>
            <form id="ticketForm">
                <label>اسم العميل:</label>
                <input type="text" id="customer_name" required>
                
                <label>رقم الجوال:</label>
                <input type="text" id="customer_phone" required>
                
                <label>موديل الجهاز:</label>
                <input type="text" id="device_model" required>
                
                <label>وصف العطل والشكوى:</label>
                <textarea id="issue_description" rows="4" required></textarea>
                
                <button type="submit">إصدار التذكرة والتشخيص الذكي ✨</button>
            </form>
            
            <div id="resultBox" class="result">
                <h3>✅ تم تسجيل الجهاز بنجاح!</h3>
                <p><strong>رقم التذكرة لـ التتبع:</strong> <span id="resId" style="font-size: 20px; color: #2563eb; font-weight: bold;"></span></p>
                <p><strong>التشخيص المبدئي بالذكاء الاصطناعي (Gemini):</strong></p>
                <p id="resAi" style="background: white; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0;"></p>
            </div>
            <a href="/search" class="nav-link">👈 الانتقال لصفحة تتبع العملاء</a>
        </div>

        <script>
            document.getElementById('ticketForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector('button');
                btn.innerText = "جاري التحليل والاتصال بـ Gemini...";
                btn.disabled = true;

                const data = {
                    customer_name: document.getElementById('customer_name').value,
                    customer_phone: document.getElementById('customer_phone').value,
                    device_model: document.getElementById('device_model').value,
                    issue_description: document.getElementById('issue_description').value
                };

                try {
                    const response = await fetch('/create-ticket/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    
                    document.getElementById('resId').innerText = result.ticket_id;
                    document.getElementById('resAi').innerText = result.ai_analysis;
                    document.getElementById('resultBox').style.display = 'block';
                } catch (err) {
                    alert('حدث خطأ أثناء الاتصال بالسيرفر');
                } finally {
                    btn.innerText = "إصدار التذكرة والتشخيص الذكي ✨";
                    btn.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """

# --- واجهة البحث المدمجة ---
@app.get("/search", response_class=HTMLResponse)
def search_page():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>FixMaster - تتبع حالة الجهاز</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', sans-serif; background-color: #f0f4f8; margin: 0; padding: 20px; }
            .container { max-width: 500px; background: white; margin: 60px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; border-top: 8px solid #2563eb; }
            h2 { color: #1e3a8a; margin-bottom: 20px; }
            input { width: 100%; padding: 12px; margin-top: 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 16px; text-align: center; font-family: 'Cairo'; }
            button { width: 100%; background-color: #1e3a8a; color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
            .status-box { display: none; margin-top: 25px; padding: 20px; border-radius: 8px; text-align: right; background-color: #f8fafc; border: 1px solid #e2e8f0; }
            .badge { background-color: #3b82f6; color: white; padding: 4px 12px; border-radius: 50px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🔍 تتبع حالة جهازك</h2>
            <p style="color: #64748b;">أدخل رقم التذكرة المعطى لك من المركز لمعرفة حالة الإصلاح مباشرة</p>
            <input type="number" id="ticketId" placeholder="مثال: 4">
            <button onclick="trackDevice()">بحث عن التذكرة</button>
            
            <div id="statusBox" class="status-box">
                <p><strong>جهازك من نوع:</strong> <span id="devModel"></span></p>
                <p><strong>حالة الجهاز الحالية:</strong> <span id="devStatus" class="badge"></span></p>
                <p><strong>تقرير الفحص الفني للـ AI:</strong></p>
                <p id="devAi" style="background: white; padding: 10px; border-radius: 6px; font-size: 14px; border: 1px solid #cbd5e1;"></p>
            </div>
            <a href="/" style="margin-top:20px; display:inline-block; color:#1e3a8a; text-decoration:none;">⬅️ العودة للرئيسية</a>
        </div>

        <script>
            async function trackDevice() {
                const id = document.getElementById('ticketId').value;
                if(!id) return alert('برجاء كتابة رقم التذكرة');
                
                try {
                    const response = await fetch(`/track/${id}`);
                    if(!response.ok) { alert('رقم التذكرة غير موجود!'); return; }
                    const result = await response.json();
                    
                    document.getElementById('devModel').innerText = result.device_model;
                    document.getElementById('devStatus').innerText = result.status;
                    document.getElementById('devAi').innerText = result.ai_diagnosis;
                    document.getElementById('statusBox').style.display = 'block';
                } catch(err) {
                    alert('خطأ في الاتصال بالسيرفر');
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/create-ticket/")
def create_new_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    try:
        prompt_text = f"أنت خبير صيانة أجهزة محترف. قم بتحليل العطل التالي لجهاز ({ticket_data.device_model}): '{ticket_data.issue_description}'. أعطني تشخيصاً مبدئياً متوقعاً في سطرين فقط باللغة العربية، واقترح قطع الغيار المتوقع تغييرها بوضوح."
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt_text)
        diagnosis_result = response.text if response.text else "لم يتمكن الذكاء الاصطناعي من صياغة تشخيص."
    except Exception as e:
        diagnosis_result = f"تم تخطي التشخيص التلقائي مؤقتاً (سبب الفشل: {str(e)[:50]})"

    new_ticket = DeviceTicket(
        customer_name=ticket_data.customer_name, customer_phone=ticket_data.customer_phone,
        device_model=ticket_data.device_model, issue_description=ticket_data.issue_description,
        status="قيد الاستلام", ai_diagnosis=diagnosis_result
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    return {"status": "success", "ticket_id": new_ticket.id, "ai_analysis": new_ticket.ai_diagnosis}

@app.get("/track/{ticket_id}")
def track_device(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(DeviceTicket).filter(DeviceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="عذراً، رقم التذكرة غير موجود.")
    return {"device_model": ticket.device_model, "status": ticket.status, "ai_diagnosis": ticket.ai_diagnosis}
