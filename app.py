# -*- coding: utf-8 -*-
"""
문서 편집 위장 채팅 — Flask-SocketIO 실시간 서버
=====================================================
- 같은 '방 코드'에 들어온 사람끼리 실시간으로 메시지를 주고받음
- 방마다 대화 기록을 서버가 보관 → 새로고침/재접속해도 대화 유지
- 정적 파일(index.html) 서빙 + WebSocket 중계

실행(로컬):
    pip install -r requirements.txt
    python app.py
    → 브라우저에서 http://127.0.0.1:8003  (두 탭으로 같은 방 코드 입력해 테스트)
"""
import os, time
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins='*')

# 방별 상태: { room: {'history':[msg...], 'users':{sid:name}} }
rooms = {}
HISTORY_LIMIT = 300


def room_state(room):
    return rooms.setdefault(room, {'history': [], 'users': {}})


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@socketio.on('join')
def on_join(data):
    room = (data.get('room') or '').strip().upper()
    name = (data.get('name') or '익명').strip()[:20]
    if not room:
        return
    join_room(room)
    st = room_state(room)
    st['users'][request.sid] = name
    # 새로 들어온 사람에게 지금까지의 대화 기록 전송 (← 새로고침해도 유지)
    emit('history', st['history'])
    # 방 전체에 참가자 목록/입장 알림
    emit('presence', {'users': list(st['users'].values())}, room=room)
    emit('system', {'text': f'{name} 님이 들어왔습니다.'}, room=room)


@socketio.on('message')
def on_message(data):
    room = (data.get('room') or '').strip().upper()
    text = (data.get('text') or '').strip()[:2000]
    cid = data.get('cid', '')
    if not room or not text:
        return
    st = room_state(room)
    name = st['users'].get(request.sid, '익명')
    msg = {'cid': cid, 'name': name, 'text': text, 't': time.strftime('%H:%M')}
    st['history'].append(msg)
    st['history'] = st['history'][-HISTORY_LIMIT:]
    emit('message', msg, room=room)   # 보낸 사람 포함 전원에게 (본인 메시지는 cid로 구분)


@socketio.on('typing')
def on_typing(data):
    room = (data.get('room') or '').strip().upper()
    if not room:
        return
    name = room_state(room)['users'].get(request.sid, '')
    emit('typing', {'name': name}, room=room, include_self=False)


@socketio.on('disconnect')
def on_disconnect():
    for room, st in list(rooms.items()):
        if request.sid in st['users']:
            name = st['users'].pop(request.sid)
            emit('presence', {'users': list(st['users'].values())}, room=room)
            emit('system', {'text': f'{name} 님이 나갔습니다.'}, room=room)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8003))
    print(f'위장 채팅 서버 → http://127.0.0.1:{port}')
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
