
from flask import Flask, request, jsonify, send_file
from main import lunch
import os
import ffmpeg
import uuid
from pathlib import Path
from flask_cors import CORS



app = Flask(__name__)
CORS(app)


UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def convert_video_to_wav(input_file, output_file,output_path):

    try:
        os.makedirs(output_path, exist_ok=True)
        print(f"Folder '{output_path}' created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")


    try:
        # Extract audio and save it as a WAV file
        ffmpeg.input(input_file).output(output_file, format='wav').run()
        print(f"Successfully converted {input_file} to {output_file}")
    except ffmpeg.Error as e:
        print(f"An error occurred: {e}")
        print(e.stderr.decode('utf8'))


@app.route('/download_audio', methods=['POST'])
def transcribe_video():
    # youtube_url = request.form.get('youtube_url')
    # if not youtube_url:
    #     return jsonify({'error': 'Please provide a YouTube URL.'}), 400

    # return jsonify({'audio_file': str(youtube_url)}), 200
    print('Hello')




@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({"error": "No video file part"}), 400
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filename = file.filename
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        root, _ = os.path.splitext(filename)
        new_file_path = root + '.wav'

        random_name = str(uuid.uuid4())
        output_path = f'audio_files/{random_name}'
        output_path_item = f'audio_files/{random_name}/{new_file_path}'

        convert_video_to_wav(path, output_path_item,output_path)
        audio_file = next(Path(__file__).parent.glob(f'{output_path}/*.wav'))
        lunch(audio_file)
        return send_file(f"audio_files/{random_name}/"+ root + '.txt', as_attachment=True)
        return jsonify({"message": f"File {filename} uploaded successfully"}), 200
    

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)