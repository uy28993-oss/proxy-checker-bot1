import socket
import ssl
import threading
import ipaddress
from queue import Queue
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import tempfile

# ===== BOT TOKEN =====
TOKEN = os.getenv("TOKEN")

# ===== GLOBAL =====
q = Queue()
lock = threading.Lock()


# ===== LOAD TARGETS =====
def load_targets(source):
    targets = []

    try:
        if "/" in source:
            net = ipaddress.ip_network(source, strict=False)
            targets = [str(ip) for ip in net.hosts()]
        else:
            targets = [source]
    except:
        pass

    return targets


# ===== CDN DETECTION =====
def detect_cdn(response):
    r = response.lower()

    if "cloudflare" in r:
        return "Cloudflare"
    elif "cloudfront" in r:
        return "Cloudfront"
    elif "google" in r or "gws" in r:
        return "Google"
    return "Unknown"


# ===== SCANNER =====
def scan_worker(host, timeout, update, context, results):
    while not q.empty():
        ip, port = q.get()

        try:
            sock = socket.create_connection((ip, port), timeout=timeout)
            context_ssl = ssl.create_default_context()
            ssock = context_ssl.wrap_socket(sock, server_hostname=host)

            payload = f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n"
            ssock.sendall(payload.encode())

            resp = ssock.recv(4096).decode(errors="ignore")
            ssock.close()

            if "200" in resp or "101" in resp:
                cdn = detect_cdn(resp)
                result = f"{ip}:{port} | {cdn}"

                with lock:
                    results.append(result)

                # send live result
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ {result}"
                )

        except:
            pass

        q.task_done()


# ===== COMMAND =====
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(
                "Usage:\n/scan host cidr ports\n\nExample:\n/scan example.com 1.1.1.0/24 443,80"
            )
            return

        host = args[0]
        source = args[1]
        ports = [int(p) for p in args[2].split(",")]
        timeout = 5
        threads = 100

        targets = load_targets(source)

        if not targets:
            await update.message.reply_text("❌ Invalid target")
            return

        await update.message.reply_text(
            f"🚀 Scan started\nTargets: {len(targets)}\nPorts: {ports}"
        )

        results = []

        # fill queue
        for ip in targets:
            for port in ports:
                q.put((ip, port))

        # start threads
        for _ in range(threads):
            threading.Thread(
                target=scan_worker,
                args=(host, timeout, update, context, results),
                daemon=True
            ).start()

        q.join()

        # save results
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as f:
            for r in results:
                f.write(r + "\n")
            filename = f.name

        await update.message.reply_text("✅ Scan completed")

        # send file
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(filename, "rb")
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 HOST SCANNER BOT\n\nUse:\n/scan host cidr ports\n\nExample:\n/scan example.com 1.1.1.0/24 443,80"
    )


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()                asyncio.open_connection(ip, port), timeout=TIMEOUT
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
