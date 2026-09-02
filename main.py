import os
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

# استدعاء المتغيرات السرية وتنظيفها
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip().strip('"').strip("'")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip().strip('"').strip("'")
raw_gemini_key = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = raw_gemini_key.strip().strip('"').strip("'") if raw_gemini_key else None

# رقم هاتف المحامي الشخصي للإشعارات والمستندات
ADMIN_PHONE = "9647702956021"

# إعداد عميل الذكاء الاصطناعي
if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = genai.Client()

# التعليمات والضوابط القانونية ورابط الحجز
SYSTEM_PROMPT = """
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في العراق.

المهام وقواعد الإجابة الصارمة:
1. قدّم إجابات قانونية عامة وموجزة جداً ومختصرة، دون الدخول في تفاصيل فنية دقيقة أو شروحات إجرائية.
2. يُمنع منعاً باتاً شرح كيفية إقامة الدعاوى أو صياغة اللوائح والعرائض القضائية أو تفصيل خطوات التقاضي أمام المحاكم.
3. وضّح للموكل أن الاستفسارات والرسائل يتم الاطلاع عليها وتدقيقها من قبل الأستاذ المحامي شخصياً وفق ما يتناسب مع جدول أعماله والتزاماته في المحاكم.

الموقع وأوقات العمل:
- العنوان: بغداد - زيونة - قرب دار الأزياء العراقية (البحث في خرائط Google: مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية).
- أوقات العمل: من الأحد إلى الخميس (الجمعة والسبت عطلة، وتُستثنى العطل الرسمية).
- الفترة الصباحية (8:00 ص - 2:00 ظ): تواجد المحامي في أروقة المحاكم ومتابعة المعاملات بالدوائر والجهات الرسمية.
- فترة المقابلات المكتبية (2:00 ظ - 4:00 ع): مخصصة للاستشارات والمقابلات المباشرة بعد تثبيت موعد مسبق.

حجز المواعيد ولائحة الأجور وآلية الدفع:
- إمكانية الاستشارة: حضورياً (في مقر المكتب) أو عن بُعد (عبر الهاتف أو المنصات الرقمية).
- عند رغبة الموكل بتثبيت موعد، زوّده برابط استمارة الحجز الإلكترونية مباشرة:
https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform
- لائحة أجور الاستشارات الرسمية المباشرة مع المحامي:
  * استشارات الأحوال الشخصية: 75,000 دينار عراقي.
  * الاستشارات المدنية والشركات والعقود: 150,000 دينار عراقي.
  * الاستشارات الجزائية والجنائية: 300,000 دينار عراقي.
- آلية الدفع: وضّح للموكل أنه بعد إرسال استمارة الحجز، يتواصل المكتب معه لتأكيد الموعد وإرسال تفاصيل الدفع عبر وسائل الدفع الإلكترونية المحلية المعتمدة أو روابط الدفع المباشرة (Payment Links) للاستشارة عن بُعد، أو سدادها مباشرة داخل المكتب للمقابلات الحضورية.

نص إخلاء المسؤولية الإلزامي:
اختم كل رد بدون استثناء بالنص التالي في سطر مستقل:
"⚠️ تنبيه إخلاء مسؤولية: هذا رد آلي مبرمج صادر عن المساعد الذكي لمكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية لغرض الاسترشاد والتوجيه الأولي فقط، ولا يُعد استشارة قانونية رسمية ولا ينشئ رابطة توكيل. لحجز موعد استشارة رسمية ودراسة القضية (حضورياً أو عن بُعد)، يُرجى التقديم عبر رابط الاستمارة: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
"""

@app.route("/", methods=["GET"])
def home():
    return "Legal Assistant Bot is Active", 200

# مسار استقبال وتأكيد الـ Webhook
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
            from_number = message["from"]
            msg_type = message.get("type")

            # 1. معالجة الرسائل النصية
            if msg_type == "text":
                user_query = message["text"]["body"]
                print(f"Message from {from_number}: {user_query}", flush=True)

                try:
                    response = ai_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=f"{SYSTEM_PROMPT}\n\nرسالة المستفسر: {user_query}",
                    )
                    reply_text = response.text
                except Exception as e:
                    print(f"Gemini 2.0 Error: {e}", flush=True)
                    try:
                        response = ai_client.models.generate_content(
                            model="gemini-1.5-flash",
                            contents=f"{SYSTEM_PROMPT}\n\nرسالة المستفسر: {user_query}",
                        )
                        reply_text = response.text
                    except Exception as e2:
                        print(f"Gemini 1.5 Error: {e2}", flush=True)
                        reply_text = (
                            "أهلاً بك في مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية.\n"
                            "نعتذر عن تعذر معالجة الطلب آلياً في الوقت الحالي. "
                            "يتم الاطلاع على الرسائل من قبل المكتب تباعاً، أو يمكنك حجز موعد عبر الاستمارة:\n"
                            "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                        )

                # إرسال الرد للمراجع
                send_whatsapp_message(from_number, reply_text)

                # إرسال إشعار فوري إلى رقم المحامي الشخصي
                if from_number != ADMIN_PHONE:
                    admin_summary = (
                        f"📩 *استفسار جديد عبر البوت*\n"
                        f"👤 *المراجع:* +{from_number}\n"
                        f"💬 *السؤال:* {user_query}\n\n"
                        f"🤖 *رد البوت:*\n{reply_text}"
                    )
                    send_whatsapp_message(ADMIN_PHONE, admin_summary)

            # 2. معالجة الصور والمستندات القانونية
            elif msg_type in ["image", "document"]:
                media_id = message[msg_type].get("id")
                caption = message[msg_type].get("caption", "لا يوجد وصف")
                doc_title = "صورة" if msg_type == "image" else "مستند PDF/ملف"

                client_receipt = (
                    "أهلاً بك في مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية.\n\n"
                    f"✅ تم استلام الـ ({doc_title}) بنجاح. سيتم تدقيقه وعرضه على الأستاذ المحامي شخصياً وفق جدول أعماله والتزاماته في المحاكم.\n\n"
                    "لتثبيت موعد مقابلة رسمية:\n"
                    "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                )
                send_whatsapp_message(from_number, client_receipt)

                if from_number != ADMIN_PHONE:
                    notice = f"📎 *وصل {doc_title} جديد للمكتب*\n👤 *من المراجع:* +{from_number}\n📝 *الوصف:* {caption}"
                    sent = send_whatsapp_media(ADMIN_PHONE, msg_type, media_id, notice)
                    if not sent:
                        send_whatsapp_message(ADMIN_PHONE, notice)

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
    if caption:
        payload[media_type]["caption"] = caption

    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
