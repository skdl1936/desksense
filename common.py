import psutil
import subprocess
import aiohttp
import genId
from aiohttp import web
from aiohttp_session import get_session
import socketio
from jinja2 import Environment, FileSystemLoader
from setting import SETTING
from datetime import datetime, timedelta, timezone

app = aiohttp.web.Application()
sio = socketio.AsyncServer(cors_allowed_origins='*')
sio.attach(app) #http와 socket.io 통합

async def session_check(request):
    session = await get_session(request)
    if 'authenticated' not in session:
        raise web.HTTPFound('/login')
    return session

def response_html(page, data=None):
    global SETTING
    try:
        rand = genId.generate_hash()
        template_loader = FileSystemLoader('html')
        template_env = Environment(loader=template_loader)
        template = template_env.get_template(page)
        if data:
            rendered_template = template.render(system_mode=SETTING['SYSTEM_MODE'], rand=rand, data=data)
        else:
            rendered_template = template.render(system_mode=SETTING['SYSTEM_MODE'], rand=rand)
        return web.Response(text=rendered_template, content_type='text/html')
    except Exception as e:
        # 오류 발생 시의 응답
        return aiohttp.web.Response(text=str(e), status=500)

# 집중도 계산식
#  ( 1- (움직임 횟수 * 15) / 총 학습시간 ) * 100 => 이런식으로 계산했음
def calculate_concentration(start_time, count):
    now = datetime.now(timezone(timedelta(hours=9)))
    total_seconds = (now - start_time).total_seconds()

    if total_seconds == 0:
        return 0.0
    
    distracted_seconds = count * 15
    concentration = max(0, 1 - (distracted_seconds / total_seconds))
    return round(concentration * 100, 2)

# 차트에 그릴 집중도
def calculate_interval_concentration(duration_seconds, count):
    if duration_seconds == 0:
        return 0.0

    distracted_seconds = count * 15
    concentration = max(0, 1 - (distracted_seconds / duration_seconds))
    return min(round(concentration * 100, 2), 100)
