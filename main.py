import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# --- ১. Render Port Server Setup ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# --- ২. Environment Variables & Gemini Client ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()

client = None
if GEMINI_KEY:
    client = genai.Client(api_key=GEMINI_KEY)

user_chats = {}

# --- ৩. AI Functions ---

# (ক) পার্সোনাল চ্যাটের উত্তর ও মেমোরি হ্যান্ডলার
async def get_personal_chat_response(user_id, prompt):
    if not client:
        return "GEMINI_KEY পাওয়া যায়নি!"
    
    if user_id not in user_chats:
        user_chats[user_id] = client.chats.create(model='gemini-2.5-flash')
    
    chat = user_chats[user_id]

    for attempt in range(3):
        try:
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
                return "⚠️ এআই কোটা লিমিট শেষ বা সার্ভার ব্যস্ত। অনুগ্রহ করে কয়েক সেকেন্ড পর আবার চেষ্টা করুন।"
            return f"AI Error: {str(e)}"

# (খ) চ্যানেলের জন্য অটো মুভি/সিরিজ রিভিউ জেনারেটর
async def generate_channel_review(title_text):
    if not client:
        return None
    
    prompt = f"""
    তুমি একজন প্রফেশনাল মুভি ও সিরিজ বিশ্লেষক। নিচের নামটি বা ক্যাপশনটি একটি মুভি বা টিভি সিরিজ সংক্রান্ত:
    "{title_text}"

    তুমি বাংলা ভাষায় নিচের নির্দিষ্ট ফরম্যাট অনুযায়ী সুন্দর ও আকর্ষণীয় একটি বিবরণ তৈরি করে দাও:

    🎬 **সিরিজ/মুভির নাম:** 
    📅 **রিলিজ সাল:** 
    🌍 **দেশ (Country):** 
    🎞️ **জনরা (Genre):** 
    📺 **সিজন ও এপিসোড সংখ্যা:** (সিরিজ হলে বর্তমান কতটি সিজন ও মোট কতটি এপিসোড রয়েছে, মুভি হলে 'Movie' লিখবে)

    📊 **উপাদান বিশ্লেষণ:**
    - 💖 রোমান্স: X%
    - 🗡️ অ্যাকশন: X%
    - 🔪 থ্রিলার: X%
    - 👽 সাই-ফাই: X%
    - 😂 কমেডি: X%
    - 💋 কিসিং/সেক্স সিন: X%

    📖 **সংক্ষিপ্ত কাহিনী (স্পয়লার মুক্ত):**
    (এখানে ২-৩ লাইনে আকর্ষণীয় গল্প লিখবে)

    প্রয়োজনীয় ইমোজি ব্যবহার করবে এবং কোনো অতিরিক্ত সূচনা বা ভূমিকা ছাড়াই সরাসরি এই ফরম্যাটে আউটপুট দিবে।
    """

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if ("429" in str(e) or "503" in str(e)) and attempt < 2:
                await asyncio.sleep(3)
                continue
            return None

# --- ৪. Telegram Handlers ---

# চ্যানেলে টেক্সট, ফটো বা মিডিয়া ক্যাপশন সহ যেকোনো পোস্ট এলে তা প্রসেস করবে
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_post = update.channel_post
    if not channel_post:
        return
    
    # টেক্সট অথবা ফটোর ক্যাপশন নেওয়া
    post_text = channel_post.text or channel_post.caption
    if not post_text:
        return
    
    post_text = post_text.strip()
    review_text = await generate_channel_review(post_text)
    
    if review_text:
        try:
            await channel_post.reply_text(review_text)
        except Exception as e:
            print(f"Reply Error: {e}")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    status_msg = await update.message.reply_text("🤖 সোনা পাখি চিন্তা করছে...")
    
    response_text = await get_personal_chat_response(user_id, user_text)
    await status_msg.edit_text(response_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if client:
        user_chats[user_id] = client.chats.create(model='gemini-2.6-flash')
    await update.message.reply_text("হ্যালো! আমি আপনার পার্সোনাল ও চ্যানেল অ্যাসিস্ট্যান্ট সোনা পাখি।")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if client:
        user_chats[user_id] = client.chats.create(model='gemini-3.6-flash')
    await update.message.reply_text("🔄 আমাদের আগের সব মেমোরি রিসেট করা হয়েছে!")

# --- ৫. Main Execution ---
if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("reset", reset))
        
        # চ্যানেলের টেক্সট ও মিডিয়া (ছবিসহ) পোস্ট ধরার ফিল্টার
        app.add_handler(MessageHandler(filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION), handle_channel_post))
        
        # পার্সোনাল প্রাইভেট চ্যাট হ্যান্ডলার
        app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_message))
        
        print("Bot is starting...")
        app.run_polling()
