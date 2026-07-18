from flask import Flask, jsonify, request, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import datetime
import threading
import time
import cloudinary
import cloudinary.uploader
import os
import base64
import json

app = Flask(__name__)
app.secret_key = 'veltri-secret-key-2026'
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*")

# Cloudinary config (REPLACE WITH YOUR CREDENTIALS)
cloudinary.config(
    cloud_name="YOUR_CLOUD_NAME",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET"
)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veltri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============================================
# DATABASE TABLES
# ============================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100), default="User")
    bio = db.Column(db.String(200), default="Hey! I'm using Veltri")
    profile_pic = db.Column(db.String(300), default="")
    online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_image = db.Column(db.Boolean, default=False)
    is_video = db.Column(db.Boolean, default=False)
    is_voice = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, video, voice, location

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, nullable=False)
    sender = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_image = db.Column(db.Boolean, default=False)
    is_video = db.Column(db.Boolean, default=False)
    is_voice = db.Column(db.Boolean, default=False)
    message_type = db.Column(db.String(20), default='text')

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='text')  # text, image, video
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    views = db.Column(db.Text, default='[]')

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    receiver = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1 = db.Column(db.String(80), nullable=False)
    user2 = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# ============================================
# SOCKET.IO EVENTS (Real-time)
# ============================================

@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    if username:
        join_room(username)
        user = User.query.filter_by(username=username).first()
        if user:
            user.online = True
            user.last_seen = datetime.datetime.utcnow()
            db.session.commit()

@socketio.on('send_message')
def handle_send_message(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    # Save to database
    message = Message(
        sender=sender,
        receiver=receiver,
        content=content,
        message_type=msg_type
    )
    db.session.add(message)
    db.session.commit()
    
    # Emit to receiver if online
    socketio.emit('new_message', {
        'sender': sender,
        'receiver': receiver,
        'content': content,
        'timestamp': message.timestamp.strftime('%H:%M'),
        'type': msg_type
    }, room=receiver)
    
    # Also emit to sender (to update their chat)
    socketio.emit('new_message', {
        'sender': sender,
        'receiver': receiver,
        'content': content,
        'timestamp': message.timestamp.strftime('%H:%M'),
        'type': msg_type
    }, room=sender)

@socketio.on('send_group_message')
def handle_send_group_message(data):
    group_id = data.get('group_id')
    sender = data.get('sender')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    # Save to database
    group_msg = GroupMessage(
        group_id=group_id,
        sender=sender,
        content=content,
        message_type=msg_type
    )
    db.session.add(group_msg)
    db.session.commit()
    
    # Get all members
    members = GroupMember.query.filter_by(group_id=group_id).all()
    for member in members:
        socketio.emit('new_group_message', {
            'group_id': group_id,
            'sender': sender,
            'content': content,
            'timestamp': group_msg.timestamp.strftime('%H:%M'),
            'type': msg_type
        }, room=member.username)

@socketio.on('disconnect')
def handle_disconnect():
    # We'll handle this with login tracking
    pass

# ============================================
# ROUTES
# ============================================

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
    name = data.get('name', username)
    
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'error': 'Username already taken!'}), 400
    
    new_user = User(username=username, password=password, name=name)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Account created!', 'username': username}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid credentials!'}), 401
    
    user.online = True
    user.last_seen = datetime.datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Welcome back!',
        'username': username,
        'name': user.name,
        'profile_pic': user.profile_pic
    }), 200

@app.route('/logout', methods=['POST'])
def logout():
    data = request.json
    username = data.get('username')
    user = User.query.filter_by(username=username).first()
    if user:
        user.online = False
        user.last_seen = datetime.datetime.utcnow()
        db.session.commit()
    return jsonify({'message': 'Logged out'})

@app.route('/get-user/<username>', methods=['GET'])
def get_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'username': user.username,
        'name': user.name,
        'bio': user.bio,
        'profile_pic': user.profile_pic,
        'online': user.online,
        'last_seen': user.last_seen.strftime('%H:%M') if user.last_seen else ''
    })

@app.route('/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    username = data.get('username')
    name = data.get('name')
    bio = data.get('bio')
    profile_pic = data.get('profile_pic')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if name:
        user.name = name
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
    result = [{'username': u.username, 'name': u.name, 'profile_pic': u.profile_pic} for u in users]
    return jsonify(result)

# ============================================
# FRIEND REQUESTS
# ============================================

@app.route('/send-friend-request', methods=['POST'])
def send_friend_request():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    
    if sender == receiver:
        return jsonify({'error': 'Cannot add yourself!'}), 400
    
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
        user = User.query.filter_by(username=f.user2).first()
        result.append({
            'username': f.user2,
            'name': user.name if user else f.user2,
            'profile_pic': user.profile_pic if user else '',
            'online': user.online if user else False
        })
    for f in friends2:
        user = User.query.filter_by(username=f.user1).first()
        result.append({
            'username': f.user1,
            'name': user.name if user else f.user1,
            'profile_pic': user.profile_pic if user else '',
            'online': user.online if user else False
        })
    return jsonify(result)

# ============================================
# MESSAGES
# ============================================

@app.route('/send-message', methods=['POST'])
def send_message():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    if not sender or not receiver or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    message = Message(
        sender=sender,
        receiver=receiver,
        content=content,
        message_type=msg_type
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({'message': 'Message sent!', 'id': message.id}), 201

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
            'id': m.id,
            'sender': m.sender,
            'receiver': m.receiver,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'message_type': m.message_type,
            'is_read': m.is_read
        })
    return jsonify(result)

