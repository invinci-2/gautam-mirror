import shutil, psutil
import signal
import os
import importlib


from pyrogram import idle, filters, types, emoji
from bot import app
from sys import executable
from datetime import datetime
import pytz
import time
import threading

from telegram.error import BadRequest, Unauthorized
from telegram import ParseMode, BotCommand, InputTextMessageContent, InlineQueryResultArticle, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Filters, InlineQueryHandler, MessageHandler, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.utils.helpers import escape_markdown
from telegram.ext import CommandHandler
from bot import bot, dispatcher, updater, botStartTime, LOG_GROUP, BOT_NO, IGNORE_PENDING_REQUESTS, CHAT_NAME, app, OWNER_ID
from bot.helper.ext_utils import fs_utils
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import *
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
from .helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper import button_build
from bot.helper import get_text, check_heroku

from .modules import authorize, cancel_mirror, mirror_status, mirror, shell, eval, delete, speedtest, usage, mediainfo, config

now=datetime.now(pytz.timezone('Asia/Kolkata'))


def stats(update, context):
    global main
    currentTime = get_readable_time(time.time() - botStartTime)
    current = now.strftime('%m/%d %I:%M:%S %p')
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    stats = f"〣 {CHAT_NAME} 〣\n\n" \
            f'Rᴜɴɴɪɴɢ Sɪɴᴄᴇ : {currentTime}\n' \
            f'Sᴛᴀʀᴛᴇᴅ Aᴛ : {current}\n\n' \
            f'<b>DISK INFO</b>\n' \
            f'<b><i>Total</i></b>: {total}\n' \
            f'<b><i>Used</i></b>: {used} ~ ' \
            f'<b><i>Free</i></b>: {free}\n\n' \
            f'<b>DATA USAGE</b>\n' \
            f'<b><i>UL</i></b>: {sent} ~ ' \
            f'<b><i>DL</i></b>: {recv}\n\n' \
            f'<b>SERVER STATS</b>\n' \
            f'<b><i>CPU</i></b>: {cpuUsage}%\n' \
            f'<b><i>RAM</i></b>: {memory}%\n' \
            f'<b><i>DISK</i></b>: {disk}%\n'
    keyboard = [[InlineKeyboardButton("CLOSE", callback_data="stats_close")]]
    main = sendMarkup(stats, context.bot, update, reply_markup=InlineKeyboardMarkup(keyboard))


def call_back_data(update, context):
    global main
    query = update.callback_query
    query.answer()
    main.delete()
    main = None


def start(update:Update, context:CallbackContext) -> None:
    LOGGER.info('UID: {} - UN: {} - MSG: {}'.format(update.message.chat.id,update.message.chat.username,update.message.text))
    uptime = get_readable_time((time.time() - botStartTime))
    if CustomFilters.authorized_user(update) or CustomFilters.authorized_chat(update):
        if update.message.chat.type == "private" :
            reply_message = sendMessage(f"<b>Hei {update.message.chat.first_name}</b>,\n\nWelcome To One Of A {CHAT_NAME} Bot", context.bot, update)
            threading.Thread(target=auto_delete_message, args=(bot, update.message, reply_message)).start()
        else :
            sendMessage(f"<b>I'm Awake Already!</b>\n<b>Haven't Slept Since:</b> <code>{uptime}</code>", context.bot, update)
    else :
        uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
        sendMessage(f"<b>Hei {uname},</b>\n\n<b>If You Want To Use Me</b>\n\n<b>You Have To Join @GautamS_Mirror</b>\n\n<b><i>NOTE : All The Uploaded Links Will Be Sent Here In Your Private Chat From Now</i></b>", context.bot, update)



def restart(update, context):
    restart_message = sendMessage(f"Restarting The Bot {BOT_NO}", context.bot, update)
    LOGGER.info(f'Restarting The Bot...')
    # Save restart message object in order to reply to it after restarting
    with open(".restartmsg", "w") as f:
        f.truncate(0)
        f.write(f"{restart_message.chat.id}\n{restart_message.message_id}\n")
    fs_utils.clean_all()
    os.execl(executable, executable, "-m", "bot")



