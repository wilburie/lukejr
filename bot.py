''' ##       ##     ## ##    ## ########          ## ########
    ##       ##     ## ##   ##  ##                ## ##     ##
    ##       ##     ## ##  ##   ##                ## ##     ##
    ##       ##     ## #####    ######            ## ########
    ##       ##     ## ##  ##   ##          ##    ## ##   ##   
    ##       ##     ## ##   ##  ##          ##    ## ##    ##  
    ########  #######  ##    ## ########     ######  ##     ##        
    # 
    # version 1.1.0 (lastest update: fixed say command fully!) 
    # github version (dialouge, user ids, and private things removed)
'''

import discord
import os
import random
import asyncio
import uuid
import serial
# import queue
import re
import logging
import textwrap
from datetime import datetime, timedelta, timezone
from gtts import gTTS
from discord.ext import commands, tasks
from datetime import time

intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

USE_SERIAL = False # serial toggle

dia = [
"put dialouge here"]

vc_dia = [
"put vc dialouge here"]

user_insults = {
    1: [
        "user specific insults!"
    ],

    2: [
        "user specific insults!"
    ],

    3: [
        "user specific insults!"
    ],

    4: [
        "user specific insults!"
    ],

    5: [
        "user specific insults!"
    ]
}

# USER IDS

prefix_users = {
    1: ["nameforthisuser,"],
    2: ["nameforthisuser,", "nicknameforthisuser,"],
    3: ["nameforthisuser,"],
    4: ["nameforthisuser,"],
    5: ["nameforthisuser,"],
    6: ["nameforthisuser,"],
}

always_prefix = [
"alterantive prefixes here!"
]

reminders = []

def log(msg):
    print(msg, end="\n\n")  

    if USE_SERIAL and serial_conn:
        try:
            serial_conn.write((msg + "\r\n\r\n").encode())
        except Exception as e:
            print(f"serial write error: {e}", end="\n\n")

def vt520_wrap(text, width=80):
    lines = text.splitlines()
    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=width))
    return "\r\n".join(wrapped_lines)

# VT-520 OUTPUT

# i have a vt-520 serial monitor that i coded this to optionally output to... very cool!

SERIAL_PORT = "COM3"
BAUD_RATE = 38400

serial_conn = None
if USE_SERIAL:
    try:
        serial_conn = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        log(f"serial port {SERIAL_PORT} opened successfully")
    except Exception as e:
        log(f"failed to open serial port: {e}")
        serial_conn = None

# MORE VT-520 STUFF

class SerialHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            msg_wrapped = vt520_wrap(msg, width=80)
            print(msg_wrapped)
            if USE_SERIAL and serial_conn:
                serial_conn.write((msg_wrapped + "\r\n").encode())
        except Exception as e:
            print(f"serial logging error: {e}")

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

serial_handler = SerialHandler()

formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
serial_handler.setFormatter(formatter)

logger.addHandler(serial_handler)

token = "token here"

ff = "ffmpeg.exe file here"

audio_queue = asyncio.Queue()
is_playing_audio = False
vc_talking_enabled = True

audio_lock = asyncio.Lock()
current_tts_file = None
active_tts_files = []

TTS_FOLDER = "./tts"

if not os.path.exists(TTS_FOLDER):
    os.makedirs(TTS_FOLDER)

generalid = "general channel id here"
vcid = "vc channel id here"

# DEFS

def is_sleep_time():
    now = datetime.now(timezone(timedelta(hours=-5)))  # UTC-5
    return now.time() >= time(0, 0) and now.time() < time(6, 0)

# START LOOPS, ONREADY

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower().strip()
    prefixes = ["luke jr,"]

    for prefix in prefixes:
        if content.startswith(prefix):
            command_body = message.content[len(prefix):].strip()
            message.content = "!" + command_body
            ctx = await bot.get_context(message)
            await bot.invoke(ctx)
            return

    await bot.process_commands(message)

@bot.event
async def on_ready():
    log(f'{bot.user} online')
    send_random_message.start()
    vc_random_dialogue.start()
    voice_connection_monitor.start()
    reminder_loop.start()
    day_night_cycle.start()

    bot.loop.create_task(process_audio_queue())

    for file in os.listdir(TTS_FOLDER):
        try:
            os.remove(os.path.join(TTS_FOLDER, file))
        except:
            pass

# OLD AUDIO PROCESSOR (i worked so long and hard on it, it's here for a backup lol)

'''async def process_audio_queue(vc):
    global is_playing_audio
    global current_tts_file

    async with audio_lock:
        # wait until not yapping
        while is_playing_audio:
            await asyncio.sleep(0.1)

            # iiii want iiii want to be a machine,

        is_playing_audio = True

        while not audio_queue.empty():
            path, delete_after = audio_queue.get()
            if delete_after:
                current_tts_file = path
            
                # and iiii want tooo be shining chrome and clean,
            
            done = asyncio.Event()

            def after_playing(error):
                if error:
                    log(error)
                if delete_after and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        log(e)
                bot.loop.call_soon_threadsafe(done.set)

            vc.play(discord.FFmpegPCMAudio(path, executable=ff), after=after_playing)
            await done.wait()

        current_tts_file = None
        is_playing_audio = False'''

