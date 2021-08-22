from bot import BOT_NO

class _BotCommands:
    def __init__(self):
        self.StartCommand = f'start'
        self.PingCommand = 'ping'
        self.HelpCommand = f'help{BOT_NO}'
        self.LogCommand = f'log{BOT_NO}'

        self.MirrorCommand = f'mir{BOT_NO}'
        self.UnzipMirrorCommand = f'unzip{BOT_NO}'
        self.TarMirrorCommand = f'tar{BOT_NO}'

        self.CancelMirror = f'cancel{BOT_NO}'
        self.CancelAllCommand = f'call{BOT_NO}'

        self.ListCommand = f'list{BOT_NO}'
        self.SearchCommand = 'search'
        self.LookCommand = 'look'

        self.StatusCommand = 'status'
        self.StatsCommand = 'stats'

        self.AuthorizedUsersCommand = f'users{BOT_NO}'
        self.AuthorizeCommand = f'a{BOT_NO}'
        self.UnAuthorizeCommand = f'u{BOT_NO}'
        self.AddSudoCommand = f'addsudo{BOT_NO}'
        self.RmSudoCommand = f'rmsudo{BOT_NO}'

        
        self.RestartCommand = f're{BOT_NO}'
        self.RebootCommand = f'reboot{BOT_NO}'
        
        
        self.SpeedCommand = 'speedtest'

        self.CloneCommand = f'clone'
        self.CountCommand = f'count'

        self.WatchCommand = f'ytdl{BOT_NO}'
        self.TarWatchCommand = f'ytdltar{BOT_NO}'

        self.DeleteCommand = f'kill{BOT_NO}'

        self.UsageCommand = f'usage{BOT_NO}'

        self.MediaInfoCommand = f'mediainfo{BOT_NO}'

        self.ShellCommand = 'shell'
        self.ExecHelpCommand = 'exechelp'

        self.UpdateCommand = 'update'
        self.ConfigMenuCommand = 'config'
        
        self.TsHelpCommand = 'tshelp'
        

BotCommands = _BotCommands()
