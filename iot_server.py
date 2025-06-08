from setting import SETTING
import secrets
import asyncio
from aiohttp_session import setup #pip install aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage #pip install cryptography
import json
from common import web, app  # socket_events.py에서 sio 인스턴스를 가져옵니다.
from request_handlers import mainHandle  # request_handlers.py에서 mainHandle 함수를 가져옵니다.
from socket_events import start_sensor_task

# 암호화 키 설정
SETTING['SECRET_KEY'] = secrets.token_bytes(32)

# 세션 미들웨어 설정
setup(app, EncryptedCookieStorage(SETTING['SECRET_KEY'], cookie_name=SETTING['COOKIE_NAME']))

async def web_server():
    app.router.add_static('/static/', path='static/', name='static') #리소스 위치    
    app.router.add_get('/', mainHandle) #http://172.16.237.107:5000
    #app.router.add_get('/login', loginHandle) #http://172.16.237.107:5000/login
    #추가 내용
    # app.router.add_get('/temperature', temperatureHandle) #http://172.16.237.107:5000/temperature

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000) # http://본인아이피:5000
    await site.start()
    
async def main():
    try:
        await web_server()  # 웹 서버 시작
        start_sensor_task(asyncio.get_event_loop())
        
        # 무한 루프로 서버가 계속 실행되도록 유지
        while True:
            await asyncio.sleep(3600)  # 예시로, 1시간마다 대기를 풀고 다시 대기함
    except KeyboardInterrupt:
        print("프로그램이 사용자에 의해 종료됨.")
    except Exception as e:
        print(f"예외 발생: {e}")
       
if __name__ == '__main__':
    asyncio.run(main())