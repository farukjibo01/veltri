from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import datetime
import threading
import time
import cloudinary
import cloudinary.uploader
import os

app = Flask(__name__)
CORS(app)

# === CLOUDINARY CONFIG (YOUR CREDENTIALS) ===
cloudinary.config(
    cloud_name="YOUR_CLOUD_NAME",  # <-- REPLACE WITH YOURS
    api_key="YOUR_API_KEY",        # <-- REPLACE WITH YOURS
    api_secret="YOUR_API_SECRET"   # <-- REPLACE WITH YOURS
)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veltri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === DATABASE TABLES ===

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    snap = db.Column(db.Boolean, default=False)
    is_image = db.Column(db.Boolean, default=False)  # NEW

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='text')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_image = db.Column(db.Boolean, default=False)  # NEW

with app.app_context():
    db.create_all()

# === FUNCTIONS ===

def delete_snap_after_delay(message_id):
    time.sleep(10)
    with app.app_context():
        message = Message.query.get(message_id)
        if message and message.snap:
            db.session.delete(message)
            db.session.commit()
            print(f"Snap message {message_id} deleted!")

# === ROUTES ===

@app.route('/')
def home():
    return send_from_directory('.', 'login.html')

@app.route('/login-page')
def login_page():
    return send_from_directory('.', 'login.html')

@app.route('/chat')
def chat():
    return send_from_directory('.', 'index.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'error': 'Username already taken!'}), 400
    
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': f'Welcome to Veltri, {username}!'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid username or password!'}), 401
    
    return jsonify({'message': f'Welcome back, {username}!'}), 200

@app.route('/send-message', methods=['POST'])
def send_message():
    data = request.json
    username = data.get('username')
    content = data.get('content')
    snap = data.get('snap', False)
    is_image = data.get('is_image', False)
    
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    
    new_message = Message(username=username, content=content, snap=snap, is_image=is_image)
    db.session.add(new_message)
    db.session.commit()
    
    if snap:
        threading.Thread(target=delete_snap_after_delay, args=(new_message.id,)).start()
    
    return jsonify({'message': 'Message sent!', 'id': new_message.id}), 201

@app.route('/upload-image', methods=['POST'])
def upload_image():
    data = request.json
    username = data.get('username')
    image_data = data.get('image')
    snap = data.get('snap', False)
    
    if not username or not image_data:
        return jsonify({'error': 'Missing data'}), 400
    
    # Upload to Cloudinary
    try:
        upload_result = cloudinary.uploader.upload(image_data)
        image_url = upload_result['secure_url']
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    # Save as a message
    new_message = Message(username=username, content=image_url, snap=snap, is_image=True)
    db.session.add(new_message)
    db.session.commit()
    
    if snap:
        threading.Thread(target=delete_snap_after_delay, args=(new_message.id,)).start()
    
    return jsonify({'message': 'Image uploaded!', 'url': image_url}), 201

@app.route('/get-messages', methods=['GET'])
def get_messages():
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    result = []
    for m in messages:
        result.append({
            'username': m.username,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'snap': m.snap,
            'is_image': m.is_image
        })
    return jsonify(result)

@app.route('/post-story', methods=['POST'])
def post_story():
    data = request.json
    username = data.get('username')
    content = data.get('content')
    is_image = data.get('is_image', False)
    
    if not username or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    new_story = Story(username=username, content=content, is_image=is_image)
    db.session.add(new_story)
    db.session.commit()
    
    return jsonify({'message': 'Story posted!'}), 201

@app.route('/get-stories', methods=['GET'])
def get_stories():
    twenty_four_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    stories = Story.query.filter(Story.created_at >= twenty_four_hours_ago).order_by(Story.created_at.desc()).all()
    
    result = []
    for s in stories:
        result.append({
            'username': s.username,
            'content': s.content,
            'type': s.type,
            'time': s.created_at.strftime('%H:%M'),
            'is_image': s.is_image
        })
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
