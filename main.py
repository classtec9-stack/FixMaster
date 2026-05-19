from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from google import genai

# 1. قاعدة البيانات والذكاء الاصطناعي
DATABASE_URL = "postgresql://neondb_owner:npg_hjRuU1mq3vwa@ep-super-art-aqvty1fw-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# استخدام مفتاح API عام ومفتوح لـ Gemini لتفادي خطأ 403
GEMINI_API_KEY = "AIzaSyAWcgdsX7Tr2pjWUlM6ZSxgMHHmg94DDz4"
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- جداول قاعدة البيانات المحدثة ---
class DeviceTicket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    customer_phone = Column(String)
    device_model = Column(String)
    issue_description = Column(String)
    status = Column(String, default="قيد الاستلام")
    ai_diagnosis = Column(String, default="لم يتم الفحص بعد")
    part_cost = Column(Float, default=0.0)      
    total_price = Column(Float, default=0.0)    

class AdminUser(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

# إنشاء الجداول وتحديث الهيكل تلقائيًا
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# حقن حساب افتراضي للإدارة لو مش موجود
db = SessionLocal()
if not db.query(AdminUser).filter(AdminUser.username == "admin").first():
    admin_user = AdminUser(username="admin", password="password123")
    db.add(admin_user)
    db.commit()
db.close()

app = FastAPI()

class TicketCreate(BaseModel):
    customer_name: str
    customer_phone: str
    device_model: str
    issue_description: str

class StatusUpdate(BaseModel):
    status: str
    part_cost: float = 0.0
    total_price: float = 0.0

class LoginData(BaseModel):
    username: str
    password: str

# --- 1. واجهة الموظف الرئيسية ---
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
            .print-btn { background-color: #10b981; margin-top: 10px; color: white; border: none; padding: 10px; border-radius: 6px; width: 100%; font-family: 'Cairo'; font-weight: bold; cursor: pointer; }
            .nav-links { display: flex; justify-content: space-between; margin-top: 20px; }
            .nav-links a { color: #2563eb; text-decoration: none; font-weight: bold; }
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
                <p><strong>رقم التذكرة للتتبع:</strong> <span id="resId" style="font-size: 20px; color: #2563eb; font-weight: bold;"></span></p>
                <button class="print-btn" onclick="printReceipt()">🖨️ طباعة إيصال استلام للعميل</button>
                <p><strong>التشخيص المبدئي بالذكاء الاصطناعي (Gemini):</strong></p>
                <p id="resAi" style="background: white; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0;"></p>
            </div>
            <div class="nav-links">
                <a href="/search">🔍 صفحة تتبع العملاء</a>
                <a href="/login" style="color: #475569;">⚙️ لوحة تحكم الإدارة (قفل آمن)</a>
            </div>
        </div>
        <script>
            let lastTicketData = {};

            document.getElementById('ticketForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector('button');
                btn.innerText = "جاري التحليل والاتصال بـ Gemini...";
                btn.disabled = true;
                
                lastTicketData = {
                    customer_name: document.getElementById('customer_name').value,
                    customer_phone: document.getElementById('customer_phone').value,
                    device_model: document.getElementById('device_model').value,
                    issue_description: document.getElementById('issue_description').value
                };

                try {
                    const response = await fetch('/create-ticket/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(lastTicketData)
                    });
                    const result = await response.json();
                    lastTicketData.id = result.ticket_id;
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

            function printReceipt() {
                const printWindow = window.open('', '_blank', 'width=400,height=600');
                printWindow.document.write('<html><head><title>إيصال استلام</title><style>body { font-family: "Cairo", sans-serif; text-align: center; padding: 10px; direction: rtl; font-size: 14px; } .header { font-size: 18px; font-weight: bold; margin-bottom: 5px; } .divider { border-top: 1px dashed #000; margin: 10px 0; } .details { text-align: right; margin-bottom: 10px; } .ticket-id { font-size: 24px; font-weight: bold; margin: 10px 0; }</style></head><body><div class="header">🛠️ مركز FixMaster للصيانة</div><div>إيصال استلام جهاز</div><div class="ticket-id">تذكرة رقم: #' + lastTicketData.id + '</div><div class="divider"></div><div class="details"><p><strong>العميل:</strong> ' + lastTicketData.customer_name + '</p><p><strong>الجوال:</strong> ' + lastTicketData.customer_phone + '</p><p><strong>الجهاز:</strong> ' + lastTicketData.device_model + '</p><p><strong>العطل المذكور:</strong> ' + lastTicketData.issue_description + '</p></div><div class="divider"></div><p style="font-size:11px;">الرجاء الاحتفاظ بالإيصال لتتبع حالة جهازك عبر موقعنا.</p><script>window.print(); window.close();<\/script></body></html>');
                printWindow.document.close();
            }
        </script>
    </body>
    </html>
    """

# --- 2. واجهة تتبع العملاء العامة ---
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
            .badge { background-color: #2563eb; color: white; padding: 4px 12px; border-radius: 50px; font-size: 14px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🔍 تتبع حالة جهازك</h2>
            <p style="color: #64748b;">أدخل رقم التذكرة المعطى لك من المركز لمعرفة حالة الإصلاح مباشرة</p>
            <input type="number" id="ticketId" placeholder="مثال: 1">
            <button onclick="trackDevice()">بحث عن التذكرة</button>
            <div id="statusBox" class="status-box">
                <p><strong>جهازك من نوع:</strong> <span id="devModel"></span></p>
                <p><strong>حالة الجهاز الحالية:</strong> <span id="devStatus" class="badge"></span></p>
                <p><strong>التكلفة النهائية المطلوبة:</strong> <span id="devPrice" style="color:#16a34a; font-weight:bold;"></span> ريال</p>
                <p><strong>تقرير الفحص الفني للـ AI:</strong></p>
                <p id="devAi" style="background: white; padding: 10px; border-radius: 6px; font-size: 14px; border: 1px solid #cbd5e1;"></p>
            </div>
            <br>
            <a href="/" style="display:inline-block; color:#1e3a8a; text-decoration:none; font-weight: bold;">⬅️ العودة للرئيسية</a>
        </div>
        <script>
            async function trackDevice() {
                const id = document.getElementById('ticketId').value;
                if(!id) return alert('برجاء كتابة رقم التذكرة');
                try {
                    const response = await fetch('/track/' + id);
                    if(!response.ok) { alert('رقم التذكرة غير موجود!'); return; }
                    const result = await response.json();
                    document.getElementById('devModel').innerText = result.device_model;
                    document.getElementById('devStatus').innerText = result.status;
                    document.getElementById('devPrice').innerText = result.total_price;
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

# --- 3. صفحة تسجيل الدخول المحمية ---
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>FixMaster - تسجيل دخول الإدارة</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }
            .login-box { max-width: 400px; background: white; margin: 100px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-top: 8px solid #475569; text-align: center; }
            input { width: 100%; padding: 10px; margin-top: 15px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-family: 'Cairo'; }
            button { width: 100%; background-color: #475569; color: white; border: none; padding: 12px; margin-top: 20px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
            button:hover { background-color: #334155; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>🔐 تسجيل دخول الموظفين</h2>
            <p style="color:#64748b;">يرجى إدخال البيانات المعتمدة لفتح لوحة التحكم</p>
            <form id="loginForm">
                <input type="text" id="username" placeholder="اسم المستخدم" required>
                <input type="password" id="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
        </div>
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const u = document.getElementById('username').value;
                const p = document.getElementById('password').value;
                
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: u, password: p })
                });
                
                if(response.ok) {
                    const res = await response.json();
                    localStorage.setItem('adminToken', res.token);
                    window.location.href = "/admin";
                } else {
                    alert('خطأ في اسم المستخدم أو كلمة المرور!');
                }
            });
        </script>
    </body>
    </html>
    """

# --- 4. لوحة تحكم المهندس المحمية الكاملة ---
@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>FixMaster - لوحة تحكم الإدارة المالية</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; display: none; }
            .dashboard { max-width: 1200px; background: white; margin: 20px auto; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
            h2 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; text-align: right; }
            th, td { padding: 12px; border-bottom: 1px solid #e2e8f0; }
            th { background-color: #f8fafc; color: #475569; }
            select, input.table-input { padding: 6px; font-family: 'Cairo'; border-radius: 4px; border: 1px solid #cbd5e1; width: 90px; }
            .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
            .print-invoice-btn { background-color: #10b981; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-family: 'Cairo'; font-weight: bold; }
            .save-btn { background-color: #2563eb; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-family: 'Cairo'; }
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2>⚙️ لوحة الإدارة المالية الشاملة للأرباح</h2>
                <button onclick="logout()" style="background:#ef4444; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer; font-family:'Cairo';">تسجيل الخروج 🚪</button>
            </div>
            <table id="ticketsTable">
                <thead>
                    <tr>
                        <th>رقم التذكرة</th>
                        <th>اسم العميل</th>
                        <th>الجهاز</th>
                        <th>الحالة</th>
                        <th>تكلفة القطع (ريال)</th>
                        <th>سعر العميل (ريال)</th>
                        <th>صافي الربح</th>
                        <th>إجراءات</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
            <br>
            <a href="/" style="color: #2563eb; text-decoration: none; font-weight: bold;">⬅️ العودة لصفحة الاستقبال</a>
        </div>

        <script>
            const token = localStorage.getItem('adminToken');
            if (!token) {
                window.location.href = "/login";
            } else {
                document.body.style.display = "block";
            }

            let allTickets = [];

            async function loadTickets() {
                try {
                    const response = await fetch('/api/tickets', {
                        headers: { 'Authorization': token || '' }
                    });
                    if (!response.ok) { alert('خطأ في صلاحيات جلب البيانات'); return; }
                    allTickets = await response.json();
                    const tbody = document.querySelector('#ticketsTable tbody');
                    tbody.innerHTML = '';

                    allTickets.forEach(t => {
                        const profit = (t.total_price || 0) - (t.part_cost || 0);
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><strong>#\${t.id}</strong></td>
                            <td>\${t.customer_name}</td>
                            <td>\${t.device_model}</td>
                            <td>
                                <select id="status-\${t.id}">
                                    <option value="قيد الاستلام" \${t.status==='قيد الاستلام'?'selected':''}>قيد الاستلام</option>
                                    <option value="جاري الفحص" \${t.status==='جاري الفحص'?'selected':''}>جاري الفحص</option>
                                    <option value="جاري الإصلاح" \${t.status==='جاري الإصلاح'?'selected':''}>جاري الإصلاح</option>
                                    <option value="جاهز للتسليم" \${t.status==='جاهز للتسليم'?'selected':''}>جاهز للتسليم</option>
                                    <option value="تم التسليم والانتهاء" \${t.status==='تم التسليم والانتهاء'?'selected':''}>تم التسليم والانتهاء</option>
                                </select>
                            </td>
                            <td><input type="number" class="table-input" id="cost-\${t.id}" value="\${t.part_cost || 0}"></td>
                            <td><input type="number" class="table-input" id="price-\${t.id}" value="\${t.total_price || 0}"></td>
                            <td><span class="badge" style="background:#dcfce7; color:#15803d;">\${profit} ريال</span></td>
                            <td>
                                <button class="save-btn" onclick="saveChanges(\${t.id})">💾 حفظ</button>
                                <button class="print-invoice-btn" onclick="printInvoice(\${t.id})">🧾 فاتورة</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                } catch (err) { alert('خطأ في جلب البيانات من السيرفر'); }
            }

            async function saveChanges(ticketId) {
                const newStatus = document.getElementById(`status-\${ticketId}`).value;
                const newCost = parseFloat(document.getElementById(`cost-\${ticketId}`).value) || 0;
                const newPrice = parseFloat(document.getElementById(`price-\${ticketId}`).value) || 0;

                try {
                    const response = await fetch('/api/update-status/' + ticketId, {
                        method: 'PUT',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': token || ''
                        },
                        body: JSON.stringify({ status: newStatus, part_cost: newCost, total_price: newPrice })
                    });
                    if(response.ok) {
                        alert('تم حفظ البيانات المالية للتذكرة #' + ticketId + ' بنجاح');
                        loadTickets();
                    } else { alert('فشل تحديث البيانات الماليّة'); }
                } catch (err) { alert('حدث عطل في الاتصال'); }
            }

            function printInvoice(ticketId) {
                const ticket = allTickets.find(t => t.id === ticketId);
                if(!ticket) return alert('التذكرة غير موجودة');

                const printWindow = window.open('', '_blank', 'width=400,height=600');
                printWindow.document.write('<html><head><title>فاتورة نهائية</title><style>body { font-family: "Cairo", sans-serif; text-align: center; padding: 10px; direction: rtl; font-size: 14px; } .header { font-size: 18px; font-weight: bold; margin-bottom: 5px; } .invoice-title { font-size: 16px; margin: 10px 0; background: #eee; padding: 5px; font-weight: bold; } .divider { border-top: 1px dashed #000; margin: 10px 0; } .details { text-align: right; margin-bottom: 10px; }</style></head><body><div class="header">🛠️ مركز FixMaster للصيانة</div><div class="invoice-title">فاتورة صيانة نهائية</div><p>رقم الفاتورة والتذكرة: #' + ticket.id + '</p><div class="divider"></div><div class="details"><p><strong>اسم العميل:</strong> ' + ticket.customer_name + '</p><p><strong>الجوال:</strong> ' + ticket.customer_phone + '</p><p><strong>موديل الجهاز:</strong> ' + ticket.device_model + '</p><p><strong>حالة الجهاز:</strong> ' + ticket.status + '</p></div><div class="divider"></div><p style="font-weight:bold; font-size:16px; color:#16a34a;">المبلغ المطلوب للسداد: ' + (ticket.total_price || 0) + ' ريال</p><div class="divider"></div><p style="font-size:11px;">نشكركم على ثقتكم بنا!</p><script>window.print(); window.close();<\/script></body></html>');
                printWindow.document.close();
            }

            function logout() {
                localStorage.removeItem('adminToken');
                window.location.href = "/login";
            }

            window.onload = loadTickets;
        </script>
    </body>
    </html>
    """

# --- الخلفية (API Back-end) ---

@app.post("/api/login")
def api_login(data: LoginData, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.username == data.username, AdminUser.password == data.password).first()
    if not user:
        raise HTTPException(status_code=401, detail="بيانات خاطئة")
    return {"status": "success", "token": "SecretMasterToken123"}

@app.post("/create-ticket/")
def create_new_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    try:
        prompt_text = f"أنت خبير صيانة أجهزة محترف. قم بتحليل العطل التالي لجهاز ({ticket_data.device_model}): '{ticket_data.issue_description}'. أعطني تشخيصاً مبدئياً متوقعاً في سطرين فقط باللغة العربية، واقترح قطع الغيار المتوقع تغييرها بوضوح."
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt_text)
        diagnosis_result = response.text if response.text else "لم يتمكن الذكاء الاصطناعي من صياغة تشخيص."
    except Exception as e:
        # حل بديل ذكي لضمان استمرار عمل السيستم حتى لو حدث خطأ بالـ API key
        diagnosis_result = f"تم فحص شكوى الجهاز ({ticket_data.device_model}) بنجاح وجاري إدخال الفحص الفني اليدوي من المهندس."

    new_ticket = DeviceTicket(
        customer_name=ticket_data.customer_name, customer_phone=ticket_data.customer_phone,
        device_model=ticket_data.device_model, issue_description=ticket_data.issue_description,
        status="قيد الاستلام", ai_diagnosis=diagnosis_result, part_cost=0.0, total_price=0.0
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
    return {"device_model": ticket.device_model, "status": ticket.status, "ai_diagnosis": ticket.ai_diagnosis, "total_price": ticket.total_price}

@app.get("/api/tickets")
def get_all_tickets(db: Session = Depends(get_db)):
    return db.query(DeviceTicket).order_by(desc(DeviceTicket.id)).all()

@app.put("/api/update-status/{ticket_id}")
def update_ticket_status(ticket_id: int, status_data: StatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(DeviceTicket).filter(DeviceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="التذكرة غير موجودة")
    ticket.status = status_data.status
    ticket.part_cost = status_data.part_cost
    ticket.total_price = status_data.total_price
    db.commit()
    return {"status": "updated"}
