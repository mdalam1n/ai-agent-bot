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

# --- ২. Environment Variables & Gemini Setup ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()

client = None
if GEMINI_KEY:
    client = genai.Client(api_key=GEMINI_KEY)

# চ্যাট হিস্ট্রি ধরে রাখার জন্য ডিকশনারি
user_chats = {}

def get_or_create_chat(user_id):
    if not client:
        return None
    if user_id not in user_chats:
        user_chats[user_id] = client.chats.create(model='gemini-2.5-flash')
    return user_chats[user_id]

# --- ৩. AI Response Handlers ---

# (ক) টেক্সট চ্যাটের উত্তর
async def get_personal_chat_response(user_id, prompt):
    if not client:
        return "⚠️ GEMINI_KEY পাওয়া যায়নি!"
    
    chat = get_or_create_chat(user_id)

    for attempt in range(3):
        try:
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
                return "⚠️ এআই সার্ভার ব্যস্ত। কিছুক্ষণ পর আবার চেষ্টা করুন।"
            return f"AI Error: {str(e)}"

# (খ) ভয়েস মেসেজ প্রসেস করার ফাংশন
async def process_voice_message(user_id, voice_file_path):
    if not client:
        return "⚠️ GEMINI_KEY পাওয়া যায়নি!"
    
    try:
        # ভয়েস ফাইলটি জেমিনাইতে আপলোড করা
        audio_file = client.files.upload(file=voice_file_path)
        
        prompt = "এই ভয়েস মেসেজটিতে কি বলা হয়েছে শুনো এবং ব্যবহারকারীকে বাংলায় সুন্দর ও প্রাসঙ্গিক উত্তর দাও।"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[audio_file, prompt]
        )
        
        # প্রসেস শেষে টেম্পোরারি ফাইলটি সার্ভার থেকে মুছে ফেলা
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass
        
        return response.text
    except Exception as e:
        return f"⚠️ ভয়েস প্রসেস করতে সমস্যা হয়েছে: {str(e)}"

# (গ) চ্যানেলের জন্য অটো মুভি/সিরিজ রিভিউ
async def generate_channel_review(title_text):
    if not client:
        return None
    
    prompt = f"""
    তুমি একজন প্রফেশনাল মুভি ও সিরিজ বিশ্লেষক। নিচের নামটি বা বিবরণটি একটি মুভি বা টিভি সিরিজ সংক্রান্ত:
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
                contents=prompt
            )
            return response.text
        except Exception as e:
            if ("429" in str(e) or "503" in str(e)) and attempt < 2:
                await asyncio.sleep(3)
                continue
            return None

# --- ৪. Telegram Event Handlers ---

# ভয়েস মেসেজ হ্যান্ডলার
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status_msg = await update.message.reply_text("🎙️ সোনা পাখি ভয়েসটি শুনছে...")
    
    # টেলিগ্রাম থেকে ভয়েস ফাইল ডাউনলোড
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    local_filename = f"voice_{user_id}.ogg"
    await voice_file.download_to_drive(local_filename)
    
    # ভয়েস প্রসেস করে উত্তর আনা
    response_text = await process_voice_message(user_id, local_filename)
    
    # লোকাল ফাইল ডিলিট
    if os.path.exists(local_filename):
        os.remove(local_filename)
        
    await status_msg.edit_text(response_text)

# প্রাইভেট টেক্সট মেসেজ হ্যান্ডলার
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    status_msg = await update.message.reply_text("🤖 সোনা পাখি চিন্তা করছে...")
    
    response_text = await get_personal_chat_response(user_id, user_text)
    await status_msg.edit_text(response_text)

# চ্যানেলে পোস্ট এলে অটো রিভিউ
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_post = update.channel_post
    if not channel_post:
        return
    
    post_text = channel_post.text or channel_post.caption
    if not post_text:
        return
    
    review_text = await generate_channel_review(post_text.strip())
    
    if review_text:
        try:
            if channel_post.text:
                await channel_post.edit_text(review_text)
            elif channel_post.caption:
                await channel_post.edit_caption(caption=review_text[:1024])
        except Exception:
            await context.bot.send_message(chat_id=channel_post.chat_id, text=review_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_or_create_chat(user_id)
    await update.message.reply_text("হ্যালো! আমি আপনার পার্সোনাল ও চ্যানেল অ্যাসিস্ট্যান্ট সোনা পাখি। আপনি টেক্সট বা ভয়েস মেসেজ পাঠাতে পারেন!")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_chats:
        del user_chats[user_id]
    get_or_create_chat(user_id)
    await update.message.reply_text("🔄 আমাদের আগের সব মেমোরি রিসেট করা হয়েছে!")

# --- ৫. Main Execution ---
if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("reset", reset))
        
        # ভয়েস মেসেজের জন্য হ্যান্ডলার
        app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VOICE, handle_voice_message))
        
        # টেক্সট মেসেজের জন্য হ্যান্ডলার
        app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_message))
        
        # চ্যানেল পোস্টের জন্য হ্যান্ডলার
        app.add_handler(MessageHandler(filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION), handle_channel_post))
        
        print("Bot is starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
