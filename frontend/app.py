from flask import Flask, render_template, request
import yt_dlp

app = Flask(__name__)

def get_audio_url(youtube_url):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info['url']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/play', methods=['POST'])
def play_stream():
    youtube_url = request.form.get('url')
    direct_stream_url = get_audio_url(youtube_url)
    
    return f'''
    <audio controls autoplay style="width: 100%;">
        <source src="{direct_stream_url}" type="audio/mp4">
        Your browser does not support the audio element.
    </audio>
    '''

if __name__ == '__main__':
    app.run(debug=True)
