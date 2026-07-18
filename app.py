from flask import Flask, jsonify, request, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import datetime
import threading
import time
import cloudinary
import cloudinary.uploader
import os
import base64

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app)

# Cloudinary (for images/videos)
cloudinary.config(
    cloud_name="YOUR_CLOUD_NAME",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET"
)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veltri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === DATABASE TABLES ===

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.String(200), default="Hey! I'm using Veltri")
    profile_pic = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    snap = db.Column(db.Boolean, default=False)
    is_image = db.Column(db.Boolean, default=False)
    is_video = db.Column(db.Boolean, default=False)
    is_voice = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='text')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_image = db.Column(db.Boolean, default=False)
    is_video = db.Column(db.Boolean, default=False)
    views = db.Column(db.Text, default='[]')  # JSON list of usernames who viewed

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1 = db.Column(db.String(80), nullable=False)
    user2 = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

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
    return jsonify({'message': 'Account created!'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid credentials!'}), 401
    return jsonify({'message': 'Welcome back!', 'username': username}), 200

@app.route('/get-user/<username>', methods=['GET'])
def get_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'username': user.username,
        'bio': user.bio,
        'profile_pic': user.profile_pic
    })

@app.route('/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    username = data.get('username')
    bio = data.get('bio')
    profile_pic = data.get('profile_pic')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if bio:
        user.bio = bio
    if profile_pic:
        user.profile_pic = profile_pic
    if password:
        user.password = password
    
    db.session.commit()
    return jsonify({'message': 'Profile updated!'})

@app.route('/search-users', methods=['POST'])
def search_users():
    data = request.json
    query = data.get('query', '')
    users = User.query.filter(User.username.contains(query)).all()
    result = [{'username': u.username} for u in users]
    return jsonify(result)

@app.route('/send-friend-request', methods=['POST'])
def send_friend_request():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    
    existing = FriendRequest.query.filter_by(sender=sender, receiver=receiver, status='pending').first()
    if existing:
        return jsonify({'error': 'Request already sent!'}), 400
    
    request_obj = FriendRequest(sender=sender, receiver=receiver)
    db.session.add(request_obj)
    db.session.commit()
    return jsonify({'message': 'Friend request sent!'})

@app.route('/get-friend-requests/<username>', methods=['GET'])
def get_friend_requests(username):
    requests = FriendRequest.query.filter_by(receiver=username, status='pending').all()
    result = [{'sender': r.sender} for r in requests]
    return jsonify(result)

@app.route('/accept-friend-request', methods=['POST'])
def accept_friend_request():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    
    request_obj = FriendRequest.query.filter_by(sender=sender, receiver=receiver).first()
    if request_obj:
        request_obj.status = 'accepted'
        db.session.commit()
        
        # Add to friends list
        friend = Friend(user1=sender, user2=receiver)
        db.session.add(friend)
        db.session.commit()
        return jsonify({'message': 'Friend request accepted!'})
    return jsonify({'error': 'Request not found'}), 404

@app.route('/reject-friend-request', methods=['POST'])
def reject_friend_request():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    
    request_obj = FriendRequest.query.filter_by(sender=sender, receiver=receiver).first()
    if request_obj:
        db.session.delete(request_obj)
        db.session.commit()
        return jsonify({'message': 'Friend request rejected!'})
    return jsonify({'error': 'Request not found'}), 404

@app.route('/get-friends/<username>', methods=['GET'])
def get_friends(username):
    friends1 = Friend.query.filter_by(user1=username).all()
    friends2 = Friend.query.filter_by(user2=username).all()
    
    result = []
    for f in friends1:
        result.append({'username': f.user2})
    for f in friends2:
        result.append({'username': f.user1})
    return jsonify(result)

@app.route('/send-message', methods=['POST'])
def send_message():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    content = data.get('content')
    snap = data.get('snap', False)
    is_image = data.get('is_image', False)
    is_video = data.get('is_video', False)
    is_voice = data.get('is_voice', False)
    
    if not sender or not receiver or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    new_message = Message(
        sender=sender,
        receiver=receiver,
        content=content,
        snap=snap,
        is_image=is_image,
        is_video=is_video,
        is_voice=is_voice
    )
    db.session.add(new_message)
    db.session.commit()
    
    if snap:
        threading.Thread(target=delete_snap_after_delay, args=(new_message.id,)).start()
    
    return jsonify({'message': 'Message sent!', 'id': new_message.id}), 201

@app.route('/get-messages', methods=['POST'])
def get_messages():
    data = request.json
    user1 = data.get('user1')
    user2 = data.get('user2')
    
    messages = Message.query.filter(
        ((Message.sender == user1) & (Message.receiver == user2)) |
        ((Message.sender == user2) & (Message.receiver == user1))
    ).order_by(Message.timestamp.asc()).all()
    
    result = []
    for m in messages:
        result.append({
            'sender': m.sender,
            'receiver': m.receiver,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'snap': m.snap,
            'is_image': m.is_image,
            'is_video': m.is_video,
            'is_voice': m.is_voice
        })
    return jsonify(result)

@app.route('/upload-media', methods=['POST'])
def upload_media():
    data = request.json
    username = data.get('username')
    media_data = data.get('media')
    snap = data.get('snap', False)
    media_type = data.get('type', 'image')  # image or video
    
    if not username or not media_data:
        return jsonify({'error': 'Missing data'}), 400
    
    try:
        upload_result = cloudinary.uploader.upload(media_data, resource_type='auto')
        media_url = upload_result['secure_url']
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'url': media_url}), 201

@app.route('/post-story', methods=['POST'])
def post_story():
    data = request.json
    username = data.get('username')
    content = data.get('content')
    is_image = data.get('is_image', False)
    is_video = data.get('is_video', False)
    
    if not username or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    new_story = Story(username=username, content=content, is_image=is_image, is_video=is_video)
    db.session.add(new_story)
    db.session.commit()
    return jsonify({'message': 'Story posted!'}), 201

@app.route('/get-stories', methods=['POST'])
def get_stories():
    data = request.json
    viewer = data.get('viewer')
    twenty_four_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    stories = Story.query.filter(Story.created_at >= twenty_four_hours_ago).order_by(Story.created_at.desc()).all()
    
    result = []
    for s in stories:
        # Check if viewer is friends with the story poster
        is_friend = Friend.query.filter(
            ((Friend.user1 == s.username) & (Friend.user2 == viewer)) |
            ((Friend.user1 == viewer) & (Friend.user2 == s.username))
        ).first()
        
        if is_friend or s.username == viewer:
            views = eval(s.views) if s.views else []
            result.append({
                'id': s.id,
                'username': s.username,
                'content': s.content,
                'is_image': s.is_image,
                'is_video': s.is_video,
                'time': s.created_at.strftime('%H:%M'),
                'views': views
            })
    return jsonify(result)

@app.route('/view-story', methods=['POST'])
def view_story():
    data = request.json
    story_id = data.get('story_id')
    viewer = data.get('viewer')
    
    story = Story.query.get(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    views = eval(story.views) if story.views else []
    if viewer not in views:
        views.append(viewer)
        story.views = str(views)
        db.session.commit()
    
    return jsonify({'message': 'Story viewed!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
