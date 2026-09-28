import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import openai

# Environment Variables থেকে API Key নেয়া হবে
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
OPENAI_KEY = os.environ.get("OPENAI_KEY")

# Gemini Setup
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Gemini Response
async def get_gemini_response(prompt):
    if not GEMINI_KEY:
        return "Gemini API Key সেট করা নেই।"
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"

# OpenAI Response
async def get_openai_response(prompt):
    if not OPENAI_KEY:
        return "OpenAI API Key সেট করা নেই।"
    try:
        client = openai.AsyncOpenAI(api_key=OPENAI_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {str(e)}"

# Telegram Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    status_msg = await update.message.reply_text("🤖 *AI Agent প্রসেস করছে...*", parse_mode="Markdown")

    # প্যারালাল প্রসেসিং (Gemini + OpenAI)
    gemini_task = asyncio.create_task(get_gemini_response(user_text))
    openai_task = asyncio.create_task(get_openai_response(user_text))

    gemini_res, openai_res = await asyncio.gather(gemini_task, openai_task)

    final_reply = (
        f"📱 *Autonomous AI Agent Response*\n\n"
        f"--- 🔵 *Google Gemini* ---\n{gemini_res}\n\n"
        f"--- 🟢 *OpenAI ChatGPT* ---\n{openai_res}"
    )

    await status_msg.edit_text(final_reply, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("AI Agent running...")
    app.run_polling()
