import requests
from telegram.ext import CommandHandler
from telegram.message import Message
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot import Interval, INDEX_URL, BUTTON_FOUR_NAME, BUTTON_FOUR_URL, BUTTON_FIVE_NAME, BUTTON_FIVE_URL, BUTTON_SIX_NAME, BUTTON_SIX_URL, BLOCK_MEGA_FOLDER, BLOCK_MEGA_LINKS, VIEW_LINK
from bot import dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_dict, download_dict_lock, SHORTENER, SHORTENER_API, TAR_UNZIP_LIMIT, aria2
from bot.helper.ext_utils import fs_utils, bot_utils
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException, NotSupportedExtractionArchive
from bot.helper.mirror_utils.download_utils.aria2_download import AriaDownloadHelper
from bot.helper.mirror_utils.download_utils.mega_downloader import MegaDownloadHelper
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.mirror_utils.status_utils import listeners
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.tar_status import TarStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.gdownload_status import DownloadStatus
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper import button_build
import urllib
import pathlib
import os
import subprocess
import threading
import re
import random
import string
import time

ariaDlManager = AriaDownloadHelper()
ariaDlManager.start_listener()

class MirrorListener(listeners.MirrorListeners):
    def __init__(self, bot, update, pswd, isTar=False, tag=None, extract=False):
        super().__init__(bot, update)
        self.isTar = isTar
        self.tag = tag
        self.extract = extract
        self.pswd = pswd

    def onDownloadStarted(self):
        pass

    def onDownloadProgress(self):
        # We are handling this on our own!
        pass

    def clean(self):
        try:
            aria2.purge()
            Interval[0].cancel()
            del Interval[0]
            delete_all_messages()
        except IndexError:
            pass

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = download.name()
            gid = download.gid()
            size = download.size_raw()
            if name is None: # when pyrogram's media.file_name is of NoneType
                name = os.listdir(f'{DOWNLOAD_DIR}{self.uid}')[0]
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        if self.isTar:
            download.is_archiving = True
            try:
                with download_dict_lock:
                    download_dict[self.uid] = TarStatus(name, m_path, size)
                path = fs_utils.tar(m_path)
            except FileNotFoundError:
                LOGGER.info('File to archive not found!')
                self.onUploadError('Internal error occurred!!')
                return
        elif self.extract:
            download.is_extracting = True
            try:
                path = fs_utils.get_base_name(m_path)
                LOGGER.info(
                    f"Extracting : {name} "
                )
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, m_path, size)
                pswd = self.pswd
                if pswd is not None:
                    archive_result = subprocess.run(["pextract", m_path, pswd])
                else:
                    archive_result = subprocess.run(["extract", m_path])
                if archive_result.returncode == 0:
                    threading.Thread(target=os.remove, args=(m_path,)).start()
                    LOGGER.info(f"Deleting archive : {m_path}")
                else:
                    LOGGER.warning('Unable to extract archive! Uploading anyway')
                    path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
                LOGGER.info(
                    f'got path : {path}'
                )

            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        up_name = pathlib.PurePath(path).name
        up_path = f'{DOWNLOAD_DIR}{self.uid}/{up_name}'
        if up_name == "None":
            up_name = "".join(os.listdir(f'{DOWNLOAD_DIR}{self.uid}/'))
        LOGGER.info(f"Upload Name : {up_name}")
        drive = gdriveTools.GoogleDriveHelper(up_name, self)
        size = fs_utils.get_path_size(up_path)
        upload_status = UploadStatus(drive, size, gid, self)
        with download_dict_lock:
            download_dict[self.uid] = upload_status
        update_all_messages()
        drive.upload(up_name)

    def onDownloadError(self, error):
        error = error.replace('<', ' ')
        error = error.replace('>', ' ')
        with download_dict_lock:
            try:
                download = download_dict[self.uid]
                del download_dict[self.uid]
                fs_utils.clean_download(download.path())
            except Exception as e:
                LOGGER.error(str(e))
                pass
            count = len(download_dict)
            fn = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        msg = f"<b>User : {fn} </b>\n<b>Status : Download Stopped</b>\nReason : <i>{error}</i>"
        sendMessage(msg, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadStarted(self):
        pass

    def onUploadProgress(self):
        pass

    def onUploadComplete(self, link: str, size, files, folders, typ):
        with download_dict_lock:
            msg = f'<b>• Filename : </b><i><code>{download_dict[self.uid].name()}</code></i>\n\n<b>• Size : </b><code>{size}</code>'
            if os.path.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{download_dict[self.uid].name()}'):
                msg += f'\n<i> - Type: Folder</i>'
                msg += f'\n<i> - Subfolder(s): {folders}</i>'
                msg += f'\n<i> - Files: {files}</i>'
            else:
                msg += f'\n<i> - Type: {typ}</i>'
            buttons = button_build.ButtonMaker()
            if SHORTENER is not None and SHORTENER_API is not None:
                surl = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={link}&format=text').text
                buttons.buildbutton("DRIVE LINK", surl)
            else:
                buttons.buildbutton("DRIVE LINK", link)
            LOGGER.info(f'Done Uploading {download_dict[self.uid].name()}')
            if INDEX_URL is not None:
                url_path = requests.utils.quote(f'{download_dict[self.uid].name()}')
                share_url = f'{INDEX_URL}/{url_path}'
                if os.path.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{download_dict[self.uid].name()}'):
                    share_url += '/'
                    if SHORTENER is not None and SHORTENER_API is not None:
                        siurl = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={share_url}&format=text').text
                        buttons.buildbutton("INDEX LINK", siurl)
                    else:
                        buttons.buildbutton("INDEX LINK", share_url)
                else:
                    share_urls = f'{INDEX_URL}/{url_path}?a=view'
                    if SHORTENER is not None and SHORTENER_API is not None:
                        siurl = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={share_url}&format=text').text
                        siurls = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={share_urls}&format=text').text
                        buttons.buildbutton("INDEX LINK", siurl)
                        if VIEW_LINK:
                            buttons.buildbutton("VIEW LINK", siurls)
                    else:
                        buttons.buildbutton("INDEX LINK", share_url)
                        if VIEW_LINK:
                            buttons.buildbutton("VIEW LINK", share_urls)
            if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
            if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")
            if BUTTON_SIX_NAME is not None and BUTTON_SIX_URL is not None:
                buttons.buildbutton(f"{BUTTON_SIX_NAME}", f"{BUTTON_SIX_URL}")
            if self.message.from_user.username:
                uname = f"@{self.message.from_user.username}"
            else:
                uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
            if uname is not None:
                msg += f'\n\n<b>#Uploaded By {uname}</b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
                msg_g = f'\n\n - <b><i>Never Share G-Drive/Index Link.</i></b>\n - <b><i>Join TD To Access G-Drive Link.</i></b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.uid]
            count = len(download_dict)
        fwdpm = f'\n\n<b>You Can Find Upload In Private Chat</b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
        logmsg = sendLog(msg + msg_g, self.bot, self.update, InlineKeyboardMarkup(buttons.build_menu(2)))
        if logmsg:
            log_m = f"\n\n<b>Link Uploaded, Click Below Button</b>"
        else:
            pass
        sendMarkup(msg + log_m + fwdpm, self.bot, self.update, InlineKeyboardMarkup([[InlineKeyboardButton(text="CLICK HERE", url=logmsg.link)]]))
        sendPrivate(msg + msg_g, self.bot, self.update, InlineKeyboardMarkup(buttons.build_menu(2)))
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadError(self, error):
        e_str = error.replace('<', '').replace('>', '')
        with download_dict_lock:
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.message.message_id]
            count = len(download_dict)
        if self.message.from_user.username:
            uname = f"@{self.message.from_user.username}"
        else:
            uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        if uname is not None:
            men = f'{uname} '
        sendMessage(men + e_str, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

def _mirror(bot, update, isTar=False, extract=False):
    mesg = update.message.text.split('\n')
    message_args = mesg[0].split(' ')
    name_args = mesg[0].split('|')
    user_id = update.effective_user.id
    bot_d = bot.get_me()
    b_uname = bot_d.username
    uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
    uid= f"<a>{update.message.from_user.id}</a>"
    
    try:
        link = message_args[1]
        print(link)
        if link.startswith("|") or link.startswith("pswd: "):
            link = ''
    except IndexError:
        link = ''
    try:
        name = name_args[1]
        name = name.strip()
        if name.startswith("pswd: "):
            name = ''
    except IndexError:
        name = ''
    try:
        ussr = urllib.parse.quote(mesg[1], safe='')
        pssw = urllib.parse.quote(mesg[2], safe='')
    except:
        ussr = ''
        pssw = ''
    if ussr != '' and pssw != '':
        link = link.split("://", maxsplit=1)
        link = f'{link[0]}://{ussr}:{pssw}@{link[1]}'
    pswd = re.search('(?<=pswd: )(.*)', update.message.text)
    if pswd is not None:
      pswd = pswd.groups()
      pswd = " ".join(pswd)
    LOGGER.info(link)
    link = link.strip()
    reply_to = update.message.reply_to_message
    if reply_to is not None:
        file = None
        tag = reply_to.from_user.username
        media_array = [reply_to.document, reply_to.video, reply_to.audio]
        for i in media_array:
            if i is not None:
                file = i
                break

        if not bot_utils.is_url(link) and not bot_utils.is_magnet(link) or len(link) == 0:
            if file is not None:
                if file.mime_type != "application/x-bittorrent":
                    listener = MirrorListener(bot, update, pswd, isTar, tag, extract)
                    tgs = sendMessage(f"<b>Processing Your File.....</b>", bot, update)
                    time.sleep(1)
                    tg_downloader = TelegramDownloadHelper(listener)
                    ms = update.message
                    tg_downloader.add_download(ms, f'{DOWNLOAD_DIR}{listener.uid}/', name)
                    editMessage(f"<b>{uname} has sent - </b>\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n<b>Filename:</b> <code>{download_dict[listener.uid].name()}</code>\n\n<b>Type:</b> <code>{file.mime_type}</code>\n<b>Size:</b> {download_dict[listener.uid].size()}\n\nUser ID : {uid} \n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", tgs)
                    time.sleep(1)
                    sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested Telegram File Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
                    if len(Interval) == 0:
                        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
                    return
                else:
                    link = file.get_file().file_path

    else:
        tag = None
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        if isTar:
            sendMessage(f"<b><i>No download source provided</i></b>\n\n<b>If you don't know how to use bots check others message</b>\n\n<b>Example :- /{BotCommands.TarMirrorCommand} <i>(Your Torrent Magnet, GDrive Link, DDL Or Mega.nz Links)</i></b>\n<b><i>For Torrent And Telegram Files , Reply to the File with</i></b> /{BotCommands.TarMirrorCommand}", bot, update)
        elif extract:
            sendMessage(f"<b><i>No download source provided</i></b>\n\n<b>If you don't know how to use bots check others message</b>\n\n<b>Example :- /{BotCommands.UnzipMirrorCommand} <i>(Your Torrent Magnet, GDrive Link, DDL Or Mega.nz Links)</i></b>\n<b><i>For Torrent And Telegram Files , Reply to the File with</i></b> /{BotCommands.UnzipMirrorCommand}", bot, update)
        else:
            sendMessage(f"<b><i>No download source provided</i></b>\n\n<b>If you don't know how to use bots check others message</b>\n\n<b>Example :- /{BotCommands.MirrorCommand} <i>(Your Torrent Magnet, DDL Or Mega.nz Links)</i></b>\n<b><i>For Torrent And Telegram Files , Reply to the File with</i></b> /{BotCommands.MirrorCommand}", bot, update)
        return
    

    try:
        link = direct_link_generator(link)
    except DirectDownloadLinkException as e:
        LOGGER.info(f'{link}: {e}')
        if "ERROR:" in str(e):
            sendMessage(f"{e}", bot, update)
            return
        if "YTDL" in str(e):
            sendMessage(f"{e}", bot, update)
            return
        if "Index" in str(e):
            sendMessage(f"{e}", bot, update)
            return
        if "Yet" in str(e):
            sendMessage(f"{e}", bot, update)
            return
        if "Uptobox" in str(e):
            sendMessage(f"{e}", bot, update)
            return

    listener = MirrorListener(bot, update, pswd, isTar, tag, extract)  

    if bot_utils.is_gdrive_link(link):
        if not isTar and not extract:
            sendMessage(f"Use /clone To Copy File/Folder", bot, update)
            return
        res, size, name, files = gdriveTools.GoogleDriveHelper().clonehelper(link)
        if res != "":
            sendMessage(res, bot, update)
            return
        if TAR_UNZIP_LIMIT is not None:
            LOGGER.info(f'Checking File/Folder Size')
            limit = TAR_UNZIP_LIMIT
            limit = limit.split(' ', maxsplit=1)
            limitint = int(limit[0])
            msg = f'Failed, Tar/Unzip limit is {TAR_UNZIP_LIMIT}.\nYour File/Folder size is {get_readable_file_size(size)}.'
            if 'G' in limit[1] or 'g' in limit[1]:
                if size > limitint * 1024**3:
                    sendMessage(msg, listener.bot, listener.update)
                    return
            elif 'T' in limit[1] or 't' in limit[1]:
                if size > limitint * 1024**4:
                    sendMessage(msg, listener.bot, listener.update)
                    return
        LOGGER.info(f"Download Name : {name}")
        drive = gdriveTools.GoogleDriveHelper(name, listener)
        gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=12))
        download_status = DownloadStatus(drive, size, listener, gid)
        with download_dict_lock:
            download_dict[listener.uid] = download_status
        if len(Interval) == 0:
            Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
        gmgs = sendMessage("<b>Processing Your G-Drive Link...</b>", bot, update)
        time.sleep(2)
        editMessage(f"{uname} has sent - \n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n<code>{link}</code>\n\nUser ID : {uid}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", gmgs)
        time.sleep(1)
      # sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested G-Drive Folder Has Been Added To The Status For Archiving</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        if not isTar:
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested G-Drive File Has Been Added To The Status For Extracting</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        else:
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested G-Drive Folder Has Been Added To The Status For Archiving</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        drive.download(link)

    elif bot_utils.is_mega_link(link):
        link_type = get_mega_link_type(link)
        if link_type == "folder" and BLOCK_MEGA_FOLDER:
            sendMessage("Mega folder are blocked!", bot, update)
        elif BLOCK_MEGA_LINKS:
            sendMessage("<b>Mega Links Are Blocked🚫 in Mirror Bots</b>\n\n<b>Use Mega Bots For Downloading Mega Stuff</b>😇", bot, update)
        else:
            mgs = sendMessage("<b>Processing Your Mega.nz Link...</b>", bot, update)
            time.sleep(2)
            mega_dl = MegaDownloadHelper()
            mega_dl.add_download(link, f'{DOWNLOAD_DIR}/{listener.uid}/', listener)
            editMessage(f"{uname} has sent - \n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n<code>{link}</code>\n\nUser ID : {uid}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", mgs)
            time.sleep(1)
            if link_type == "folder":
                sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested MEGA Folder Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
            else:
                sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested MEGA File Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
    else:
        bot_start = f"http://t.me/{b_uname}?start=start"
        mssg = sendMessage("<b>Processing Your URI...</b>", bot, update)
        time.sleep(2)
        ariaDlManager.add_download(link, f'{DOWNLOAD_DIR}/{listener.uid}/', listener, name)
        if reply_to is not None:
            editMessage(f"{uname} has sent - \n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n<b>Filename:</b> <code>{file.file_name}</code>\n\n<b>Type:</b> <code>{file.mime_type}</code>\n<b>Size:</b> {get_readable_file_size(file.file_size)}\n\nUser ID : {uid}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", mssg)
            time.sleep(1)         
        else:
            editMessage(f"{uname} has sent - \n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n<code>{link}</code>\n\nUser ID : {uid}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", mssg)
            time.sleep(1)
        if reply_to is not None:
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested Torrent File Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        elif link.startswith("magnet"):
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested Magnet Link Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        elif link.endswith(".torrent"):
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested Torrent Link Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        elif '0:/' in link or '1:/' in link or '2:/' in link or '3:/' in link or '4:/' in link or '5:/' in link or '6:/' in link or "workers.dev" in link:
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested Index Link Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
        else:
            sendMessage(f"<b>Hei {uname}</b>\n\n<b>Your Requested DDL Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>\n", bot, update)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))



def mirror(update, context):
    _mirror(context.bot, update)



def tar_mirror(update, context):
    _mirror(context.bot, update, True)


def unzip_mirror(update, context):
    _mirror(context.bot, update, extract=True)


mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
tar_mirror_handler = CommandHandler(BotCommands.TarMirrorCommand, tar_mirror,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
unzip_mirror_handler = CommandHandler(BotCommands.UnzipMirrorCommand, unzip_mirror,
                                      filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
dispatcher.add_handler(unzip_mirror_handler)
