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

# প্রতিটি ইউজারের চ্যাট হিস্ট্রি ধরে রাখার জন্য ডিকশনারি
user_chats = {}

# --- ৩. AI Response Function with Memory & Auto-Retry ---
async def get_gemini_response(user_id, prompt):
    if not client:
        return "GEMINI_KEY পাওয়া যায়নি!"
    
    # নতুন ইউজার হলে তার জন্য একটি চ্যাট সেশন তৈরি করবে (gemini-3.8-flash দিয়ে)
    if user_id not in user_chats:
        user_chats[user_id] = client.chats.create(model='gemini-3.8-flash')
    
    chat = user_chats[user_id]

    # ৩ বার চেষ্টা করার লুপ (503 High Demand এরর এড়াতে)
    for attempt in range(3):
        try:
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                await asyncio.sleep(2) # ২ সেকেন্ড অপেক্ষা করে আবার চেষ্টা করবে
                continue
            return f"AI Error: {str(e)}"

# --- ৪. Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # /start দিলে নতুন করে চ্যাট সেশন শুরু হবে
    if client:
        user_chats[user_id] = client.chats.create(model='gemini-3.8-flash')
    await update.message.reply_text("হ্যালো! আমি আপনার এসিস্ট্যান্ট সোনা পাখি। আমি আগের কথাবার্তা মনে রাখতে পারবো। আমাকে যেকোনো প্রশ্ন করতে পারেন।")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if client:
        user_chats[user_id] = client.chats.create(model='gemini-3.8-flash')
    await update.message.reply_text("🔄 আমাদের আগের সব কথা রিসেট করা হয়েছে!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    status_msg = await update.message.reply_text("🤖 সোনা পাখি চিন্তা করছে...")
    
    response_text = await get_gemini_response(user_id, user_text)
    
    await status_msg.edit_text(response_text)

# --- ৫. Main Execution ---
if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("reset", reset))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Bot is starting...")
        app.run_polling()
