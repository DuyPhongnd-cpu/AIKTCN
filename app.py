import os
import sys
import base64
import requests
import time
import re
import json
import threading
from datetime import datetime
from functools import wraps
from flask import Flask, render_template_string, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename

try:
    import pypdf
    import docx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except:
    pass

# PostgreSQL integration
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PG = True
except ImportError:
    HAS_PG = False

APP_NAME = "AI DUY PHONG"
APP_VERSION = "35.0 (7 AI Power Hub: Crawler & Coder Added)"

# --- TẢI BIẾN MÔI TRƯỜNG ---
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8", errors="ignore") as f_env:
            for line in f_env:
                line = line.strip().lstrip('\ufeff')
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    except:
        pass

VILAO_API_KEY = os.environ.get("VILAO_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "7594576473")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Vtc@123")

# Local AI Ollama
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# PostgreSQL Config
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG_HOST = os.environ.get("POSTGRES_HOST", "")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_USER = os.environ.get("POSTGRES_USER", "postgres")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
PG_DB = os.environ.get("POSTGRES_DB", "ai_hub_db")

# Router Models Mapping (7 AI Models)
MODELS_MAP = {
    "openai": os.environ.get("MODEL_OPENAI", "gpt-4o"),
    "document_ai": os.environ.get("MODEL_DOC", "occ/claude-fable-5"),
    "claude": os.environ.get("MODEL_CLAUDE", "occ/claude-fable-5-1"),
    "gemini": os.environ.get("MODEL_GEMINI", "rge/models/gemini-3.5-flash"),
    "deepseek": os.environ.get("MODEL_DEEPSEEK", "deepseek-chat"),
    "crawler": os.environ.get("MODEL_CRAWLER", "rge/models/gemini-3.5-flash"),
    "coder": os.environ.get("MODEL_CODER", "occ/claude-fable-5")
}

