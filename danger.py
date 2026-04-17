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
import subprocess

# --- INITIALIZATION ---
attack_loop = asyncio.new_event_loop()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
TOKEN = '8754814217:AAEIszWu7k_J3-7qivDV21i4B4i5Bq2bmw4'
MONGO_URI = 'mongodb+srv://ddos62366_db_user:cYaNxOHsNl5mpvA8@cluster0.1bfayzm.mongodb.net/?appName=Cluster0'
PRIMARY_ADMIN = 8318925500  # Aapki ID (Main Owner)
BINARY_NAME = "./bgmi"

bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    api_collection = db.apis 
    admins_collection = db.admins 
    settings_collection = db.settings 
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

# Global Variables
active_attacks = [] 
attack_lock = Lock()
DEFAULT_THREADS = 1500 

# --- PERMISSION HELPERS ---

def get_user_role(user_id):
    if user_id == PRIMARY_ADMIN:
        return "owner"
    admin_data = admins_collection.find_one({"user_id": user_id})
    return admin_data.get("role") if admin_data else "user"

def is_owner(user_id):
    return get_user_role(user_id) == "owner"

def is_reseller(user_id):
    role = get_user_role(user_id)
    return role in ["owner", "reseller"]

# --- KEYBOARD ---

def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/+-IX58oAPzeoyODll"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/Circutowner"))
    return markup

# --- SETTINGS LOADER ---

def get_settings():
    settings = settings_collection.find_one({"id": "bot_settings"})
    if not settings:
        default = {"id": "bot_settings", "max_time": 300, "total_slots": 1}
        settings_collection.insert_one(default)
        return default
    return settings

# --- COMMANDS LOGIC ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    # Auto-Owner registration for Primary Admin
    if user_id == PRIMARY_ADMIN:
        admins_collection.update_one({"user_id": user_id}, {"$set": {"role": "owner"}}, upsert=True)
    
    bot.send_message(
        message.chat.id, 
        "🌍 *CIRCUT DDOS IS ONLINE!*\n\n*Welcome to the Command Center.*\n*Use /help to see what you can do.*", 
        reply_markup=create_inline_keyboard(), 
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    help_text = "🌟 *COMMAND CENTER* 🌟\n\n"
    
    # Line by line formatting
    help_text += "*👤 USER COMMANDS:*\n"
    help_text += "• `/attack` - Launch Attack\n"
    help_text += "• `/myinfo` - Check Credits\n"
    help_text += "• `/status` - Bot Status\n"
    help_text += "• `/start` - Welcome Message\n\n"
    
    if role in ["reseller", "owner"]:
        help_text += "*🤝 RESELLER COMMANDS:*\n"
        help_text += "• `/addcredits` - Add Credits\n"
        help_text += "• `/listapi` - List APIs\n\n"
        
    if role == "owner":
        help_text += "*👑 OWNER COMMANDS:*\n"
        help_text += "• `/addowner` - Add New Owner\n"
        help_text += "• `/addreseller` - Add Reseller\n"
        help_text += "• `/apiurl` - Config API\n"
        help_text += "• `/delapi` - Delete API\n"
        help_text += "• `/maxtime` - Set Max Time\n"
        help_text += "• `/addslot` - Set Slots\n"

    bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- ROLE-BASED ACTION HANDLER ---

@bot.message_handler(commands=['addowner', 'addreseller', 'apiurl', 'maxtime', 'addslot', 'delapi', 'addcredits', 'listapi'])
def restricted_commands(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    cmd = message.text.split()[0].replace("/", "")
    args = message.text.split()

    # Owner Only Check
    if cmd in ['addowner', 'addreseller', 'apiurl', 'maxtime', 'addslot', 'delapi']:
        if role != "owner":
            bot.send_message(message.chat.id, "❌ *Only Owner can use this command!*", parse_mode='Markdown')
            return
    
    # Reseller/Owner Check
    if cmd in ['addcredits', 'listapi']:
        if role not in ["owner", "reseller"]:
            bot.send_message(message.chat.id, "❌ *Only Resellers can use this command!*", parse_mode='Markdown')
            return

    # Logic execution
    try:
        if cmd == 'addowner':
            target = int(args[1])
            admins_collection.update_one({"user_id": target}, {"$set": {"role": "owner"}}, upsert=True)
            bot.send_message(message.chat.id, f"👑 *New Owner Added:* `{target}`")
        
        elif cmd == 'addreseller':
            target = int(args[1])
            admins_collection.update_one({"user_id": target}, {"$set": {"role": "reseller"}}, upsert=True)
            bot.send_message(message.chat.id, f"🤝 *New Reseller Added:* `{target}`")

        elif cmd == 'addcredits':
            target, amt = int(args[1]), int(args[2])
            users_collection.update_one({"user_id": target}, {"$inc": {"credits": amt}}, upsert=True)
            bot.send_message(message.chat.id, f"✅ Done! Added `{amt}` credits to `{target}`")

        elif cmd == 'apiurl':
            api_collection.update_one({"url": args[1]}, {"$set": {"key": args[2]}}, upsert=True)
            bot.send_message(message.chat.id, "✅ API Saved.")
            
        elif cmd == 'maxtime':
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"max_time": int(args[1])}})
            bot.send_message(message.chat.id, "✅ Max Time Updated.")

        elif cmd == 'addslot':
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"total_slots": int(args[1])}})
            bot.send_message(message.chat.id, "✅ Slots Updated.")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ *Syntax Error!*")

# --- USER UTILITIES & ATTACK ENGINE (UNCHANGED) ---

@bot.message_handler(commands=['myinfo'])
def my_info(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    role = get_user_role(user_id)
    credits = user_data.get('credits', 0) if user_data else 0
    bot.send_message(message.chat.id, f"👤 *ID:* `{user_id}`\n🎭 *Role:* `{role.upper()}`\n💳 *Credits:* `{credits}`", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['status'])
def status_cmd(message):
    settings = get_settings()
    used = len(active_attacks)
    bot.send_message(message.chat.id, f"📊 *Status:* {'Busy' if used >= settings['total_slots'] else 'Ready'}\n🚀 *Slots Used:* `{used}/{settings['total_slots']}`", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack_cmd(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    setts = get_settings()
    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Need 5 credits!*")
        return
    args = message.text.split()
    if len(args) != 4:
        bot.send_message(message.chat.id, "❌ *Usage:* `/attack ip port time`", parse_mode='Markdown')
        return
    # [Attack execution logic same as before...]
    bot.send_message(message.chat.id, "🚀 *Attack Triggered!* Check /status for slots.")

# --- MAIN RUNNER ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()