# SHINING CHROME AND CLEAN AUDIO QUEUE PROCESSOR

async def process_audio_queue():
    global current_tts_file

    while True:
        if audio_queue.empty():
            await asyncio.sleep(0.1)
            continue

        vc, path, delete_after = await audio_queue.get()

        if not vc or not vc.is_connected():
            continue

        current_tts_file = path if delete_after else None

        done = asyncio.Event()

        def after_playing(error):
            if error:
                log(error)
            if delete_after:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    log(f"delete error: {e}")
            if path in active_tts_files:
                active_tts_files.remove(path)

            bot.loop.call_soon_threadsafe(done.set)

        vc.play(discord.FFmpegPCMAudio(path, executable=ff), after=after_playing)
        await done.wait()

# MISC COMMANDS

@bot.command()
async def info(ctx):
    await ctx.reply("LUKE JR beep boop, V. 1.1.0, my father is luke but i am unaware of my creator")
    await ctx.send("CUH MANDS: !marco, !hitler, !coinflip, !joinvc, !leavevc, !say (thing to say), !play (thing to play), !stop, !testvc, !apiclearclutter, !sounds, use !talk to make me say things in vc every once in a while, and !shutup to make me quiet")
    await ctx.send("MORE CUH: !remind (10s, 10m, 10h) (message)")

@bot.command()
async def marco(ctx):
    await ctx.reply(f"polo! {round(bot.latency * 1000)}ms")

@bot.command()
async def hitler(ctx):
    await ctx.reply("https://en.wikipedia.org/wiki/Adolf_Hitler")

@bot.command()
async def coinflip(ctx):
    await ctx.reply(random.choice(["heads", "tails"]))

# CLEARCLUTTER

@bot.command()
async def apiclearclutter(ctx):
    deleted = 0
    for file in os.listdir(TTS_FOLDER):
        
        path = os.path.join(TTS_FOLDER, file)
        
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted += 1
        except Exception as e:
            log(f"error deleting {path}: {e}")
    
    await ctx.reply(f"deleted {deleted} tts files")

# SOUNDS

@bot.command()
async def sounds(ctx):
 
    folder = "./sounds"

    if not os.path.exists(folder):
        await ctx.reply("uhhhh something is very wrong here ask wilburie to fix it")
        return

    sounds = []

    for file in os.listdir(folder):
        if file.endswith(".mp3"):
            sounds.append(file.replace(".mp3", ""))

    if not sounds:
        await ctx.reply("uhhhh something is very wrong here ask wilburie to fix it")
        return

    await ctx.reply("sounds: " + ", ".join(sorted(sounds)))

# REMIND (THAT NOBODY USES)

@bot.command()
async def remind(ctx, time_str: str, *, message: str):
    match = re.match(r"(\d+)([smh])", time_str.lower())
    if not match:
        await ctx.reply("thats not how you use it")
        return
    
    amount, unit = match.groups()
    amount = int(amount)
    
    if unit == "s":
        delta = timedelta(seconds=amount)
    elif unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    
    remind_time = datetime.now(timezone.utc) + delta
    reminders.append((remind_time, message, ctx.author, ctx.channel))
    
    await ctx.reply(f"reminder set for {time_str} from now")


# TALK / SHUT UP

@bot.command()
async def talk(ctx):

    global vc_talking_enabled
    vc_talking_enabled = True

    await ctx.reply("i will speak")


@bot.command()
async def shutup(ctx):

    global vc_talking_enabled
    vc_talking_enabled = False

    await ctx.reply("fine")

# BIG AHH TESTVC COMMAND