# --- THƯ MỤC PERSISTENT VOLUME TRÊN UBUNTU / COOLIFY ---
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DB_FILE = os.path.join(DATA_DIR, "hub_database.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, "exports"), exist_ok=True)

app = Flask(__name__)
app.secret_key = "vtc_digital_secret_key_2026"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- XỬ LÝ LƯU TRỮ POSTGRESQL & PERSISTENT VOLUME ---
def get_pg_connection():
    if not HAS_PG:
        return None
    try:
        if DATABASE_URL:
            return psycopg2.connect(DATABASE_URL)
        elif PG_HOST:
            return psycopg2.connect(
                host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB, connect_timeout=3
            )
    except Exception as e:
        print(f"[PostgreSQL] Thông báo: Không kết nối được Postgres ({e}), dùng Persistent JSON Volume.")
    return None

def init_postgres():
    conn = get_pg_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hub_state (
                        id VARCHAR(50) PRIMARY KEY,
                        state_data JSONB NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
            print("[PostgreSQL] Khởi tạo bảng hub_state thành công!")
        except Exception as e:
            print("[PostgreSQL] Lỗi init table:", e)
        finally:
            conn.close()

init_postgres()

def load_db():
    conn = get_pg_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT state_data FROM hub_state WHERE id = %s;", ('main_workspace',))
                row = cur.fetchone()
                if row and row.get('state_data'):
                    return row['state_data']
        except Exception as e:
            print("[PostgreSQL] Lỗi load:", e)
        finally:
            conn.close()

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_db(data):
    conn = get_pg_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO hub_state (id, state_data, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE 
                    SET state_data = EXCLUDED.state_data, updated_at = NOW();
                """, ('main_workspace', json.dumps(data, ensure_ascii=False)))
                conn.commit()
        except Exception as e:
            print("[PostgreSQL] Lỗi save:", e)
        finally:
            conn.close()

    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[Storage] Lỗi lưu file JSON:", e)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('idx'))
        else:
            error = "Sai mật khẩu quản trị!"
    return render_template_string(HTML_LOGIN, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/api/sync', methods=['GET', 'POST'])
@login_required
def api_sync():
    if request.method == 'POST':
        data = request.json or {}
        save_db(data)
        return jsonify({"status": "ok", "storage": "PostgreSQL + Persistent Volume"})
    else:
        return jsonify(load_db())

# --- LÕI XỬ LÝ FILE & AI ---
class FileProcessor:
    @staticmethod
    def process_file(file_path: str, filename: str) -> dict:
        ext = filename.split(".")[-1].lower()
        if ext in ["png", "jpg", "jpeg", "webp", "gif"]:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                return {"type": "image", "content": b64, "ext": ext}
        text_content = ""
        try:
            if ext == "pdf":
                import pypdf
                with open(file_path, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    for page in reader.pages: text_content += page.extract_text() + "\n"
            elif ext in ["docx", "doc"]:
                import docx
                doc = docx.Document(file_path)
                for para in doc.paragraphs: text_content += para.text + "\n"
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()
        except: text_content = "[Lỗi trích xuất định dạng]"
        return {"type": "text", "content": text_content.strip()[:60000]}

class VilaoRouterAPI:
    def ask(self, model_key: str, user_content: list, chat_history: list, system_prompt: str, ai_name_tag: str) -> str:
        enhanced_system = system_prompt + f"\n\nQUY TẮC:\n1. Tên đại diện của bạn là {ai_name_tag}.\n2. Kế thừa toàn bộ ngữ cảnh trao đổi trước đó.\n3. Trình bày chuẩn xác chuyên môn cao, sử dụng Markdown phân cấp."
        
        messages = [{"role": "system", "content": enhanced_system}]
        for h in chat_history: messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_content})

        # XỬ LÝ LOCAL AI OLLAMA
        if model_key == "ollama":
            hosts_to_try = [
                OLLAMA_HOST,
                "http://172.17.0.1:11434",
                "http://host.docker.internal:11434",
                "http://127.0.0.1:11434",
                "http://localhost:11434"
            ]
            text_only = "".join([i["text"] for i in user_content if i["type"] == "text"])
            ollama_msgs = [{"role": "system", "content": enhanced_system}]
            for h in chat_history: ollama_msgs.append({"role": h["role"], "content": h["content"]})
            ollama_msgs.append({"role": "user", "content": text_only})
            payload = {"model": OLLAMA_MODEL, "messages": ollama_msgs, "stream": False}
            
            last_err = ""
            for h in hosts_to_try:
                try:
                    url = f"{h.rstrip('/')}/api/chat"
                    r = requests.post(url, json=payload, timeout=60)
                    if r.status_code == 200:
                        return r.json()["message"]["content"]
                except Exception as e:
                    last_err = str(e)
            return f"🤖 [Local Ollama]: Chưa kết nối được Ollama trên Host ({last_err}). Vui lòng kiểm tra tiến trình `ollama serve` port 11434."

        # XỬ LÝ CLOUD ROUTER (VILAO)
        real_model_name = MODELS_MAP.get(model_key, "gpt-4o")
        if not VILAO_API_KEY: 
            return "🤖 LỖI: Chưa cấu hình VILAO_API_KEY trong file .env hoặc tab Environment trên Coolify."
            
        try:
            url = "https://api.vilao.ai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {VILAO_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": real_model_name, "messages": messages}
            res = requests.post(url, headers=headers, json=payload, timeout=120)
            if res.status_code == 200: 
                rdata = res.json()
                if "choices" in rdata and len(rdata["choices"]) > 0: return rdata["choices"][0]["message"]["content"]
                elif "error" in rdata: return f"🤖 [Trạm Router Từ Chối]: {rdata['error']}"
                else: return f"🤖 [Dữ liệu phản hồi]: {res.text}"
            return f"🤖 [Router Error {res.status_code}]: {res.text}"
        except Exception as e: return f"🤖 Lỗi Mạng Router Core: {str(e)}"

class AIAgentCore:
    def process(self, message, model_key="openai", text_files="", image_files=None, target_url="", chat_history=None):
        if image_files is None: image_files = []
        if chat_history is None: chat_history = []
        
        lmsg = message.lower()
        ai_name = "OpenAI GPT-4o"
        avatar = "fa-robot"; avatar_color = "#059669"
        
        # Nhận diện @mention cho 7 AI Models
        if "@crawler" in lmsg or "@cào" in lmsg or "@cao" in lmsg or "@web" in lmsg:
            model_key = "crawler"; ai_name = "Web Crawler AI (Cào Dữ Liệu & Tin Tức)"; avatar = "fa-spider"; avatar_color = "#06b6d4"
        elif "@coder" in lmsg or "@code" in lmsg or "@lập trình" in lmsg or "@laptrinh" in lmsg:
            model_key = "coder"; ai_name = "Code Architect AI (Kỹ Sư Lập Trình & Debug)"; avatar = "fa-laptop-code"; avatar_color = "#ec4899"
        elif "@claude" in lmsg or "@xử lý văn bản" in lmsg or "@hsmt" in lmsg or "@vanban" in lmsg:
            model_key = "claude"; ai_name = "Claude 3.5 Sonnet (Văn Thư & HSMT)"; avatar = "fa-brain"; avatar_color = "#7c3aed"
        elif "@gpt" in lmsg or "@openai" in lmsg:
            model_key = "openai"; ai_name = "OpenAI GPT-4o (Thư Ký Tổng Hợp)"; avatar = "fa-robot"; avatar_color = "#059669"
        elif "@gemini" in lmsg:
            model_key = "gemini"; ai_name = "Google Gemini Pro (Tra Cứu & Đa Phương Tiện)"; avatar = "fa-bolt"; avatar_color = "#0284c7"
        elif "@deepseek" in lmsg:
            model_key = "deepseek"; ai_name = "DeepSeek V3 (Toán & Thuật Toán)"; avatar = "fa-fire"; avatar_color = "#ea580c"
        elif "@ollama" in lmsg or "@local" in lmsg:
            model_key = "ollama"; ai_name = "Local AI (Ollama Offline)"; avatar = "fa-server"; avatar_color = "#059669"
        else:
            if model_key == "crawler":
                ai_name = "Web Crawler AI (Cào Dữ Liệu & Tin Tức)"; avatar = "fa-spider"; avatar_color = "#06b6d4"
            elif model_key == "coder":
                ai_name = "Code Architect AI (Kỹ Sư Lập Trình & Debug)"; avatar = "fa-laptop-code"; avatar_color = "#ec4899"
            elif model_key in ["claude", "document_ai"]:
                ai_name = "Claude 3.5 Sonnet (Văn Thư & HSMT)"; avatar = "fa-brain"; avatar_color = "#7c3aed"
            elif model_key == "gemini":
                ai_name = "Google Gemini Pro (Tra Cứu & Đa Phương Tiện)"; avatar = "fa-bolt"; avatar_color = "#0284c7"
            elif model_key == "deepseek":
                ai_name = "DeepSeek V3 (Toán & Thuật Toán)"; avatar = "fa-fire"; avatar_color = "#ea580c"
            elif model_key == "ollama":
                ai_name = "Local AI (Ollama Offline)"; avatar = "fa-server"; avatar_color = "#059669"
                
        c_msg = re.sub(r'@[a-zÀ-ỹ0-9_]+', '', message, count=2, flags=re.IGNORECASE).strip()
        if not c_msg: c_msg = message

        # Trích xuất URL tự động và cào nội dung nếu có link
        url_context = ""
        found_urls = re.findall(r'(https?://[^\s]+)', c_msg)
        if target_url and target_url not in found_urls:
            found_urls.append(target_url)

        for u in found_urls[:2]:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                res = requests.get(u, headers=headers, timeout=12)
                text = re.sub(r'<[^>]+>', ' ', res.text)
                clean_web = re.sub(r'\s+', ' ', text).strip()[:18000]
                url_context += f"\n=== DỮ LIỆU CÀO TRỰC TUYẾN TỪ LINK: {u} ===\n{clean_web}\n"
            except Exception as e:
                url_context += f"\n[Lỗi cào dữ liệu từ link {u}: {str(e)}]\n"
            
        full_text_prompt = c_msg
        if url_context: full_text_prompt += f"\n\n{url_context}"
        if text_files: full_text_prompt += f"\n\n--- TÀI LIỆU LƯU TRỮ VĨNH VIỄN CỦA DỰ ÁN ---\n{text_files[:80000]}"
        
        user_content_payload = [{"type": "text", "text": full_text_prompt}]
        for img in image_files[:10]:
            mime = f"image/{img['ext']}" if img['ext'] != 'jpg' else "image/jpeg"
            user_content_payload.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img['content']}"}})
            
        sys_pr = "Bạn là hệ thống Liên Hợp AI Duy Phong. Đang trong phiên làm việc của Trưởng phòng Kỹ thuật Công nghệ VTC."
        ans = VilaoRouterAPI().ask(model_key, user_content_payload, chat_history, sys_pr, ai_name)
        return {"answer": ans, "model": model_key, "ai_name": ai_name, "avatar": avatar, "avatar_color": avatar_color}

agent_core = AIAgentCore()

def telegram_polling():
    if not TELEGRAM_BOT_TOKEN:
        return
    offset = 0
    poll_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chat_histories = {} 
    while True:
        try:
            res = requests.get(poll_url, params={"offset": offset, "timeout": 30}, timeout=40)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("result", []):
                    offset = item["update_id"] + 1
                    msg = item.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")
                    if str(chat_id) != str(TELEGRAM_ADMIN_CHAT_ID) and TELEGRAM_ADMIN_CHAT_ID:
                        requests.post(send_url, json={"chat_id": chat_id, "text": "❌ Lỗi: Miễn phận sự."})
                        continue
                    if text:
                        if chat_id not in chat_histories: chat_histories[chat_id] = []
                        if "/clear" in text:
                            chat_histories[chat_id] = []; requests.post(send_url, json={"chat_id": chat_id, "text": "✅ Đã xóa trí nhớ Telegram"})
                            continue
                        requests.post(send_url, json={"chat_id": chat_id, "text": "⏳ *Đang họp phòng ban AI...*", "parse_mode": "Markdown"})
                        reply = agent_core.process(text, model_key="openai", chat_history=chat_histories[chat_id][-4:])
                        chat_histories[chat_id].append({"role": "user", "content": text})
                        chat_histories[chat_id].append({"role": "assistant", "content": reply["answer"]})
                        requests.post(send_url, json={"chat_id": chat_id, "text": f"✅ **{reply['ai_name']}**:\n\n{reply['answer'][:3800]}", "parse_mode": "Markdown"})
        except:
            time.sleep(5)

if TELEGRAM_BOT_TOKEN:
    threading.Thread(target=telegram_polling, daemon=True).start()

# --- HTML GIAO DIỆN ĐĂNG NHẬP ---
HTML_LOGIN = r"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><title>Đăng nhập AI Hub VTC</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
body{font-family:'Roboto',sans-serif;background:#0f172a;color:#f8fafc;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
.login-box{background:#1e293b;padding:40px;border-radius:15px;box-shadow:0 10px 30px rgba(0,0,0,0.5);text-align:center;border:1px solid #334155;width:360px;}
input{width:100%;padding:15px;margin:20px 0;border-radius:8px;border:1px solid #475569;background:#0b0f19;color:white;outline:none;box-sizing:border-box;font-size:15px;}
input:focus{border-color:#3b82f6;}
button{width:100%;background:#3b82f6;color:white;border:none;padding:15px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:16px;transition:0.2s;}
button:hover{background:#2563eb;}
.error{color:#ef4444;font-size:13px;margin-bottom:15px;}
</style></head>
<body>
<div class="login-box">
    <i class="fa-solid fa-brain" style="font-size:45px;color:#3b82f6;margin-bottom:15px;"></i>
    <h2 style="margin:0 0 10px 0;">AI WORKSPACE HUB</h2>
    <div style="font-size:12.5px;color:#10b981;font-weight:bold;">VTC DIGITAL - PHÒNG KTCN</div>
    {% if error %}<div class="error" style="margin-top:15px;">{{ error }}</div>{% endif %}
    <form method="POST">
        <input type="password" name="password" placeholder="Nhập Mật Khẩu (Mặc định: Vtc@123)" required>
        <button type="submit"><i class="fa-solid fa-lock-open"></i> ĐĂNG NHẬP HỆ THỐNG</button>
    </form>
</div>
</body></html>"""

# --- HTML GIAO DIỆN CHÍNH (7 AI MODELS) ---
HTML_UI = r"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><title>AI DUY PHONG V35 (7-AI POWER HUB)</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
body{font-family:'Roboto',sans-serif;background:#2b2d31;color:#f2f3f5;margin:0;display:flex;flex-direction:column;height:100vh;overflow:hidden;}
header{background:#1e1f22;padding:12px 20px;border-bottom:1px solid #111214;font-weight:700;font-size:16px;display:flex;align-items:center;justify-content:space-between;box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index:10;}
.btn-clear{background:#da373c;color:white;border:none;padding:8px 15px;border-radius:6px;font-size:13px;font-weight:bold;cursor:pointer;transition:0.2s;display:flex;align-items:center;gap:6px;}
.btn-clear:hover{background:#a12828;}
.btn-logout{background:transparent;color:#949ba4;border:1px solid #3f4147;padding:6px 12px;border-radius:6px;font-size:12px;cursor:pointer;text-decoration:none;}
.btn-logout:hover{background:#da373c;color:white;border-color:#da373c;}
.main{display:flex;flex:1;overflow:hidden;}
.sidebar{width:360px;background:#232428;border-right:1px solid #1e1f22;padding:15px;display:flex;flex-direction:column;gap:15px;overflow-y:auto;}
.chat-container{flex:1;display:flex;flex-direction:column;background:#313338;}
.chat-header{background:#2b2d31;border-bottom:1px solid #1e1f22;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;}
.chat-title{font-size:15px;font-weight:bold;color:#f2f3f5;display:flex;align-items:center;gap:10px;}
.file-dashboard{font-size:12px;color:#949ba4;display:flex;flex-direction:column;align-items:flex-end;gap:4px;}
.btn-clear-small{background:#da373c;color:white;border:none;padding:4px 10px;border-radius:4px;font-size:11px;font-weight:bold;cursor:pointer;transition:0.2s;}
.btn-clear-small:hover{background:#a12828;}
.chat-history{flex:1;padding:25px 30px;overflow-y:auto;display:flex;flex-direction:column;gap:20px;}
.msg{max-width:90%;padding:15px 18px;border-radius:12px;line-height:1.6;font-size:14.5px;position:relative; word-wrap:break-word;}
.msg-user{align-self:flex-end;background:#5865f2;color:white;border-bottom-right-radius:2px;box-shadow:0 3px 5px rgba(0,0,0,0.1);}
.msg-user .author{font-size:11px;font-weight:bold;color:#c9cdfb;margin-bottom:5px;border-bottom:1px dashed rgba(255,255,255,0.3);padding-bottom:5px;}
.msg-ai{align-self:flex-start;background:#2b2d31;color:#dbdee1;border-bottom-left-radius:2px;border:1px solid #1e1f22; width:100%;box-shadow:0 3px 6px rgba(0,0,0,0.05);}
.msg-ai pre{background:#1e1f22;padding:12px;border-radius:8px;overflow-x:auto;}
.msg-ai h1,.msg-ai h2,.msg-ai h3{color:#5865f2;margin-top:10px;margin-bottom:5px;}
.model-badge{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:bold;margin-bottom:10px;border-bottom:1px dashed #3f4147;padding-bottom:8px;width:100%;}
.export-panel{display:flex;gap:10px;margin-top:15px;border-top:1px dashed #3f4147;padding-top:10px;justify-content:flex-end;}
.export-badge, .export-txt{cursor:pointer;font-size:12px;color:#23a559;background:#1e1f22;padding:8px 15px;border-radius:8px;border:1px solid #23a559;font-weight:bold;transition:0.2s;}
.export-txt{color:#f59e0b;border-color:#f59e0b;}
.export-badge:hover{background:#23a559;color:white;}
.export-txt:hover{background:#f59e0b;color:white;}
.input-area{background:#2b2d31;padding:12px 25px;border-top:1px solid #1e1f22;display:flex;flex-direction:column;gap:8px;}
.ai-card{background:#2b2d31;padding:8px 12px;border-radius:8px;cursor:pointer;border:1px solid #1e1f22;display:flex;align-items:center;gap:10px;font-size:13px;transition:0.2s;margin-bottom:5px;}
.ai-card:hover{border-color:#3b82f6;background:#313338;}
.ai-card.active{border-color:#3b82f6;background:rgba(59,130,246,0.15);font-weight:bold;}
.ai-card-title{font-weight:700;font-size:13px;}
.ai-card-desc{font-size:11px;color:#949ba4;}
.chat-input-wrapper{display:flex;gap:12px;align-items:flex-end;}
textarea{flex:1;background:#383a40;color:#dbdee1;padding:12px 15px;border:1px solid #383a40;border-radius:10px;outline:none;resize:vertical;font-size:15px;min-height:50px;max-height:180px;}
textarea:focus{border-color:#5865f2;}
.btn-send{background:#5865f2;color:#fff;border:none;padding:12px 22px;border-radius:10px;cursor:pointer;font-weight:bold;font-size:15px;height:50px;transition:0.2s;}
.btn-send:hover{background:#4752c4;}
.file-btn{position:relative;background:#10b981;border:1px solid #059669;padding:12px;border-radius:10px;cursor:pointer;color:white;display:flex;align-items:center;height:50px;box-sizing:border-box;transition:0.2s;}
.file-btn:hover{background:#059669;}
.file-btn input{position:absolute;top:0;left:0;width:100%;height:100%;opacity:0;cursor:pointer;}
.sb-title{color:#949ba4;font-size:11.5px;font-weight:700;border-bottom:1px solid #3f4147;padding-bottom:6px;margin-bottom:6px;}

/* Tree CSS */
.tree-container { display:flex; flex-direction:column; gap:3px; flex:1; overflow-y:auto; overflow-x:hidden;}
.tree-node{display:flex; align-items:center; justify-content:space-between; padding:7px 10px; border-radius:6px; cursor:pointer; color:#dbdee1; transition:0.2s; font-size:13px; border:1px solid transparent;}
.tree-node:hover{background:#2b2d31; border-color:#3f4147;}
.tree-node.active{background:#5865f2; color:white; border-color:#5865f2; font-weight:bold;}
.tree-node.active .tree-actions i{color:#e2e8f0;}
.tree-node-content{display:flex; align-items:center; gap:8px; flex:1; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;}
.tree-actions{display:none; gap:8px; font-size:11.5px; color:#949ba4;}
.tree-node:hover .tree-actions{display:flex;}
.tree-actions i:hover{color:#f1c40f;}
.btn-add-folder{background:transparent; border:1px dashed #3f4147; color:#949ba4; padding:8px; text-align:center; border-radius:8px; cursor:pointer; font-size:12px; margin-top:8px; transition:0.2s; font-weight:bold;}
.btn-add-folder:hover{border-color:#5865f2; color:#5865f2;}
.web-tab{display:flex;gap:8px;border-bottom:1px solid #334155;padding-bottom:8px;}
.wbtn{background:#334155;border:1px solid #475569;color:#cbd5e1;padding:6px 12px;border-radius:15px;font-size:12px;cursor:pointer;font-weight:bold;transition:0.2s;}
.wbtn.active{background:#3b82f6;color:white;border-color:#3b82f6;}
.url-input{width:100%;padding:10px;border-radius:8px;border:1px solid #3b82f6;background:#0f172a;color:white;display:none;margin-bottom:8px;font-size:13.5px;outline:none;}
</style></head><body>
<header>
    <div><i class="fa-solid fa-layer-group" style="color:#5865f2;"></i> AI WORKSPACE HUB V35 (7 AI MODELS & CRAWLER)</div>
    <div style="display:flex;align-items:center;gap:15px;">
        <span style="font-size:12px;color:#10b981;font-weight:bold;"><i class="fa-solid fa-database"></i> PostgreSQL & Persistent Storage</span>
        <a href="/logout" class="btn-logout"><i class="fa-solid fa-right-from-bracket"></i> Đăng Xuất</a>
    </div>
</header>
<div class="main">
    <div class="sidebar">
        <!-- ĐỘI NGŨ NHÂN SỰ 7 AI MODELS -->
        <div>
            <div class="sb-title">DANH SÁCH NHÂN SỰ (THẾ MẠNH CHUYÊN MÔN)</div>
            
            <div class="ai-card active" onclick="sel('openai',this)">
                <i class="fa-solid fa-robot" style="color:#10b981;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">OpenAI GPT-4o</div>
                    <div class="ai-card-desc">Thư ký tổng hợp, lập luận & logic đa năng</div>
                </div>
            </div>
            
            <div class="ai-card" onclick="sel('claude',this)">
                <i class="fa-solid fa-brain" style="color:#a855f7;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">Claude 3.5 Sonnet</div>
                    <div class="ai-card-desc">Chuyên viên Văn thư, Soát xét Hợp đồng & HSMT</div>
                </div>
            </div>

            <!-- 2 CHÚ AI MỚI BỔ SUNG -->
            <div class="ai-card" onclick="sel('crawler',this)" style="border-left: 3px solid #06b6d4;">
                <i class="fa-solid fa-spider" style="color:#06b6d4;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">Web Crawler AI</div>
                    <div class="ai-card-desc">Cào dữ liệu web, bóc tách giá cả & tin tức</div>
                </div>
            </div>

            <div class="ai-card" onclick="sel('coder',this)" style="border-left: 3px solid #ec4899;">
                <i class="fa-solid fa-laptop-code" style="color:#ec4899;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">Code Architect AI</div>
                    <div class="ai-card-desc">Chuyên gia Lập trình, Debug & Viết mã nguồn</div>
                </div>
            </div>
            
            <div class="ai-card" onclick="sel('gemini',this)">
                <i class="fa-solid fa-bolt" style="color:#38bdf8;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">Google Gemini Pro</div>
                    <div class="ai-card-desc">Tra cứu Web, Tài liệu khủng (2M) & Đa phương tiện</div>
                </div>
            </div>
            
            <div class="ai-card" onclick="sel('deepseek',this)">
                <i class="fa-solid fa-fire" style="color:#f59e0b;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">DeepSeek V3</div>
                    <div class="ai-card-desc">Tính toán số liệu, Thuật toán & Tài chính</div>
                </div>
            </div>
            
            <div class="sb-title" style="margin-top:10px;color:#10b981;border-color:#10b981;">LOCAL AI (NỘI BỘ VTC OFFLINE)</div>
            <div class="ai-card" onclick="sel('ollama',this)" style="border:1px dashed #10b981;">
                <i class="fa-solid fa-server" style="color:#10b981;font-size:17px;"></i>
                <div>
                    <div class="ai-card-title">Local Ollama Server</div>
                    <div class="ai-card-desc">Chạy offline trên máy chủ VTC, bảo mật 100%</div>
                </div>
            </div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;">💡 Gõ <b>@crawler, @coder, @claude</b> trong chat để giao việc nhanh.</div>
        </div>
        
        <!-- CÂY THƯ MỤC CHUYÊN SÂU -->
        <div style="display:flex; flex-direction:column; flex:1; min-height:0; margin-top:5px;">
            <div class="sb-title">CÂY DỰ ÁN & HỒ SƠ (POSTGRESQL SYNC)</div>
            <div class="tree-container" id="treeList"><i class="fa-solid fa-spinner fa-spin"></i> Đang nạp cơ sở dữ liệu...</div>
            <div class="btn-add-folder" onclick="addFolder()"><i class="fa-solid fa-folder-plus"></i> Tạo Thư Mục Cha (Dự Án)</div>
        </div>
    </div>
    
    <div class="chat-container">
        <div class="chat-header">
            <div class="chat-title" id="chatTitle"><i class="fa-solid fa-comments"></i> Chọn phòng làm việc...</div>
            <div class="file-dashboard">
                <span id="savedFilesList">📁 Data Đầu Vào: Đang tải...</span>
                <button onclick="clearChatData()" class="btn-clear-small"><i class="fa-solid fa-trash-can"></i> Xóa Data Phòng này</button>
            </div>
        </div>
        
        <div class="chat-history" id="chatArea"></div>
        
        <div class="input-area">
            <div class="web-tab">
                <button class="wbtn active" onclick="sTab('vanban',this)"><i class="fa-solid fa-pen-nib"></i> Soạn Thảo</button>
                <button class="wbtn" onclick="sTab('link',this)"><i class="fa-solid fa-globe"></i> Đọc Link Website</button>
            </div>
            <input type="text" id="url" class="url-input" placeholder="Dán Link trang Web tin tức, tài liệu vào đây...">
            <div class="chat-input-wrapper">
                <div class="file-btn" title="Tải File lên Phòng làm việc này">
                    <i class="fa-solid fa-paperclip"></i>
                    <input type="file" id="f" multiple onchange="hf()">
                </div>
                <textarea id="q" placeholder="Ra lệnh cho nhóm AI (Có thể dán Link Website thẳng vào chat)..."></textarea>
                <button class="btn-send" id="b" onclick="snd()"><i class="fa-solid fa-paper-plane"></i> GỬI LỆNH</button>
            </div>
            <div id="fl" style="color:#10b981;font-size:12px;font-weight:bold;">Sẵn sàng nhận lệnh. 7 Chú AI trực chiến 24/7.</div>
        </div>
    </div>
</div>

<script>
let treeData = [
    { id: "fold_1", name: "📁 CÁC DỰ ÁN", type: "folder", isOpen: true, children: [
        { id: "chat_0", name: "📝 Việc hàng ngày", type: "chat" },
        { id: "chat_1", name: "📝 Hồ sơ mời thầu (HSMT)", type: "chat" }
    ]}
];
let catHists = {}; let catHtmls = {}; let dbExports = {};
let curC = null; let lastSelM = "openai"; let tab="vanban";

// Khởi động đồng bộ hóa Server State (Postgres + Persistent Volume)
fetch('/api/sync').then(r=>r.json()).then(d => {
    if(d.tree) treeData = d.tree;
    if(d.hists) catHists = d.hists;
    if(d.htmls) catHtmls = d.htmls;
    if(d.exports) dbExports = d.exports;
    
    updateTreeHTML();
    let ninit = findNode(treeData, "chat_0");
    if(ninit) setCat("chat_0", ninit.name);
    else {
        let first = getFirstChat(treeData);
        if(first) setCat(first.id, first.name);
    }
});

function getFirstChat(nodes) {
    for(let n of nodes) {
        if(n.type === "chat") return n;
        if(n.children) { let res = getFirstChat(n.children); if(res) return res; }
    }
    return null;
}

function svSt(){
    if(!curC) return;
    catHtmls[curC] = document.getElementById('chatArea').innerHTML;
    fetch('/api/sync', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tree: treeData, hists: catHists, htmls: catHtmls, exports: dbExports})
    });
}
function sTab(t,e){ tab=t; document.querySelectorAll('.wbtn').forEach(c=>c.classList.remove('active')); e.classList.add('active'); document.getElementById('url').style.display = (t==='link')?'block':'none'; }

function renderTree(nodes, padding = 0) {
    let h = "";
    nodes.forEach((n) => {
        if (n.type === "folder") {
            let icon = n.isOpen ? "fa-folder-open" : "fa-folder";
            h += `<div class="tree-node" style="padding-left:${padding}px">
                    <div class="tree-node-content" onclick="toggleFolder('${n.id}')">
                        <i class="fa-solid ${icon}" style="color:#f1c40f"></i> <span style="font-weight:bold;">${n.name}</span>
                    </div>
                    <div class="tree-actions">
                        <i class="fa-solid fa-plus" title="Thêm phòng nhỏ" onclick="addChild('${n.id}', event)"></i>
                        <i class="fa-solid fa-pen" title="Đổi tên" onclick="renNode('${n.id}', event)"></i>
                        <i class="fa-solid fa-trash" title="Xóa thư mục" onclick="delNode('${n.id}', event)"></i>
                    </div>
                  </div>`;
            if (n.isOpen && n.children) h += renderTree(n.children, padding + 15);
        } else {
            let act = (n.id === curC) ? "active" : "";
            h += `<div class="tree-node ${act}" style="padding-left:${padding}px" onclick="setCat('${n.id}', '${n.name}')">
                    <div class="tree-node-content">
                        <i class="fa-solid fa-file-pen" style="color:#94a3b8"></i> <span>${n.name}</span>
                    </div>
                    <div class="tree-actions">
                        <i class="fa-solid fa-pen" title="Đổi tên" onclick="renNode('${n.id}', event)"></i>
                        <i class="fa-solid fa-trash" title="Xóa" onclick="delNode('${n.id}', event)"></i>
                    </div>
                  </div>`;
        }
    }); return h;
}

function findNode(nodes, id) {
    for(let n of nodes) {
        if(n.id === id) return n;
        if(n.children) { let found = findNode(n.children, id); if(found) return found; }
    } return null;
}
function deleteNode(nodes, id) {
    for(let i=0; i<nodes.length; i++) {
        if(nodes[i].id === id) { nodes.splice(i, 1); return true; }
        if(nodes[i].children) { if(deleteNode(nodes[i].children, id)) return true; }
    } return false;
}
function updateTreeHTML() { document.getElementById('treeList').innerHTML = renderTree(treeData); }

function addFolder() {
    let name = prompt("Nhập tên Thư mục Bố (Khu vực dự án lớn):");
    if(name) { treeData.push({ id: "fold_" + Date.now(), name: "📁 " + name, type: "folder", isOpen: true, children: [] }); updateTreeHTML(); svSt(); }
}
function addChild(parentId, e) {
    e.stopPropagation(); let name = prompt("Nhập tên Phòng chat con dành cho hạng mục này:");
    if(name) { 
        let p = findNode(treeData, parentId); let id = "chat_" + Date.now();
        if(!p.children) p.children = [];
        p.children.push({ id: id, name: "📝 " + name, type: "chat" }); 
        p.isOpen = true; updateTreeHTML(); setCat(id, name); svSt();
    }
}
function renNode(id, e) {
    e.stopPropagation(); let n = findNode(treeData, id); let name = prompt("Sửa tên:", n.name);
    if(name) { n.name = name.trim(); updateTreeHTML(); svSt(); if(id === curC) setCat(id, name); }
}
function delNode(id, e) {
    e.stopPropagation();
    if(confirm("XÓA MỤC: Hệ thống Server sẽ xóa sạch lịch sử nhánh này. Bạn đồng ý chứ?")) { 
        deleteNode(treeData, id); updateTreeHTML(); svSt();
        if(id === curC) { curC = null; document.getElementById('chatArea').innerHTML="Đã xóa phòng. Vui lòng chọn phòng khác bên trái."; }
    }
}
function toggleFolder(id) { let n = findNode(treeData, id); n.isOpen = !n.isOpen; updateTreeHTML(); svSt(); }

function fetchFiles() {
    if(!curC) return;
    fetch('/api/files?cat_id=' + curC).then(r=>r.json()).then(d => {
        let flist = document.getElementById('savedFilesList');
        if(d.files && d.files.length > 0) {
            flist.innerHTML = `📁 Tủ Hồ Sơ Server chứa: <b style="color:#10b981">${d.files.join(', ')}</b>`;
        } else {
            flist.innerHTML = `📁 Tủ Hồ Sơ Server: TRỐNG`;
        }
    });
}

function setCat(id, name){
    if(!id) return;
    curC = id; updateTreeHTML();
    document.getElementById('chatTitle').innerHTML = `<i class="fa-solid fa-comments"></i> <b>Phòng triển khai: ${name}</b>`;
    document.getElementById('chatArea').innerHTML = catHtmls[id] || `<div class="msg msg-ai"><div class="model-badge" style="color:#10b981;"><i class="fa-solid fa-building-user"></i> HỆ THỐNG MÁY CHỦ VTC</div>Phòng làm việc <b>${name}</b> đã sẵn sàng kết nối. Mọi hình ảnh, tài liệu ném vào đây sẽ lưu trữ vĩnh viễn trên PostgreSQL & Persistent Volume.</div>`;
    document.getElementById('chatArea').scrollTop = 99999;
    document.getElementById('fl').innerHTML = `Sẵn sàng nhận lệnh.`;
    fetchFiles();
}

function clearChatData() { 
    if(!curC) return;
    if(!confirm("CẢNH BÁO MẠNH: Dọn dẹp sạch File và Chat trên bộ nhớ Server?")) return;
    const fd = new FormData(); fd.append('cat_id', curC);
    fetch('/api/clear', {method:'POST', body:fd}).then(()=>{
        catHists[curC] = []; catHtmls[curC] = ""; svSt(); setCat(curC, findNode(treeData, curC).name); 
    });
}

function sel(k,e){ lastSelM=k; document.querySelectorAll('.ai-card').forEach(c=>c.classList.remove('active')); e.classList.add('active'); }

async function hf(){ 
    if(!curC) { alert("Xin chọn 1 thư mục phòng làm việc bên trái trước khi upload file!"); return; }
    let files = document.getElementById('f').files;
    if(files.length === 0) return;
    
    document.getElementById('fl').innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="color:#f59e0b"></i> Đang tải ${files.length} file lên Server riêng...`;
    
    const fd = new FormData(); fd.append('cat_id', curC);
    for(let f of files) fd.append('files', f);

    try {
        let r = await fetch('/api/upload', {method:'POST', body:fd});
        if(r.ok) {
            document.getElementById('fl').innerHTML = `<span style="color:#10b981"><i class="fa-solid fa-check"></i> Đã cất thành công ${files.length} file vào Volume!</span>`;
            fetchFiles(); 
        }
    } catch(e) { document.getElementById('fl').innerHTML = `<span style="color:#ef4444">Lỗi Server Upload: ${e}</span>`; }
    document.getElementById('f').value = ""; 
}

function extractUrl(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const matches = text.match(urlRegex);
    return matches ? matches[0] : "";
}

document.getElementById('q').addEventListener('keydown', e => { if(e.ctrlKey && e.key==='Enter') snd(); });

async function snd() {
    if(!curC) { alert("Anh hãy click chọn một phòng làm việc trước!"); return; }
    const q = document.getElementById('q').value;
    const url = (tab==='link') ? document.getElementById('url').value : "";
    if(!q && !url) return;
    
    let userText = q;
    
    const cArea = document.getElementById('chatArea');
    cArea.innerHTML += `<div class="msg msg-user"><div class="author">👤 Trưởng Phòng</div>${q.replace(/\n/g,"<br>")}</div>`;
    cArea.scrollTop = cArea.scrollHeight;
    
    const bd = new FormData(); bd.append('message', q); bd.append('model', lastSelM); bd.append('cat_id', curC);
    if(url) bd.append('url', url);
    bd.append('history', JSON.stringify(catHists[curC] || []));
    
    document.getElementById('b').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; document.getElementById('b').disabled=true;
    document.getElementById('q').value = "";
    document.getElementById('fl').innerHTML = `Máy chủ đang xử lý tiến trình...`;
    svSt();
    
    const typingId = "typ_" + Date.now();
    cArea.innerHTML += `<div class="msg msg-ai" id="${typingId}"><i class="fa-solid fa-circle-notch fa-spin"></i> AI đang phân tích dữ liệu Server...</div>`;
    cArea.scrollTop = cArea.scrollHeight;

    try{
        const r = await fetch('/api/c', {method:'POST',body:bd});
        const d = await r.json();
        const rawContent = d.answer;
        
        if(!catHists[curC]) catHists[curC] = [];
        catHists[curC].push({"role":"user", "content": q});
        catHists[curC].push({"role":"assistant", "content": rawContent});
        
        const exportId = "exp_" + Date.now();
        dbExports[exportId] = rawContent; 
        
        let outHtml = `<div class="model-badge" style="color:${d.avatar_color}"><i class="fa-solid ${d.avatar}"></i> <span>Đại diện: ${d.ai_name}</span></div>`;
        outHtml += formatClean(rawContent);
        outHtml += `<div class="export-panel">
            <div class="export-txt" onclick="expT('${exportId}', this)"><i class="fa-solid fa-file-lines"></i> RAW (.TXT)</div>
            <div class="export-badge" onclick="expW('${exportId}', this)"><i class="fa-solid fa-file-word"></i> IN FILE WORD </div>
        </div><div style="clear:both;"></div>`;
        
        document.getElementById(typingId).innerHTML = outHtml;
        svSt(); 
        document.getElementById('fl').innerHTML = `Tác vụ hoàn thành. Chờ chỉ thị tiếp theo.`;
    } catch(e) { document.getElementById(typingId).innerHTML = "<span style='color:#da373c'>Lỗi kết nối Server! Vui lòng F5 lại web.</span>"; }
    document.getElementById('b').innerHTML = '<i class="fa-solid fa-paper-plane"></i> GỬI LỆNH'; document.getElementById('b').disabled=false;
    cArea.scrollTop = cArea.scrollHeight;
}

function expW(exportId, btn) {
    const txt = dbExports[exportId];
    if(!txt) return;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang In File Word...';
    btn.style.background = '#3b82f6';
    const fd = new FormData(); fd.append('text', txt); fd.append('format', 'docx');
    fetch('/api/export', {method:'POST', body:fd}).then(r => r.blob()).then(b => {
        let u = window.URL.createObjectURL(b); let a = document.createElement('a'); a.href = u;
        a.download = "BaoCao_TrinhDuyet.docx"; document.body.appendChild(a); a.click(); a.remove();
        btn.innerHTML = '✅ Đã tải file Word';
    }).catch(e => { alert(e); btn.innerHTML = origHtml; });
}

function expT(exportId, btn) {
    const txt = dbExports[exportId];
    if(!txt) return;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>...';
    const fd = new FormData(); fd.append('text', txt); fd.append('format', 'txt');
    fetch('/api/export', {method:'POST', body:fd}).then(r => r.blob()).then(b => {
        let u = window.URL.createObjectURL(b); let a = document.createElement('a'); a.href = u;
        a.download = "BaoCao_Raw.txt"; document.body.appendChild(a); a.click(); a.remove();
        btn.innerHTML = '✅ Đã tải file Text';
    }).catch(e => { alert(e); btn.innerHTML = origHtml;});
}

function formatClean(t) {
    if(!t) return "";
    let s = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    s = s.replace(/### (.*?)\n/g, "<h3>$1</h3>");
    s = s.replace(/## (.*?)\n/g, "<h2>$1</h2>");
    s = s.replace(/# (.*?)\n/g, "<h1>$1</h1>");
    s = s.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
    s = s.replace(/\n/g, "<br>");
    return s;
}
</script></body></html>"""

@app.route('/')
@login_required
def idx(): return render_template_string(HTML_UI)

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    cat_id = secure_filename(request.form.get("cat_id", "chat_0"))
    cat_dir = os.path.join(UPLOAD_FOLDER, cat_id)
    os.makedirs(cat_dir, exist_ok=True)
    for f in request.files.getlist("files"):
        if f.filename: f.save(os.path.join(cat_dir, secure_filename(f.filename)))
    return jsonify({"status": "ok"})

@app.route('/api/files', methods=['GET'])
@login_required
def api_files():
    cat_id = secure_filename(request.args.get("cat_id", "chat_0"))
    cat_dir = os.path.join(UPLOAD_FOLDER, cat_id)
    files = []
    if os.path.exists(cat_dir):
        files = [f for f in os.listdir(cat_dir) if os.path.isfile(os.path.join(cat_dir, f))]
    return jsonify({"files": files})

@app.route('/api/c', methods=['POST'])
@login_required
def api():
    try:
        msg = request.form.get("message", "")
        mod = request.form.get("model", "openai")
        turl = request.form.get("url", "")
        cat_id = secure_filename(request.form.get("cat_id", "chat_0"))
        
        try: chat_hist = json.loads(request.form.get("history", "[]"))
        except: chat_hist = []
        
        cat_dir = os.path.join(UPLOAD_FOLDER, cat_id)
        os.makedirs(cat_dir, exist_ok=True)
        
        fstr = ""
        img_list = []
        for fn in os.listdir(cat_dir):
            fp = os.path.join(cat_dir, fn)
            if os.path.isfile(fp):
                proc = FileProcessor.process_file(fp, fn)
                if proc["type"] == "text": fstr += f"\n=== [TÀI LIỆU DỰ ÁN]: {fn} ===\n" + proc["content"]
                elif proc["type"] == "image": img_list.append(proc)
                
        if fstr: fstr = fstr[:80000]
            
        res = agent_core.process(msg, mod, text_files=fstr, image_files=img_list, target_url=turl, chat_history=chat_hist)
        return jsonify(res)
    except Exception as e:
        return jsonify({"answer": f"Lỗi Giao thức Server: {str(e)}", "model": "ERROR", "ai_name": "Lỗi Máy Chủ", "avatar": "fa-triangle-exclamation", "avatar_color": "#da373c"})

@app.route('/api/clear', methods=['POST'])
@login_required
def api_clear():
    cat_id = secure_filename(request.form.get("cat_id", "chat_0"))
    cat_dir = os.path.join(UPLOAD_FOLDER, cat_id)
    if os.path.exists(cat_dir):
        for fn in os.listdir(cat_dir):
            try: os.remove(os.path.join(cat_dir, fn))
            except: pass
    return jsonify({"status": "ok"})

@app.route('/api/export', methods=['POST'])
@login_required
def export_docx():
    try:
        import docx
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        
        text = request.form.get("text", "")
        fmt = request.form.get("format", "docx")
        if not text: return "No content", 400
        
        if fmt == "txt":
            filepath = os.path.join(UPLOAD_FOLDER, "exports", f"Export_{int(time.time())}.txt")
            with open(filepath, "w", encoding="utf-8") as ft:
                ft.write(text.replace("**", "").replace("### ", "").replace("## ", "").replace("# ", ""))
            return send_file(filepath, as_attachment=True)
            
        clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        doc = docx.Document()
        
        try:
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Times New Roman'
            font.size = Pt(14)
        except: pass
        
        for line in clean_text.split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('### '):
                p = doc.add_heading(level=3); r = p.add_run(line[4:].replace('**', ''))
                r.font.name = 'Times New Roman'; r.font.color.rgb = RGBColor(0,0,0)
            elif line.startswith('## '):
                p = doc.add_heading(level=2); r = p.add_run(line[3:].replace('**', ''))
                r.font.name = 'Times New Roman'; r.font.color.rgb = RGBColor(0,0,0)
            elif line.startswith('# '):
                p = doc.add_heading(level=1); r = p.add_run(line[2:].replace('**', ''))
                r.font.name = 'Times New Roman'; r.font.color.rgb = RGBColor(0,0,0)
            elif line.startswith('- '):
                p = doc.add_paragraph(style='List Bullet')
                parts = line[2:].split('**')
                for i, part in enumerate(parts):
                    run = p.add_run(part); run.bold = (i % 2 != 0)
            else:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                parts = line.split('**')
                for i, part in enumerate(parts):
                    run = p.add_run(part); run.bold = (i % 2 != 0)
        
        filepath = os.path.join(UPLOAD_FOLDER, "exports", f"DeXuat_{int(time.time())}.docx")
        doc.save(filepath)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=False)
