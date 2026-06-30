#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import os
import socket
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import logging
from datetime import datetime
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys

# ==============================================
# CONFIG
# ==============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8961056279:AAHOiUU3W9dVSIMIlIA_F2PEwbwCZ99KqsE")
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================
# HEALTH CHECK SERVER
# ==============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "running"}).encode())
    
    def log_message(self, format, *args):
        pass

def start_health_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
        logger.info(f"Health server on port {PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")

# ==============================================
# STATES
# ==============================================
(IP_INPUT, PIN_INPUT, IFSC_INPUT, VEHICLE_INPUT) = range(4)

# ==============================================
# HELPERS
# ==============================================
def safe_request(url, timeout=15):
    h = {"User-Agent": "Mozilla/5.0"}
    for i in range(2):
        try:
            return requests.get(url, headers=h, timeout=timeout)
        except:
            if i == 1: raise
            time.sleep(2)

def fmt(data):
    return f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"

# ==============================================
# API FUNCTIONS
# ==============================================

async def get_ip_info(ip):
    result = {"status": "success", "query_ip": ip, "powered_by": "NEUTRONNNN_KILLER"}
    try:
        r = safe_request(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query,mobile,proxy,hosting")
        d = r.json()
        if d.get('status') == 'success':
            result["location"] = {"ip": d.get('query'), "country": d.get('country'), "region": d.get('regionName'), "city": d.get('city'), "zip": d.get('zip'), "timezone": d.get('timezone')}
            result["coordinates"] = {"latitude": d.get('lat'), "longitude": d.get('lon'), "google_maps": f"https://maps.google.com/?q={d.get('lat')},{d.get('lon')}"}
            result["network"] = {"isp": d.get('isp'), "org": d.get('org'), "as": d.get('as')}
            result["flags"] = {"mobile": d.get('mobile'), "proxy": d.get('proxy'), "hosting": d.get('hosting')}
        else:
            result = {"status": "error", "message": d.get('message', 'Error')}
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    return result

async def get_pin_info(pin):
    result = {"status": "success", "pincode": pin, "powered_by": "NEUTRONNNN_KILLER"}
    try:
        r = safe_request(f"https://api.postalpincode.in/pincode/{pin}")
        d = r.json()
        if d[0]['Status'] == "Success":
            offices = d[0]['PostOffice']
            result["total"] = len(offices)
            result["summary"] = {"total": len(offices), "delivery": sum(1 for o in offices if o.get('DeliveryStatus')=='Delivery'), "non_delivery": sum(1 for o in offices if o.get('DeliveryStatus')!='Delivery')}
            result["post_offices"] = [{"name": o.get('Name'), "district": o.get('District'), "state": o.get('State'), "pincode": o.get('Pincode'), "delivery": o.get('DeliveryStatus'), "division": o.get('Division'), "region": o.get('Region'), "circle": o.get('Circle'), "taluk": o.get('Taluk'), "block": o.get('Block')} for o in offices]
        else:
            result = {"status": "error", "message": d[0].get('Message')}
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    try:
        r2 = safe_request(f"https://api.zippopotam.us/in/{pin}")
        if r2.status_code == 200:
            pl = r2.json().get('places', [])
            if pl:
                p = pl[0]
                result["location"] = {"city": p.get('place name'), "state": p.get('state'), "lat": p.get('latitude'), "lon": p.get('longitude'), "maps": f"https://maps.google.com/?q={p.get('latitude')},{p.get('longitude')}"}
    except:
        pass
    return result

async def get_ifsc_info(ifsc):
    result = {"status": "success", "ifsc": ifsc, "powered_by": "NEUTRONNNN_KILLER"}
    try:
        r = safe_request(f"https://ifsc.razorpay.com/{ifsc}")
        if r.status_code == 404:
            return {"status": "error", "message": "IFSC not found"}
        d = r.json()
        result["bank"] = {"name": d.get('BANK'), "branch": d.get('BRANCH'), "ifsc": d.get('IFSC'), "micr": d.get('MICR'), "contact": d.get('CONTACT')}
        result["address"] = {"address": d.get('ADDRESS'), "city": d.get('CITY'), "district": d.get('DISTRICT'), "state": d.get('STATE')}
        result["services"] = {"rtgs": d.get('RTGS'), "neft": d.get('NEFT'), "imps": d.get('IMPS'), "upi": d.get('UPI')}
        result["bank_code"] = ifsc[:4]
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    return result

async def get_vehicle_info(rc):
    result = {"status": "success", "reg_no": rc, "powered_by": "NEUTRONNNN_KILLER", "telegram": "https://t.me/NEUTRONNNN_KILLER"}
    try:
        r = safe_request(f"https://vahanx.in/rc-search/{rc}", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        def gv(label):
            try:
                for div in soup.select(".hrcd-cardbody"):
                    s = div.find("span")
                    if s and label.lower() in s.text.lower():
                        p = div.find("p")
                        return p.text.strip() if p else None
            except:
                return None
        def gv2(label):
            try:
                e = soup.find("span", string=label)
                if e:
                    p = e.find_parent("div").find("p")
                    return p.text.strip() if p else None
            except:
                return None
        o = gv("Owner Name") or gv2("Owner Name")
        if o:
            result["basic_info"] = {"owner": o, "father": gv2("Father's Name") or "NA", "model": gv("Modal Name") or gv2("Model Name") or "NA", "address": gv("Address") or gv2("Address") or "NA", "city": gv("City Name") or gv2("City") or "NA", "phone": gv("Phone") or gv2("Mobile") or "NA"}
            result["vehicle"] = {"model": gv("Modal Name") or "NA", "maker": gv2("Maker Model") or "NA", "fuel": gv("Fuel Type") or gv2("Fuel Type") or "NA", "norms": gv2("Fuel Norms") or "NA", "class": gv2("Vehicle Class") or "NA", "color": gv2("Color") or "NA", "chassis": gv2("Chassis Number") or "NA", "engine": gv2("Engine Number") or "NA", "cc": gv2("Cubic Capacity") or "NA", "seat": gv2("Seating Capacity") or "NA"}
            result["validity"] = {"reg_date": gv2("Registration Date") or "NA", "fitness": gv2("Fitness Upto") or "NA", "tax": gv2("Tax Upto") or "NA", "insurance": gv2("Insurance Expiry") or "NA", "age": gv2("Vehicle Age") or "NA"}
            result["insurance"] = {"company": gv2("Insurance Company") or gv("Insurance Company") or "NA", "policy": gv2("Insurance No") or "NA", "expiry": gv2("Insurance Expiry") or "NA"}
            result["puc"] = {"no": gv2("PUC No") or "NA", "upto": gv2("PUC Upto") or "NA"}
            result["other"] = {"rto": gv2("Registered RTO") or "NA", "serial": gv2("Owner Serial No") or "NA", "financer": gv2("Financier Name") or "NA", "blacklist": gv2("Blacklist Status") or "NA"}
        else:
            result = {"status": "error", "message": "RC not found"}
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    return result

# ==============================================
# BOT HANDLERS
# ==============================================

async def start(update, context):
    kb = [[InlineKeyboardButton("🌐 IP Info", callback_data='ip')],
          [InlineKeyboardButton("📮 PIN Info", callback_data='pin')],
          [InlineKeyboardButton("🏦 IFSC Info", callback_data='ifsc')],
          [InlineKeyboardButton("🚗 Vehicle Info", callback_data='vehicle')]]
    await update.message.reply_text("🔍 *INFO GATHERING BOT*\n\n🌐 IP | 📮 PIN | 🏦 IFSC | 🚗 Vehicle\n\n👇 Select:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def menu(update, context):
    kb = [[InlineKeyboardButton("🌐 IP", callback_data='ip')],
          [InlineKeyboardButton("📮 PIN", callback_data='pin')],
          [InlineKeyboardButton("🏦 IFSC", callback_data='ifsc')],
          [InlineKeyboardButton("🚗 Vehicle", callback_data='vehicle')]]
    await update.message.reply_text("🔍 *Select:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def button(update, context):
    q = update.callback_query
    await q.answer()
    msgs = {'ip': ("🌐 *Enter IP/Domain:*\n`8.8.8.8`", IP_INPUT),
            'pin': ("📮 *Enter 6-Digit PIN:*\n`110001`", PIN_INPUT),
            'ifsc': ("🏦 *Enter IFSC:*\n`SBIN0000001`", IFSC_INPUT),
            'vehicle': ("🚗 *Enter Vehicle No:*\n`RJ18CF3690`", VEHICLE_INPUT)}
    if q.data in msgs:
        await q.edit_message_text(msgs[q.data][0], parse_mode='Markdown')
        return msgs[q.data][1]

async def handle_ip(update, context):
    u = update.message.text.strip()
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', u):
        try:
            u = socket.gethostbyname(u)
        except:
            await update.message.reply_text("❌ Invalid!")
            return IP_INPUT
    m = await update.message.reply_text("🔍 Fetching...")
    r = await get_ip_info(u)
    await m.delete()
    await update.message.reply_text(f"🌐 *IP INFO*\n{fmt(r)}", parse_mode='Markdown')
    await menu(update, context)
    return ConversationHandler.END

async def handle_pin(update, context):
    p = update.message.text.strip()
    if not p.isdigit() or len(p) != 6:
        await update.message.reply_text("❌ 6 digits!")
        return PIN_INPUT
    m = await update.message.reply_text("🔍 Fetching...")
    r = await get_pin_info(p)
    await m.delete()
    
    s = {"status": r.get("status"), "pincode": r.get("pincode"), "total": r.get("total"), "summary": r.get("summary"), "location": r.get("location"), "powered_by": r.get("powered_by")}
    await update.message.reply_text(f"📮 *SUMMARY*\n{fmt(s)}", parse_mode='Markdown')
    
    offices = r.get("post_offices", [])
    if offices:
        for i in range(0, len(offices), 5):
            chunk = offices[i:i+5]
            cn = (i//5)+1
            tc = (len(offices)+4)//5
            cd = {"pincode": p, "chunk": f"{cn}/{tc}", "offices": chunk}
            if cn == tc:
                cd["note"] = f"Total {len(offices)} offices shown."
            await update.message.reply_text(f"📮 *OFFICES ({cn}/{tc})*\n{fmt(cd)}", parse_mode='Markdown')
    
    await menu(update, context)
    return ConversationHandler.END

async def handle_ifsc(update, context):
    i = update.message.text.strip().upper()
    if len(i) != 11:
        await update.message.reply_text("❌ 11 chars!")
        return IFSC_INPUT
    m = await update.message.reply_text("🔍 Fetching...")
    r = await get_ifsc_info(i)
    await m.delete()
    await update.message.reply_text(f"🏦 *IFSC INFO*\n{fmt(r)}", parse_mode='Markdown')
    await menu(update, context)
    return ConversationHandler.END

async def handle_vehicle(update, context):
    v = update.message.text.strip().upper()
    if len(v) < 8:
        await update.message.reply_text("❌ Invalid!")
        return VEHICLE_INPUT
    m = await update.message.reply_text("🔍 Fetching...")
    r = await get_vehicle_info(v)
    await m.delete()
    await update.message.reply_text(f"🚗 *VEHICLE INFO*\n{fmt(r)}", parse_mode='Markdown')
    await menu(update, context)
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("❌ Cancelled.")
    await menu(update, context)
    return ConversationHandler.END

# ==============================================
# MAIN
# ==============================================
def main():
    print("Starting bot...", flush=True)
    
    # Start health server
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    print(f"Health server started on port {PORT}", flush=True)
    
    # Check token
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("ERROR: BOT_TOKEN not set!", flush=True)
        sys.exit(1)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(button)],
            states={
                IP_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ip)],
                PIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin)],
                IFSC_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ifsc)],
                VEHICLE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vehicle)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('menu', menu))
        app.add_handler(conv)
        
        print("Bot is running...", flush=True)
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
