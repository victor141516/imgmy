from datetime import datetime
from flask import Flask, request, jsonify, send_file, redirect
import os
import random
from redpie import Redpie
import rclone
import string
import threading
import time


app = Flask(__name__, static_url_path='/static')
REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = os.environ.get('REDIS_PORT')
REDIS_DB = os.environ.get('REDIS_DB')

IMAGES_PATH = os.environ.get('IMAGES_PATH', 'images')
MAX_SECONDS_BEFORE_DRIVE = int(os.environ.get('MAX_SECONDS_BEFORE_DRIVE', 3600))
RCLONE_DRIVE_NAME = os.environ.get('RCLONE_DRIVE_NAME', 'drive')
RCLONE_CONFIG_PATH = os.environ.get('RCLONE_CONFIG_PATH', '/rclone/rclone.conf')
if not os.path.isfile(RCLONE_CONFIG_PATH):
    RCLONE_CONFIG_PATH = None

DRIVE_IMAGES_PATH = os.environ.get('DRIVE_IMAGES_PATH', IMAGES_PATH)
if RCLONE_CONFIG_PATH:
    RCLONE_CONFIG = None
    with open(RCLONE_CONFIG_PATH) as f:
        RCLONE_CONFIG = f.read()
IMAGES_ACCESS_TIME = {}

if REDIS_HOST:
    redis_conf = {'host': REDIS_HOST}
    if REDIS_DB:
        redis_conf['db'] = REDIS_DB
    if REDIS_PORT:
        redis_conf['port'] = REDIS_PORT
    db = Redpie(**redis_conf)
else:
    db = {}


def move_to_drive_loop():
    while True:
        for img_name in db.keys():
            img_data = db[img_name]
            oldness = (datetime.now() - img_data['accessed_at']).seconds

            if img_data['location'] == 'cached':
                if oldness > MAX_SECONDS_BEFORE_DRIVE:
                    if os.path.isfile(f'{IMAGES_PATH}/{img_name}'):
                        os.remove(f'{IMAGES_PATH}/{img_name}')
                    db[img_name] = {'location': 'drive', 'accessed_at': img_data['accessed_at']}
            elif img_data['location'] == 'local':
                if not os.path.isfile(f'{IMAGES_PATH}/{img_name}'):
                    del(db[img_name])
                else:
                    if oldness > MAX_SECONDS_BEFORE_DRIVE:
                        res = rclone.with_config(RCLONE_CONFIG).run_cmd(command="copy", extra_args=[f'local:{IMAGES_PATH}/{img_name}', f'{RCLONE_DRIVE_NAME}:{DRIVE_IMAGES_PATH}'])
                        if res['code'] == 0:
                            db[img_name] = {'location': 'drive', 'accessed_at': img_data['accessed_at']}
                            os.remove(f'{IMAGES_PATH}/{img_name}')
        time.sleep(10)


def random_string(stringLength=5):
    letters = string.ascii_lowercase + string.ascii_uppercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def fetch_image_from_drive(img_name):
    if RCLONE_CONFIG is None:
        return False
    result = rclone.with_config(RCLONE_CONFIG).run_cmd(command="copy", extra_args=[f'{RCLONE_DRIVE_NAME}:{DRIVE_IMAGES_PATH}/{img_name}', f'local:{IMAGES_PATH}'])
    return result['code'] == 0


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/up', methods=["POST"])
def upload():
    file_name = random_string()
    with open(f'{IMAGES_PATH}/{file_name}', 'wb') as f:
        f.write(request.data)
    db[file_name] = {'location': 'local', 'accessed_at': datetime.now()}
    return jsonify({'code': file_name})


@app.route('/<img_name>')
def serve_image(img_name):
    try:
        location = db.get(img_name, {}).get('location')
        if location == 'local':
            db[img_name] = {'location': 'local', 'accessed_at': datetime.now()}
            return send_file(f'{IMAGES_PATH}/{img_name}', mimetype='image/jpg')
        elif location == 'cached':
            db[img_name] = {'location': 'cached', 'accessed_at': datetime.now()}
            return send_file(f'{IMAGES_PATH}/{img_name}', mimetype='image/jpg')
        elif location == 'drive':
            fetch_image_from_drive(img_name)
            db[img_name] = {'location': 'cached', 'accessed_at': datetime.now()}
            return send_file(f'{IMAGES_PATH}/{img_name}', mimetype='image/jpg')
        else:
            return redirect('/')
    except FileNotFoundError:
        return redirect('/')


if REDIS_HOST is not None and RCLONE_CONFIG_PATH is not None:
    threading.Thread(target=move_to_drive_loop).start()


if __name__ == "__main__":
    app.run('0.0.0.0', 8000, True)
