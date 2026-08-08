import asyncio
import ipaddress
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ===== TOKEN =====
TOKEN = os.getenv(8670058172:AAFm17MDc8FDKk0gTKkdV31hvx3pvDYu80g) 
TIMEOUT = 3
CONCURRENCY = 200

# CDN detection
CDN_MAP = {
    "cloudflare": "cloudflare",
    "cloudfront": "cloudfront",
    "google": "google",
    "akamai": "akamai",
    "fastly": "fastly"
}

user_data_store = {}

# ===== CDN DETECT =====
def detect_cdn(data):
    data = data.lower()
    for key in CDN_MAP:
        if key in data:
            return CDN_MAP[key]
    return "unknown"


# ===== CHECK PROXY =====
async def check_proxy(ip, port, sem, results):
    try:
        async with sem:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=TIMEOUT
            )

            request = f"GET / HTTP/1.1\r\nHost: google.com\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()

            data = await asyncio.wait_for(reader.read(1024), timeout=TIMEOUT)
            text = data.decode(errors="ignore")

            cdn = detect_cdn(text)
            results.append(f"{ip} {port} {cdn}\n")

            writer.close()
            await writer.wait_closed()

    except:
        pass


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send TXT file with IPs OR send CIDR (example: 1.1.1.0/24)"
    )


# ===== FILE INPUT =====
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    path = f"{update.message.from_user.id}.txt"
    await file.download_to_drive(path)

    with open(path) as f:
        targets = [line.strip() for line in f if line.strip()]

    user_data_store[update.message.from_user.id] = {"targets": targets}

    await update.message.reply_text("Now send ports (example: 80,443,8080)")


# ===== TEXT INPUT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # CIDR input
    if "/" in text:
        net = ipaddress.ip_network(text, strict=False)
        targets = [str(ip) for ip in net.hosts()]
        user_data_store[user_id] = {"targets": targets}
        await update.message.reply_text("Now send ports (example: 80,443)")
        return

    # Ports input
    if user_id in user_data_store:
        ports = [int(p.strip()) for p in text.split(",")]
        targets = user_data_store[user_id]["targets"]

        await update.message.reply_text("Scanning started ⚡")

        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = []
        results = []

        for ip in targets:
            for port in ports:
                tasks.append(check_proxy(ip, port, sem, results))

        await asyncio.gather(*tasks)

        output_file = f"{user_id}_working.txt"
        with open(output_file, "w") as f:
            f.writelines(results)

        await update.message.reply_document(open(output_file, "rb"))
        await update.message.reply_text(f"Done ✅ Found {len(results)} working proxies")

        user_data_store.pop(user_id, None)


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
