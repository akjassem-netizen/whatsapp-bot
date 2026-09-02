import os
import re
import threading
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip().strip('"').strip("'")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip().strip('"').strip("'")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")

ADMIN_PHONE = "9647702956021"
PROCESSED_MESSAGES = set()

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"

SYSTEM_PROMPT = f"""
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في بغداد - زيونة.

مهمتك: الرد على المراجعين بأسلوب راقٍ، مهذب، محترف، ومريح دون تعقيد أو تنفير، وتوجيههم لملء استمارة حجز الاستشارة وفق القواعد الصارمة التالية:

1. توحيد لغة الرد:
- إذا كانت رسالة المراجع باللغة العربية، يجب أن يكون الرد كاملاً باللغة العربية حصراً، بأسلوب ترحيبي وقانوني رصين ومختصر، بدون أي كلمة أو إشعار باللغة الإنجليزية نهائياً.
- إذا كانت رسالة المراجع بأي لغة أجنبية (إنجليزية، تركية، كردية، إلخ)، يكون الرد كاملاً من البداية إلى النهاية بتلك اللغة حصراً.

2. سياسة الأتعاب والأسعار:
- لا تذكر تفاصيل مالية معقدة تنفّر العميل؛ بل وضّح بلطف وأدب أن أجور الاستشارات تبدأ أولياً من 75,000 دينار عراقي، وتُحدد القيمة بدقة بعد مراجعة تفاصيل وموضوع القضية عبر الاستمارة.

3. أوقات العمل والمواعيد (صارم جداً):
- ساعات الدوام العام والاستفسارات: من 8:00 صباحاً حتى 4:00 عصراً.
- مواعيد الاستشارات المباشرة (سواء كانت حضورية أو هاتفية):
  • الفترة الأساسية: يومياً من الساعة 2:00 ظهراً وحتى الساعة 4:00 عصراً (الفترة الصباحية مخصصة لعمل الأستاذ المحامي أمام المحاكم والدوائر).
  • الفترة المسائية: من 4:00 عصراً وحتى 7:00 مساءً متاحة حصراً بالتنسيق المسبق وحسب جدول العمل.
  • يُمنع منعاً باتاً حجز أي موعد صباحي قبل الساعة 2:00 ظهراً.
  • لا توجد أي مواعيد ليلاً بعد الساعة 7:00 مساءً.

4. آلية حجز الموعد والدفع:
- لا تطلب رقم الهاتف أو البيانات الشخصية داخل المحادثة؛ بل وجّه العميل دائماً وبشكل مباشر لتعبئة استمارة حجز الاستشارة: {FORM_URL}
- وضّح له أن المكتب يراجع الطلب بعد إرسال الاستمارة ويتواصل معه مباشرة عبر الواتساب لتزويده ببيانات الدفع الإلكتروني (زين كاش، آسيا بي، كي كارد، ماستركارد/فيزا، التطبيقات المصرفية) وتثبيت أنسب موعد لحضرته.
- يمنع منعاً باتاً اختلاق أي أرقام هواتف من عندك.

5. نظام إخراج النص:
ضع ردك بالشكل التالي بدقة:
[REPLY_START]
(نص الرد الكامل الموجه للمراجع بلغته هو فقط شاملاً رابط الاستمارة، بدون أي كلمة عربية إذا كان المراجع أجنبياً، وبدون أي كلمة إنجليزية إذا كان المراجع عربياً)
[REPLY_END]

إذا كانت رسالة المراجع بأي لغة غير العربية، أضف هذا القسم في النهاية:
[ADMIN_TRANS_START]
ترجمة سؤال المراجع: (شرح عربي موجز لما طلبه المراجع)
ترجمة الرد المرسل إليه: (شرح عربي موجز لما تم إخباره به)
[ADMIN_TRANS_END]
(إذا كانت رسالة المراجع بالعربية، لا تضع قسم ADMIN_TRANS_START نهائياً).
"""

def get_active_groq_model():
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    preferred = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "llama-3.1-8b-instant"
    ]
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            active_ids = [m["id"] for m in res.json().get("data", [])]
            for pref in preferred:
                if pref in active_ids:
                    return pref
            for mid in active_ids:
                m_low = mid.lower()
                if not any(x in m_low for x in ["whisper", "orpheus", "guard", "embed", "tts"]):
                    return mid
    except Exception:
        pass
    return "openai/gpt-oss-20b"

