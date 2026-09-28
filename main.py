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

# --- ২. Environment Variables & New Gemini Client ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()

client = None
if GEMINI_KEY:
    client = genai.Client(api_key=GEMINI_KEY)

# --- ৩. AI Response Function ---
async def get_gemini_response(prompt):
    if not client:
        return "GEMINI_KEY পাওয়া যায়নি!"
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- ৪. Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("হ্যালো! আমি আপনার AI Assistant Agent। আমাকে যেকোনো প্রশ্ন করতে পারেন।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    status_msg = await update.message.reply_text("🤖 AI Agent প্রসেস করছে...")
    
    response_text = await get_gemini_response(user_text)
    
    await status_msg.edit_text(response_text)

# --- ৫. Main Execution ---
if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Bot is starting...")
        app.run_polling()