@app.on_message(filters.command([BotCommands.RebootCommand]) & filters.user(OWNER_ID))
@check_heroku
async def gib_restart(client, message, hap):
    msg_ = await message.reply_text("Restarting Dynos")
    hap.restart()


def ping(update, context):
    start_time = int(round(time.time() * 1000))
    reply = sendMessage("Starting Ping", context.bot, update)
    end_time = int(round(time.time() * 1000))
    editMessage(f'{end_time - start_time} ms', reply)



def log(update, context):
    sendLogFile(context.bot, update)



def bot_help(update, context):
    help_string_adm = f'''
/{BotCommands.HelpCommand}: To get this message

/{BotCommands.MirrorCommand} [download_url][magnet_link]: Start mirroring the link to Google Drive

/{BotCommands.TarMirrorCommand} [download_url][magnet_link]: Start mirroring and upload the archived (.tar) version of the download

/{BotCommands.UnzipMirrorCommand} [download_url][magnet_link]: Starts mirroring and if downloaded file is any archive, extracts it to Google Drive

/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive

/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive Links

/{BotCommands.DeleteCommand} [drive_url]: Delete file from Google Drive (Only Owner & Sudo)

/{BotCommands.WatchCommand} [youtube-dl supported link]: Mirror through youtube-dl. Click /{BotCommands.WatchCommand} for more help

/{BotCommands.TarWatchCommand} [youtube-dl supported link]: Mirror through youtube-dl and tar before uploading

/{BotCommands.CancelMirror}: Reply to the message by which the download was initiated and that download will be cancelled

/{BotCommands.CancelAllCommand}: Cancel all running tasks

/{BotCommands.ListCommand} [search term]: Searches the search term in the Google Drive, If found replies with the link

/{BotCommands.StatusCommand}: Shows a status of all the downloads

/{BotCommands.StatsCommand}: Show Stats of the machine the bot is hosted on

/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot

/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Can only be invoked by Owner & Sudo of the bot)

/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Can only be invoked by Owner & Sudo of the bot)

/{BotCommands.AuthorizedUsersCommand}: Show authorized users (Only Owner & Sudo)

/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner)

/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner)

/{BotCommands.RestartCommand}: Restart the bot

/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports

/{BotCommands.ConfigMenuCommand}: Get Info Menu about bot config (Owner Only)

/{BotCommands.UpdateCommand}: Update Bot from Upstream Repo (Owner Only)

/{BotCommands.UsageCommand}: To see Heroku Dyno Stats (Owner & Sudo only)

/{BotCommands.SpeedCommand}: Check Internet Speed of the Host

/{BotCommands.MediaInfoCommand}: Get detailed info about replied media (Only for Telegram file)

/{BotCommands.ShellCommand}: Run commands in Shell (Terminal)

/{BotCommands.ExecHelpCommand}: Get help for Executor module

/{BotCommands.TsHelpCommand}: Get help for Torrent search module
'''

    help_string = f'''
/{BotCommands.HelpCommand}: To get this message

/{BotCommands.MirrorCommand} [download_url][magnet_link]: Start mirroring the link to Google Drive

/{BotCommands.TarMirrorCommand} [download_url][magnet_link]: Start mirroring and upload the archived (.tar) version of the download

/{BotCommands.UnzipMirrorCommand} [download_url][magnet_link]: Starts mirroring and if downloaded file is any archive, extracts it to Google Drive

/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive

/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive Links

/{BotCommands.WatchCommand} [youtube-dl supported link]: Mirror through youtube-dl. Click /{BotCommands.WatchCommand} for more help

/{BotCommands.TarWatchCommand} [youtube-dl supported link]: Mirror through youtube-dl and tar before uploading

/{BotCommands.CancelMirror}: Reply to the message by which the download was initiated and that download will be cancelled

/{BotCommands.ListCommand} [search term]: Searches the search term in the Google Drive, If found replies with the link

/{BotCommands.StatusCommand}: Shows a status of all the downloads

/{BotCommands.StatsCommand}: Show Stats of the machine the bot is hosted on

/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot

/{BotCommands.SpeedCommand}: Check Internet Speed of the Host

/{BotCommands.MediaInfoCommand}: Get detailed info about replied media (Only for Telegram file)

/{BotCommands.TsHelpCommand}: Get help for Torrent search module
'''

    if CustomFilters.sudo_user(update) or CustomFilters.owner_filter(update):
        sendMessage(help_string_adm, context.bot, update)
    else:
        sendMessage(help_string, context.bot, update)


