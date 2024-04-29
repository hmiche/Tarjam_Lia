
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/download_audio', methods=['POST'])
def download_audio():
    youtube_url = request.form.get('youtube_url')
    if not youtube_url:
        return jsonify({'error': 'Please provide a YouTube URL.'}), 400

    return jsonify({'audio_file': str(youtube_url)}), 200
    

if __name__ == '__main__':
    app.run(debug=True, port=5000)