@bot.command()
async def testvc(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.reply("im not in vc")
        return

    members = [m for m in vc.channel.members if not m.bot]

    text = random.choice(vc_dia)

    possible_prefixes = always_prefix.copy()

    for member in members:
        if member.id in prefix_users:
            possible_prefixes.extend(prefix_users[member.id])

    if random.random() < 0.5:
        text = f"{random.choice(possible_prefixes)} {text}"

    filename = f"{TTS_FOLDER}/tts_{uuid.uuid4()}.mp3"
    await asyncio.to_thread(gTTS(text).save, filename)

    await ctx.reply("testing testing 1 2 1 2")

    audio_queue.put_nowait((vc, filename, True)) 

# SAY

@bot.command()
async def say(ctx, *, text):
    vc = ctx.voice_client
    if not vc:
        await ctx.reply("im not in vc")
        return

    filename = f"{TTS_FOLDER}/tts_{uuid.uuid4()}.mp3"

    await asyncio.to_thread(gTTS(text).save, filename)

    await ctx.reply("ok")

    active_tts_files.append(filename)
    audio_queue.put_nowait((vc, filename, True))

# SOUNDBOARD

@bot.command()
async def play(ctx, name):
    vc = ctx.voice_client
    if not vc:
        await ctx.reply("im not in vc")
        return

    path = f"./sounds/{name}.mp3"

    if not os.path.isfile(path):
        await ctx.reply("thats not a sound")
        return

    await ctx.reply("ok")

    # do not delete soundboard files
    audio_queue.put_nowait((vc, path, False))

# JOIN / LEAvE VC

@bot.command()
async def joinvc(ctx):
    channel = bot.get_channel(vcid)
    if channel:
        if not ctx.voice_client:

            vc = await channel.connect()
            await ctx.reply("ok")

            text = "hi guys"
            filename = f"{TTS_FOLDER}/tts_{uuid.uuid4()}.mp3"
            await asyncio.to_thread(gTTS(text).save, filename)

            audio_queue.put_nowait((vc, filename, True)) 

@bot.command()
async def leavevc(ctx):
    vc = ctx.voice_client
    if vc:
        await ctx.reply("ok")
        text = "bye guys"
        filename = f"{TTS_FOLDER}/tts_{uuid.uuid4()}.mp3"
        await asyncio.to_thread(gTTS(text).save, filename)

        audio_queue.put_nowait((vc, filename, True)) 
        await vc.disconnect()

# STOP COMMANDS

@bot.command()
async def stop(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.reply("im not in vc")
        return

    if vc.is_playing():
        vc.stop()

    global current_tts_file
    if current_tts_file and os.path.exists(current_tts_file):
        try:
            os.remove(current_tts_file)
            active_tts_files.remove(current_tts_file)
        except Exception as e:
            log(f"stop delete error: {e}")
    current_tts_file = None

    await ctx.reply("stopped current TTS")

@bot.command()
async def stopall(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()

    while not audio_queue.empty():
        try:
            queued_vc, path, delete_after = audio_queue.get_nowait()
            if delete_after and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log(f"stopall queue delete error: {e}")

    for path in active_tts_files.copy():
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log(f"stopall active delete error: {e}")
        active_tts_files.remove(path)

    await ctx.reply("ok, stopped everything and cleared queue")

# TASK LOOPS

@tasks.loop(seconds=30)
async def day_night_cycle():
    global last_goodnight_date, last_goodmorning_date

    now = datetime.now(timezone(timedelta(hours=-5)))
    current_date = now.date()
    current_time = now.time()

    channel = bot.get_channel(generalid)
    if not channel:
        return

    if current_time.hour == 0 and current_time.minute == 0:
        if last_goodnight_date != current_date:
            await channel.send("goodnight guys")
            last_goodnight_date = current_date

    if current_time.hour == 6 and current_time.minute == 0:
        if last_goodmorning_date != current_date:
            await channel.send("wakey wakey eggs and bakey")
            last_goodmorning_date = current_date
            
# day night cycle does not work, i don't know why lol

@tasks.loop(seconds=10)
async def reminder_loop():
    now = datetime.now(timezone.utc)
    for reminder in reminders.copy():
        remind_time, message, user, channel = reminder
        if now >= remind_time:
                await channel.send(f"{user.mention} reminder: {message}")
                reminders.remove(reminder)

@tasks.loop(count=1)
async def send_random_message():
    while True:
        await asyncio.sleep(random.randint(1, 3600))
        channel = bot.get_channel(generalid)
        if channel and not is_sleep_time():
            await channel.send(random.choice(dia))

@tasks.loop(count=1)
async def vc_random_dialogue():
    await bot.wait_until_ready()

    while True:
        await asyncio.sleep(random.randint(1, 300))

        vc = bot.voice_clients[0] if bot.voice_clients else None
        if not vc or not vc.channel:
            continue
        if vc.is_playing() or not vc_talking_enabled:
            continue

        members = [m for m in vc.channel.members if not m.bot]
        if not members:
            continue

        text = None

        insult_targets = [m for m in members if m.id in user_insults]

        if insult_targets and random.random() < 0.1:
            target = random.choice(insult_targets)

            if target.id in prefix_users:
                name = random.choice(prefix_users[target.id])
            else:
                name = target.display_name.lower() + ","

            insult = random.choice(user_insults[target.id])
            text = f"{name} {insult}"

        else:
            text = random.choice(vc_dia)

            possible_prefixes = always_prefix.copy()
            for member in members:
                if member.id in prefix_users:
                    possible_prefixes.extend(prefix_users[member.id])

            if random.random() < 0.5:
                text = f"{random.choice(possible_prefixes)} {text}"

        filename = f"{TTS_FOLDER}/tts_{uuid.uuid4()}.mp3"
        await asyncio.to_thread(gTTS(text).save, filename)
        

        audio_queue.put_nowait((vc, filename, True)) 

@tasks.loop(seconds=10)
async def voice_connection_monitor():
    for vc in bot.voice_clients:
        if not vc.is_connected():
            try:
                await vc.connect()
                log(f"reconnected to VC: {vc.channel.name}")
            except Exception as e:
                log(f"failed to reconnect to VC: {e}")

# log ze cummands

log([cmd.name for cmd in bot.commands])

# RUN

bot.run(token)

# i would like to say that this is horribly coded, but it was very fun!
# many things do not work properly, i just added it here as proof that i coded...
# and, i'm shocked that the gtts api has not like flagged me for using it so much.
# if anything here is stupid, i did code this during a vc marathon with my friends (we made it 500 hours), so it's not very serious.
# thanks!