botcmds = [
        (f'{BotCommands.HelpCommand}','Get Detailed Help'),
        (f'{BotCommands.MirrorCommand}', 'Start Mirroring'),
        (f'{BotCommands.TarMirrorCommand}','Start mirroring and upload as .tar'),
        (f'{BotCommands.UnzipMirrorCommand}','Extract files'),
        (f'{BotCommands.CloneCommand}','Copy file/folder to Drive'),
        (f'{BotCommands.CountCommand}','Count file/folder of Drive link'),
        (f'{BotCommands.DeleteCommand}','Delete file from Drive'),
        (f'{BotCommands.WatchCommand}','Mirror Youtube-dl support link'),
        (f'{BotCommands.TarWatchCommand}','Mirror Youtube playlist link as .tar'),
        (f'{BotCommands.CancelMirror}','Cancel a task'),
        (f'{BotCommands.CancelAllCommand}','Cancel all tasks'),
        (f'{BotCommands.ListCommand}','Searches files in Drive'),
        (f'{BotCommands.StatusCommand}','Get Mirror Status message'),
        (f'{BotCommands.StatsCommand}','Bot Usage Stats'),
        (f'{BotCommands.PingCommand}','Ping the Bot'),
        (f'{BotCommands.RestartCommand}','Restart the bot [owner/sudo only]'),
        (f'{BotCommands.LogCommand}','Get the Bot Log [owner/sudo only]'),
        (f'{BotCommands.MediaInfoCommand}','Get detailed info about replied media'),
        (f'{BotCommands.TsHelpCommand}','Get help for Torrent search module')
    ]


def main():
    fs_utils.start_cleanup()
    # Check if the bot is restarting
    if os.path.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        bot.edit_message_text("Restarted Successfully!", chat_id, msg_id)
        os.remove(".restartmsg")
       # bot.set_my_commands(botcmds)
    if LOG_GROUP is not None and isinstance(LOG_GROUP, str):

        try:
            now=datetime.now(pytz.timezone('Asia/Kolkata'))
            current = now.strftime('%Y/%m/%d %I:%M:%P')
            dispatcher.bot.sendMessage(f"{LOG_GROUP}", f"Bot {BOT_NO} Successfully Restarted\n\nTime : {current}")
        except Unauthorized:
            LOGGER.warning(
                "Bot isnt able to send message to support_chat, go and check!"
            )
        except BadRequest as e:
            LOGGER.warning(e.message)

    start_handler = CommandHandler(BotCommands.StartCommand, start, run_async=True)
    ping_handler = CommandHandler(BotCommands.PingCommand, ping,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    restart_handler = CommandHandler(BotCommands.RestartCommand, restart,
                                     filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    help_handler = CommandHandler(BotCommands.HelpCommand,
                                  bot_help, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    stats_handler = CommandHandler(BotCommands.StatsCommand,
                                   stats, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    del_data_msg = CallbackQueryHandler(call_back_data, pattern="stats_close")
    
    dispatcher.add_handler(del_data_msg)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(restart_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    updater.start_polling(drop_pending_updates=IGNORE_PENDING_REQUESTS)
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)

app.start()
main()
idle()
