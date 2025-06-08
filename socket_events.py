#socket_events.py
from common import sio, calculate_concentration
from sensor_reader import read_pir, read_distance
import asyncio
from datetime import datetime, timedelta, timezone

# clientId 기준으로 사용자별 시간 저장
user_sessions = {} 
KST = timezone(timedelta(hours=9))

@sio.event
async def connect(sid, environ, auth):
    print('클라이언트 연결', sid)
    client_id = auth.get('clientId')
    if not client_id:
        print('clientId 누락됨')
        return 

    user_sessions[client_id] = {
        'start_time': None, # 공부 시작 시간
        'pir_count': 0, #움직임 횟수
        'study_status': False, # 공부중인지
        'leave_count': 0, # 자리비움 횟수
        'leave_count_for_chart': 0,
        'is_away': False # 현재 자리에 없는 상태인지 여부 false: 자리에 있음
    }

@sio.event
async def disconnect(sid):
    print('클라이언트 종료', sid)

# 공부 시작 버튼 누름 감지
@sio.on('study_start')
async def study_start(sid, data):
    client_id = data.get('clientId')
    print(f'공부시작 client_id: {client_id}')

    # 공부 시작시 초기화 사항
    user_sessions[client_id]['start_time'] = datetime.now(KST)
    user_sessions[client_id]['study_status'] = True
    user_sessions[client_id]['pir_count'] = 0

    print(f"시간: {user_sessions[client_id]['start_time'].strftime('%Y-%m-%dT%H:%M:%S')}")
    await sio.emit('study_started',{
        "start_time": user_sessions[client_id]['start_time'].strftime('%Y-%m-%dT%H:%M:%S'),
        "study_status": user_sessions[client_id]['study_status']
    },to=sid)

# 공부가 끝났을 때
@sio.on('study_end')
async def study_end(sid,data):
    client_id = data.get('clientId')
    print(f'공부종료 SID: {client_id}')
    end_time = datetime.now(KST)

    if client_id in user_sessions and 'start_time' in user_sessions[client_id]:
        start_time = user_sessions[client_id]['start_time']
        duration = end_time - start_time

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        formatted_time = f'{hours:02}:{minutes:02}:{seconds:02}'
        print(f'총 학습 시간: {formatted_time}')

        # 집중도 계산
        count = user_sessions[client_id].get('pir_count', 0)
        concentration = calculate_concentration(start_time, count)
        print(f'집중도: {concentration}%')

        await sio.emit('study_result',{
            'total_time': formatted_time,
            'concentration': concentration,
            'leave_count': user_sessions[client_id]['leave_count']
        }, to=sid)

        # 유저 세션 초기화
        user_sessions[client_id]['pir_count'] = 0
        user_sessions[client_id]['start_time'] = None
        user_sessions[client_id]['study_status'] = False
        user_sessions[client_id]['leave_count'] = 0
        user_sessions[client_id]['is_away'] = False
    else:
        await sio.emit('study_result',{
            'total_time': '00:00:00',
            'concentration': 0 ,
            'leave_count': 0
        }, to=sid)

# 새로고침 시 데이터 다시 보냄
@sio.on('get_study_status')
async def handle_status_request(sid, data):
    client_id = data.get('clientId')
    if client_id in user_sessions:
        session = user_sessions[client_id]
        start_time = session['start_time']
        study_status = session.get('study_status', False)
        count = session.get('pir_count', 0)

        concentration = 0
        if study_status and start_time:
            concentration = calculate_concentration(start_time, count)

        if study_status:
            await sio.emit('study_started', {
                'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%S') if start_time else None,
                'study_status': study_status,
                'concentration': concentration
            }, to=sid)
            

cooldown = False

#  pir, 초음파센서 값을 가져와서 user_sessions에 저장
async def sensor_loop():
    global cooldown
    cooldown_time = 15

    while True:
        pir = read_pir()
        dist = read_distance()
        print(f'현재 거리: {dist}')
        # PIR센서 처리
        if pir == 1 and not cooldown:
            for client_id in user_sessions:
                user_sessions[client_id]['pir_count'] += 1
            cooldown = True

            asyncio.create_task(reset_cooldown(cooldown_time))
        
        # 초음파 센서 처리
        for client_id, session in user_sessions.items():
            if session.get('study_status', False):  # 공부 중일 때만 체크
                if 10 <= dist <= 400:  #쓰레기값 범위
                    if dist >= 100: #자리에 벗어날 때
                        if not session.get('is_away', False):
                            session['leave_count'] += 1
                            session['leave_count_for_chart'] += 1
                            session['is_away'] = True
                            print(f'{client_id} 자리를 비움. 총 이탈 횟수: {session["leave_count"]}')

                            # 자리비움 횟수 증가한것 전송
                            await sio.emit('leave_update', {
                                'clientId': client_id,
                                'leave_count': session['leave_count']
                            })
                            print('자리비움 증가로 소켓 요청 보냄')
                    else: #자리에 앉아있을때 
                        session['is_away'] = False
                else:
                    print(f"[초음파 무시됨] dist={dist} (센서 잡음)")
        await asyncio.sleep(1)

# 이벤트 루트에서 함수들을 비동기로 실행하기 위함
def start_sensor_task(loop):
    loop.create_task(sensor_loop())
    loop.create_task(concentration_loop()) 
    loop.create_task(concentration_chart_loop())
    loop.create_task(leave_chart_loop())


async def reset_cooldown(seconds):
    await asyncio.sleep(seconds)
    global cooldown
    cooldown = False

# 집중도 주기적 전송 루프 추가(작은 박스에 실시간 반영을 위함)
async def concentration_loop():
    while True:
        for client_id, session in user_sessions.items():
            start_time = session.get('start_time')
            if start_time:  # 공부 중인 경우만
                count = session.get('pir_count', 0)
                concentration = calculate_concentration(start_time, count)
                print(f'움직인 횟수:', count)
                await sio.emit('concentration_update', {
                    'clientId': client_id,
                    'concentration': concentration
                })

        await asyncio.sleep(10)  # 10초마다 업데이트

# 집중도 주기적으로 차트에 반영하기 위한 함수
async def concentration_chart_loop():
    chart_cycle = 10;
    while True:
        now = datetime.now(KST)
        for client_id, session in user_sessions.items():
            start_time = session.get('start_time')
            if start_time:
                count = session.get('pir_count',0)
                concentration = calculate_concentration(start_time, count)

                await sio.emit('concentration_chart_point',{
                    'clientId': client_id,
                    'concentration': concentration,
                    'timestamp': now.strftime('%H:%M')
                })

        await asyncio.sleep(chart_cycle) # 1분마다 차트 반영

# 자리이탈 횟수 주기적으로 차트에 반영하는 함수
async def leave_chart_loop():
    chart_cycle = 10;
    while True:
        now = datetime.now(KST)
        timestamp = now.strftime('%H:%M')

        for client_id, session in user_sessions.items():
            if session.get('study_status', False):
                delta = session.get('leave_count_for_chart', 0)

                await sio.emit('leave_chart_point', {
                    'clientId': client_id,
                    'timestamp': timestamp,
                    'leave_count': delta 
                })

                session['leave_count_for_chart'] = 0  
        await asyncio.sleep(chart_cycle)