def generate_ai_response(user_query):
    if not GROQ_API_KEY:
        return None, "مفتاح GROQ_API_KEY غير مضاف في متغيرات Render"

    active_model = get_active_groq_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            raw_text = response.json()["choices"][0]["message"]["content"]
            return raw_text, None
        else:
            return None, f"{active_model}: {response.text}"
    except Exception as e:
        return None, str(e)

def parse_ai_response(raw_text, user_query):
    is_arabic = bool(re.search(r'[\u0600-\u06FF]', user_query))
    client_reply = ""
    admin_trans = ""

    if "[REPLY_START]" in raw_text and "[REPLY_END]" in raw_text:
        client_reply = raw_text.split("[REPLY_START]")[1].split("[REPLY_END]")[0].strip()
    elif "[ADMIN_TRANS_START]" in raw_text:
        client_reply = raw_text.split("[ADMIN_TRANS_START]")[0].strip()
    else:
        client_reply = raw_text.strip()

    if "[ADMIN_TRANS_START]" in raw_text and "[ADMIN_TRANS_END]" in raw_text:
        admin_trans = raw_text.split("[ADMIN_TRANS_START]")[1].split("[ADMIN_TRANS_END]")[0].strip()
    elif "[ADMIN_TRANS_START]" in raw_text:
        admin_trans = raw_text.split("[ADMIN_TRANS_START]")[1].strip()

    for tag in ["[REPLY_START]", "[REPLY_END]", "[ADMIN_TRANS_START]", "[ADMIN_TRANS_END]"]:
        client_reply = client_reply.replace(tag, "").strip()
        if admin_trans:
            admin_trans = admin_trans.replace(tag, "").strip()

    # حظر ومسح أي أرقام هواتف قد يخترعها الذكاء
    client_reply = re.sub(r'(\*?07[3-9]\d{1}[- ]?\d{6,8}\*?|\*?1234567[^\s]*\*?)', '', client_reply).strip()

    # إزالة أي تنبيه إنجليزي إذا كان العميل يكتب بالعربية لضمان صفاء اللغة
    if is_arabic:
        client_reply = re.sub(r'⚖️?\s*Notice:?.*', '', client_reply, flags=re.DOTALL).strip()

    return client_reply, admin_trans, is_arabic

