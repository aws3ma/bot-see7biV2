import yt_dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(title)s.mp3',
    'ignoreerrors': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'logtostderr': False,
    'quiet': False,
    'no_warnings': True,
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
url = input("Youtube Video/Playlist link : ")
ytdl.extract_info(url, download=True)