@app.route('/mark-read', methods=['POST'])
def mark_read():
    data = request.json
    username = data.get('username')
    # Mark all messages as read
    messages = Message.query.filter_by(receiver=username, is_read=False).all()
    for m in messages:
        m.is_read = True
    db.session.commit()
    return jsonify({'message': 'Marked as read'})

# ============================================
# GROUPS
# ============================================

@app.route('/create-group', methods=['POST'])
def create_group():
    data = request.json
    name = data.get('name')
    creator = data.get('creator')
    members = data.get('members', [])
    
    if not name or not creator:
        return jsonify({'error': 'Missing data'}), 400
    
    group = Group(name=name, creator=creator)
    db.session.add(group)
    db.session.commit()
    
    # Add creator and members
    for member in [creator] + members:
        group_member = GroupMember(group_id=group.id, username=member)
        db.session.add(group_member)
    db.session.commit()
    
    return jsonify({'group_id': group.id, 'message': 'Group created!'}), 201

@app.route('/get-groups/<username>', methods=['GET'])
def get_groups(username):
    members = GroupMember.query.filter_by(username=username).all()
    group_ids = [m.group_id for m in members]
    groups = Group.query.filter(Group.id.in_(group_ids)).all()
    
    result = []
    for g in groups:
        member_count = GroupMember.query.filter_by(group_id=g.id).count()
        result.append({
            'id': g.id,
            'name': g.name,
            'creator': g.creator,
            'icon': g.icon,
            'member_count': member_count
        })
    return jsonify(result)

@app.route('/get-group-messages/<int:group_id>', methods=['GET'])
def get_group_messages(group_id):
    messages = GroupMessage.query.filter_by(group_id=group_id).order_by(GroupMessage.timestamp.asc()).all()
    result = []
    for m in messages:
        result.append({
            'id': m.id,
            'sender': m.sender,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'message_type': m.message_type
        })
    return jsonify(result)

@app.route('/send-group-message', methods=['POST'])
def send_group_message():
    data = request.json
    group_id = data.get('group_id')
    sender = data.get('sender')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    if not group_id or not sender or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    group_msg = GroupMessage(
        group_id=group_id,
        sender=sender,
        content=content,
        message_type=msg_type
    )
    db.session.add(group_msg)
    db.session.commit()
    
    return jsonify({'message': 'Message sent!', 'id': group_msg.id}), 201

@app.route('/add-group-member', methods=['POST'])
def add_group_member():
    data = request.json
    group_id = data.get('group_id')
    username = data.get('username')
    
    existing = GroupMember.query.filter_by(group_id=group_id, username=username).first()
    if existing:
        return jsonify({'error': 'Already in group!'}), 400
    
    member = GroupMember(group_id=group_id, username=username)
    db.session.add(member)
    db.session.commit()
    return jsonify({'message': 'Added to group!'})

# ============================================
# STORIES
# ============================================

@app.route('/post-story', methods=['POST'])
def post_story():
    data = request.json
    username = data.get('username')
    content = data.get('content')
    story_type = data.get('type', 'text')
    
    if not username or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    story = Story(username=username, content=content, type=story_type)
    db.session.add(story)
    db.session.commit()
    return jsonify({'message': 'Story posted!', 'id': story.id}), 201

@app.route('/get-stories/<username>', methods=['GET'])
def get_stories(username):
    twenty_four_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    stories = Story.query.filter(Story.created_at >= twenty_four_hours_ago).order_by(Story.created_at.desc()).all()
    
    result = []
    for s in stories:
        # Only show friends' stories
        is_friend = Friend.query.filter(
            ((Friend.user1 == s.username) & (Friend.user2 == username)) |
            ((Friend.user1 == username) & (Friend.user2 == s.username))
        ).first()
        
        if is_friend or s.username == username:
            views = json.loads(s.views) if s.views else []
            result.append({
                'id': s.id,
                'username': s.username,
                'content': s.content,
                'type': s.type,
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
    
    views = json.loads(story.views) if story.views else []
    if viewer not in views:
        views.append(viewer)
        story.views = json.dumps(views)
        db.session.commit()
    
    return jsonify({'message': 'Story viewed!'})

# ============================================
# MEDIA UPLOAD
# ============================================

@app.route('/upload-media', methods=['POST'])
def upload_media():
    data = request.json
    username = data.get('username')
    media_data = data.get('media')
    media_type = data.get('type', 'image')
    
    if not username or not media_data:
        return jsonify({'error': 'Missing data'}), 400
    
    try:
        upload_result = cloudinary.uploader.upload(media_data, resource_type='auto')
        media_url = upload_result['secure_url']
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'url': media_url}), 201

# ============================================
# CALL (WebRTC Signaling)
# ============================================

@socketio.on('call_user')
def handle_call_user(data):
    caller = data.get('caller')
    receiver = data.get('receiver')
    call_type = data.get('type', 'voice')  # voice or video
    
    socketio.emit('incoming_call', {
        'caller': caller,
        'type': call_type
    }, room=receiver)

@socketio.on('accept_call')
def handle_accept_call(data):
    caller = data.get('caller')
    receiver = data.get('receiver')
    
    socketio.emit('call_accepted', {
        'receiver': receiver
    }, room=caller)

@socketio.on('reject_call')
def handle_reject_call(data):
    caller = data.get('caller')
    socketio.emit('call_rejected', {}, room=caller)

@socketio.on('offer')
def handle_offer(data):
    socketio.emit('offer', data, room=data['receiver'])

@socketio.on('answer')
def handle_answer(data):
    socketio.emit('answer', data, room=data['caller'])

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    socketio.emit('ice_candidate', data, room=data['receiver'])

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