def process_message_background(message):
    try:
        from_number = message["from"]
        msg_type = message.get("type")

        # 1. الرسائل النصية
        if msg_type == "text":
            user_query = message["text"]["body"]
            print(f"Message from {from_number}: {user_query}", flush=True)

            raw_ai_reply, error_detail = generate_ai_response(user_query)

            if not raw_ai_reply:
                # رسالة طوارئ في حال تعطل سيرفر الذكاء
                is_arabic = bool(re.search(r'[\u0600-\u06FF]', user_query))
                if is_arabic:
                    client_reply = (
                        "أهلاً وسهلاً بحضرتك في مكتب المحامي علي كاظم الهاشمي.\n\n"
                        "تبدأ أجور الاستشارات من 75,000 دينار عراقي وتُحدد بدقة بعد مراجعة تفاصيل القضية.\n"
                        "مواعيد الاستشارات تبدأ يومياً من الساعة 2:00 ظهراً إلى 4:00 عصراً (ومن 4:00 إلى 7:00 مساءً بالتنسيق المسبق).\n\n"
                        "لتثبيت حجزكم وتحديد الموعد المناسب، يرجى ملء الاستمارة وسيتواصل معكم فريقنا عبر الواتساب:\n"
                        f"{FORM_URL}"
                    )
                else:
                    client_reply = (
                        "Welcome to the Law Office of Attorney Ali Kadhem Hashimi.\n\n"
                        "Consultation fees start from 75,000 IQD. Consultations are scheduled between 2:00 PM and 4:00 PM (or 4:00 PM – 7:00 PM upon coordination).\n\n"
                        "Please submit your request via the form below, and our team will contact you directly via WhatsApp:\n"
                        f"{FORM_URL}"
                    )
                admin_trans = None
                if error_detail and from_number != ADMIN_PHONE:
                    send_whatsapp_message(ADMIN_PHONE, f"⚠️ *خطأ فني في الذكاء الاصطناعي:*\n{error_detail}")
            else:
                client_reply, admin_trans, is_arabic = parse_ai_response(raw_ai_reply, user_query)

            # إرسال الرد للمراجع بلغته الأصلية
            send_whatsapp_message(from_number, client_reply)

            # إرسال التقرير الإداري لهاتفك الشخصي
            if from_number != ADMIN_PHONE:
                if is_arabic or not admin_trans:
                    admin_msg = (
                        f"📩 *استفسار جديد*\n"
                        f"👤 *المستفسر:* +{from_number}\n"
                        f"💬 *السؤال:* {user_query}\n\n"
                        f"🤖 *الرد:* {client_reply}"
                    )
                else:
                    admin_msg = (
                        f"📩 *استفسار وارد (بلغة أجنبية)*\n"
                        f"👤 *المستفسر:* +{from_number}\n\n"
                        f"💬 *نص المراجع الأصلي:*\n{user_query}\n\n"
                        f"🌐 *التقرير المترجم للأستاذ المحامي:*\n{admin_trans}"
                    )
                
                send_whatsapp_message(ADMIN_PHONE, admin_msg)

        # 2. الصور والمستندات
        elif msg_type in ["image", "document"]:
            media_id = message[msg_type].get("id")
            caption = message[msg_type].get("caption", "")
            doc_title = "الصورة" if msg_type == "image" else "المستند"

            receipt = (
                f"أهلاً بك، تم استلام {doc_title} بنجاح وسيتم عرضه على الأستاذ المحامي وفق جدول أعماله.\n\n"
                "لتثبيت موعد استشارة رسمي، يرجى التفضل بملء الاستمارة وسيتواصل معكم فريقنا عبر الواتساب لتأكيد الموعد:\n"
                f"{FORM_URL}"
            )
            send_whatsapp_message(from_number, receipt)

            if from_number != ADMIN_PHONE:
                notice = f"📎 *وصل {doc_title} جديد للمكتب*\n👤 *من المراجع:* +{from_number}\n📝 {caption}"
                sent = send_whatsapp_media(ADMIN_PHONE, msg_type, media_id, notice)
                if not sent:
                    send_whatsapp_message(ADMIN_PHONE, notice)

        # 3. البصمات الصوتية
        elif msg_type in ["audio", "voice"]:
            audio_obj = message.get("audio") or message.get("voice") or {}
            media_id = audio_obj.get("id")

            audio_receipt = (
                "أهلاً بك، تم استلام التسجيل الصوتي بنجاح وسيتم الاستماع إليه من قبل الأستاذ المحامي وفق جدول أعماله.\n\n"
                "لتثبيت موعد استشارة رسمي، يرجى التفضل بملء الاستمارة وسيتواصل معكم فريقنا عبر الواتساب لتأكيد الموعد:\n"
                f"{FORM_URL}"
            )
            send_whatsapp_message(from_number, audio_receipt)

            if from_number != ADMIN_PHONE and media_id:
                notice = f"🎙️ *تسجيل صوتي وارد من مستفسر*\n👤 *الرقم:* +{from_number}"
                send_whatsapp_message(ADMIN_PHONE, notice)
                send_whatsapp_media(ADMIN_PHONE, "audio", media_id)

    except Exception as e:
        print(f"Error in background: {e}", flush=True)

@app.route("/", methods=["GET"])
def home():
    return "Legal Assistant Bot is Active (Refined Soft Intake Policy)", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403

    if request.method == "POST":
        data = request.get_json()

        if (
            data.get("entry")
            and data["entry"][0].get("changes")
            and data["entry"][0]["changes"][0].get("value")
            and "messages" in data["entry"][0]["changes"][0]["value"]
        ):
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            msg_id = message.get("id")

            if msg_id in PROCESSED_MESSAGES:
                return "EVENT_RECEIVED", 200
            PROCESSED_MESSAGES.add(msg_id)
            if len(PROCESSED_MESSAGES) > 1000:
                PROCESSED_MESSAGES.clear()

            thread = threading.Thread(target=process_message_background, args=(message,))
            thread.daemon = True
            thread.start()

        return "EVENT_RECEIVED", 200

def send_whatsapp_message(to_number, text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

def send_whatsapp_media(to_number, media_type, media_id, caption=""):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": media_type,
        media_type: {"id": media_id}
    }
    if caption and media_type != "audio":
        payload[media_type]["caption"] = caption

    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
