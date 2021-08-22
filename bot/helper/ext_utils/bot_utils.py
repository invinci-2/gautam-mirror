import logging
import re
import threading
import time

from bot.helper.telegram_helper.bot_commands import BotCommands
from bot import download_dict, download_dict_lock

LOGGER = logging.getLogger(__name__)

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

FINISHED_PROGRESS_STR = "▓"
UNFINISHED_PROGRESS_STR = "░"

class MirrorStatus:
    STATUS_UPLOADING = "Uploading"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_CLONING = "Cloning"
    STATUS_WAITING = "Queued"
    STATUS_FAILED = "Failed. Cancelling Download..."
    STATUS_ARCHIVING = "Archiving"
    STATUS_EXTRACTING = "Extracting"


PROGRESS_MAX_SIZE = 100 // 8
# PROGRESS_INCOMPLETE = ['▓', '▓', '▓', '▓', '▓', '▓', '▓']

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time() + self.interval
        while not self.stopEvent.wait(nextTime - time.time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()


def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'


def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in download_dict.values():
            status = dl.status()
            if status != MirrorStatus.STATUS_ARCHIVING and status != MirrorStatus.STATUS_EXTRACTING:
                if dl.gid() == gid:
                    return dl
    return None

def getAllDownload():
    with download_dict_lock:
        for dlDetails in list(download_dict.values()):
            if dlDetails.status() == MirrorStatus.STATUS_DOWNLOADING or dlDetails.status() == MirrorStatus.STATUS_WAITING:
                if dlDetails:
                    return dlDetails
    return None

def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    if total == 0:
        p = 0
    else:
        p = round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    cPart = p % 8 - 1
    p_str = FINISHED_PROGRESS_STR * cFull
    if cPart >= 0:
        # p_str += PROGRESS_INCOMPLETE[cPart]
        p_str += FINISHED_PROGRESS_STR
    p_str += UNFINISHED_PROGRESS_STR * (PROGRESS_MAX_SIZE - cFull)
    p_str = f"[{p_str}]"
    return p_str


def progress_bar(percentage):
    """Returns a progress bar for download
    """
    #percentage is on the scale of 0-1
    comp = FINISHED_PROGRESS_STR
    ncomp = UNFINISHED_PROGRESS_STR
    pr = ""

    if isinstance(percentage, str):
        return "NaN"

    try:
        percentage=int(percentage)
    except:
        percentage = 0

    for i in range(1,11):
        if i <= int(percentage/10):
            pr += comp
        else:
            pr += ncomp
    return pr



def get_readable_message():
    with download_dict_lock:
        num_active = 0
        num_waiting = 0
        num_upload = 0
        for stats in list(download_dict.values()):
            if stats.status() == MirrorStatus.STATUS_DOWNLOADING:
               num_active += 1
            if stats.status() == MirrorStatus.STATUS_WAITING:
               num_waiting += 1
            if stats.status() == MirrorStatus.STATUS_UPLOADING:
               num_upload += 1
        msg = f"<b>DL: {num_active} || UL: {num_upload} || QUEUED: {num_waiting}</b>\n\n"
        for download in list(download_dict.values()):
            msg += f"<b>════════════════════════════════</b>\n\n"
            msg += f"<b>➜ {download.status()} :</b> <code>{download.name()}</code>"
            if download.status() != MirrorStatus.STATUS_ARCHIVING and download.status() != MirrorStatus.STATUS_EXTRACTING:
                msg += f"\n<b>➜ Progress :</b> <code>{get_progress_bar_string(download)}</code> <b>{download.progress()}</b>"
                if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                    msg += f"\n<b>➜ Downloaded :</b> <b>{get_readable_file_size(download.processed_bytes())}</b> <b>Of</b> <b>{download.size()}</b>" 
                elif download.status() == MirrorStatus.STATUS_CLONING:
                        msg += f"\n<b>➜ Cloned:</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                else:
                    msg += f"\n<b>➜ Uploaded :</b> <b>{get_readable_file_size(download.processed_bytes())}</b> <b>Of</b> <b>{download.size()}</b>"
                msg += f"\n<b>➜ Speed :</b> {download.speed()} || <b>➜ ETA:</b> {download.eta()} "
                # if hasattr(download, 'is_torrent'):
                try:
                    msg += f"\n<b>➜ Peers :</b> {download.aria_download().connections} " \
                           f"|| <b>➜ Seeds :</b> {download.aria_download().num_seeders}"
                except:
                    pass
                msg += f"\n<b>➜ To Stop :</b> <code>/{BotCommands.CancelMirror} {download.gid()}</code>"
            msg += "\n\n"
        return msg


def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result


def is_url(url: str):
    url = re.findall(URL_REGEX, url)
    if url:
        return True
    return False

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_mega_link(url: str):
    return "mega.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re.findall(MAGNET_REGEX, url)
    if magnet:
        return True
    return False

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper
