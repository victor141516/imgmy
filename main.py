from flask import Flask, request, jsonify, send_file
import os
import random
import string

app = Flask(__name__, static_url_path='/static')
IMAGES_PATH = os.environ.get('IMAGES_PATH', 'images')


def random_string(stringLength=5):
    letters = string.ascii_lowercase + string.ascii_uppercase
    return ''.join(random.choice(letters) for i in range(stringLength))


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/up', methods=["POST"])
def upload():
    file_name = random_string()
    with open(f'{IMAGES_PATH}/{file_name}', 'wb') as f:
        f.write(request.data)
    return jsonify({'code': file_name})


@app.route('/<img_name>')
def serve_image(img_name):
    return send_file(f'{IMAGES_PATH}/{img_name}', mimetype='image/jpg')


if __name__ == "__main__":
    app.run('0.0.0.0', 8000, True)
