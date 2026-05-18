from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from google import genai
import os

# 1. إعداد الاتصال بقاعدة البيانات
DATABASE_URL = "postgresql://neondb_owner:npg_hjRuU1mq3vwa@ep-super-art-aqvty1fw-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. إعداد الذكاء الاصطناعي
GEMINI_API_KEY = "AIzaSyAWcgdsX7Tr2pjWUlM6ZSxgMHHmg94DDz4"
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- الجداول في قاعدة البيانات ---
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

# 3. تطبيق FastAPI وإعداد المسارات
app = FastAPI()

# تحديد المسار الصارم والآمن لقراءة المجلد داخل Render
current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

class TicketCreate(BaseModel):
    customer_name: str
    customer_phone: str
    device_model: str
    issue_description: str

# --- المسارات (Endpoints) ---

# واجهة الموظف الرئيسية
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# واجهة تتبع العملاء
@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

# مسار استقبال جهاز جديد وتخزينه وتشخيصه بالذكاء الاصطناعي
@app.post("/create-ticket/")
def create_new_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    try:
        prompt_text = f"أنت خبير صيانة أجهزة محترف. قم بتحليل العطل التالي لجهاز ({ticket_data.device_model}): '{ticket_data.issue_description}'. أعطني تشخيصاً مبدئياً متوقعاً في سطرين فقط باللغة العربية، واقترح قطع الغيار المتوقع تغييرها بوضوح."
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_text,
        )
        diagnosis_result = response.text if response.text else "لم يتمكن الذكاء الاصطناعي من صياغة تشخيص."
    except Exception as e:
        diagnosis_result = f"تم تخطي التشخيص التلقائي مؤقتاً (سبب الفشل: {str(e)[:50]})"

    new_ticket = DeviceTicket(
        customer_name=ticket_data.customer_name,
        customer_phone=ticket_data.customer_phone,
        device_model=ticket_data.device_model,
        issue_description=ticket_data.issue_description,
        status="قيد الاستلام",
        ai_diagnosis=diagnosis_result
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    
    return {
        "status": "success",
        "ticket_id": new_ticket.id,
        "ai_analysis": new_ticket.ai_diagnosis
    }

# مسار جلب بيانات التتبع الفعلي من قاعدة البيانات لصفحة البحث
@app.get("/track/{ticket_id}")
def track_device(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(DeviceTicket).filter(DeviceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="عذراً، رقم التذكرة غير موجود.")
    return {
        "device_model": ticket.device_model,
        "status": ticket.status,
        "ai_diagnosis": ticket.ai_diagnosis
    }
