import asyncio
import json
import random
import time
from textwrap import dedent
from typing import List, Union
import base64
import tls_client

from keyboard_tree_selector import select_tree
from welearn_tree import SelectedChapter, build_course_tree, resolve_selected_chapters

REQUEST_INTERVAL = 2
HEARTBEAT_INTERVAL = 1
AJAX_URL = "https://welearn.sflep.com/Ajax/SCO.aspx"

targetTime: Union['int', List['int']]

errors: List[str] = []
maxLearningTime: int = 0
session = tls_client.Session(client_identifier="chrome_120", debug=False)

# ---------以下修改---------------------
def to_hex_byte_array(byte_array):
    return ''.join([f'{byte:02x}' for byte in byte_array])


def generate_cipher_text(password):
    # 获取当前时间戳（毫秒级）
    T0 = int(round(time.time() * 1000)) # 不清楚原因，网站和本地间有延迟，需手动补齐延迟
    # 模拟TextEncoder.encode
    P = password.encode('utf-8')
    V = (T0 >> 16) & 0xFF
    for byte in P:
        V ^= byte
    remainder = V % 100
    T1 = int((T0 / 100) * 100 + remainder)
    P1 = to_hex_byte_array(P)
    S = f"{T1}*" + P1
    S_encoded = S.encode('utf-8')
    # 模拟btoa
    E = base64.b64encode(S_encoded).decode('utf-8')
    return [E, T1]


# 登录
def login(user, pwd):
    while True:
        try:
            response = session.get("https://welearn.sflep.com/user/prelogin.aspx?loginret=http://welearn.sflep.com/user/loginredirect.aspx")
            rurl = response.headers.get('Location')

            code_challenge = rurl.split("&")[4].split("=")[1]
            state = rurl.split("&")[6].split("=")[1]

            rturl = f"/connect/authorize/callback?client_id=welearn_web&redirect_uri=https%3A%2F%2Fwelearn.sflep.com%2Fsignin-sflep&response_type=code&scope=openid%20profile%20email%20phone%20address&code_challenge={code_challenge}&code_challenge_method=S256&state={state}&x-client-SKU=ID_NET472&x-client-ver=6.32.1.0"
            # 获取回调url
            print("登录中...", end='')
            while True:
                enpwd = generate_cipher_text(pwd)

                form_data = {
                    "rturl": rturl,
                    "account": user,
                    "pwd": str(enpwd[0]),
                    "ts": str(enpwd[1])
                }

                response = session.post("https://sso.sflep.com/idsvr/account/login", data=form_data)
                
                rt_json = response.json()
                code = rt_json.get("code", -1)

                if code == -1:
                    continue

                if code == 1:
                    print("\n帐号或密码错误！")
                    exit(0)

                next_url = f"https://sso.sflep.com/idsvr"+rt_json.get("data")

                while True:
                    resp = session.get(next_url)
                    if resp.status_code in (301, 302, 303, 307, 308):
                        next_url = resp.headers.get("Location", None)
                        if not next_url:
                            break
                        print(f"Redirecting to: {next_url} (status: {resp.status_code})")
                    else:
                        break

                if code == 0:
                    print("\n登录成功！")
                    return session
                
                print(".", end='')
        except Exception as e:
            print("错误返回,登录失败！")
            print(f"错误信息：{e}, 返回信息：{response.text}")
            exit(0)
# ---------以上修改---------------------


def input_time():
    global targetTime

    print("\n\n")
    print(dedent('''\
        模式1:每个练习增加指定学习时长，请直接输入时间
        如:希望每个练习增加30秒，则输入 30

        模式2:每个练习增加随机时长，请输入时间上下限并用英文逗号隔开
        如:希望每个练习增加10～30秒，则输入 10,30
    '''))
    print("\n\n")

    input_ = input("请严格按照以上格式输入: ")
    if(',' in input_):
        try:
            targetTime = [int(temp) for temp in input_.split(',')]
        except:
            print("格式异常")
            exit(0)
    else:
        targetTime = int(input_)


def generate_learning_time():
    """每一次模拟都重新生成一次随机学习时间"""
    global targetTime

    if type(targetTime) is int:
        learntime = targetTime
    else:
        learntime = random.randint(targetTime[0], targetTime[1])
    return learntime


def output_results():
    print('运行结束!!\n错误:', len(errors), '个')
    for index, error in enumerate(errors, start=1):
        print(f"第{index}个错误:{ error}")

    print("\n\n")
    print(dedent('''\
        **********  Created By Avenshy & SSmJaE  **********
                        Version : 0.3.0
           基于GPL3.0，完全开源，免费，禁止二次倒卖或商用
           https://www.github.com/Avenshy/WELearnToSleeep
                        仅供学习，勿滥用
        ***************************************************
    '''))
    print("\n\n")
    input("Press any key to exit...")


async def simulate(learningTime: int, selected: SelectedChapter):
    chapter = selected.chapter
    context = selected.context
    print(f"""章节 : {chapter['location']}""")
    print(f"""已学 : {chapter['learntime']} 将学 : {learningTime}""")

    commonHeaders = {
        'Referer': 'https://welearn.sflep.com/student/StudyCourse.aspx'
    }

    scoid = chapter['id']
    commonData = {
        'uid': context.uid,
        'cid': context.cid,
        'scoid': scoid
    }

    await asyncio.sleep(REQUEST_INTERVAL)
    response = session.post(
        AJAX_URL,
        data={
            **commonData,
            'action': 'getscoinfo_v7',
        },
        headers=commonHeaders
    )

    if('学习数据不正确' in response.text):  # 重试
        await asyncio.sleep(REQUEST_INTERVAL)

        response = session.post(
            AJAX_URL,
            data={
                **commonData,
                'action': 'startsco160928',
            },
            headers=commonHeaders
        )
        response = session.post(
            AJAX_URL,
            data={
                **commonData,
                'action': 'getscoinfo_v7',
            },
            headers=commonHeaders
        )

        if('学习数据不正确' in response.text):
            print('\n错误:', chapter['location'])
            errors.append(chapter['location'])
            return

    returnJson = response.json()['comment']
    if('cmi' in returnJson):
        cmi = json.loads(returnJson)['cmi']

        crate = cmi['score']['scaled']
        cstatus = cmi['completion_status']
        progress = cmi['progress_measure']
        total_time = cmi['total_time']
        session_time = cmi['session_time']
    else:
        crate = ''
        cstatus = 'not_attempted'
        progress = '0'
        total_time = '0'
        session_time = '0'

    await asyncio.sleep(REQUEST_INTERVAL)
    session.post(
        AJAX_URL,
        data={
            **commonData,
            'action': 'keepsco_with_getticket_with_updatecmitime',
            'session_time': session_time,
            'total_time': total_time
        },
        headers=commonHeaders
    )

    for currentTime in range(1, learningTime + 1):
        await asyncio.sleep(1)

        if(currentTime % 60 == 0):
            session.post(
                AJAX_URL,
                data={
                    **commonData,
                    'action': 'keepsco_with_getticket_with_updatecmitime',
                    'session_time': session_time,
                    'total_time': total_time},
                headers=commonHeaders
            )

    await asyncio.sleep(REQUEST_INTERVAL)
    session.post(
        AJAX_URL,
        data={
            **commonData,
            'action': 'savescoinfo160928',
            'crate': crate,
            'cstatus': cstatus,
            'status': 'unknown',
            'progress': progress,
            'trycount': '0'
        },
        headers=commonHeaders
    )


async def heartbeat():
    startTime = time.time()
    for _ in range(maxLearningTime+4*REQUEST_INTERVAL):
        print(
            f"""\r预计学习时长 : {maxLearningTime+4*REQUEST_INTERVAL} 已学习时长 : {int(time.time()-startTime)}""", end="")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def watcher():
    global maxLearningTime

    print("查询课程中...")
    course_tree = build_course_tree(session)
    selected_nodes = select_tree("选择要刷时长的课程/单元/小节", course_tree)
    selected_chapters = resolve_selected_chapters(session, selected_nodes)
    if not selected_chapters:
        print("未获取到可处理的小节。")
        return

    input_time()
    tasks = []
    for selected in selected_chapters:
        learningTime = generate_learning_time()

        if learningTime > maxLearningTime:
            maxLearningTime = learningTime

        tasks.append(asyncio.create_task(simulate(learningTime, selected)))

    await heartbeat()
    [await task for task in tasks]


async def main():
    await asyncio.gather(
        watcher()
    )

def welearn_time_run():
    user = input("请输入用户名=>")
    pwd = input("请输入密码=>")

    login(user, pwd)
    asyncio.run(main())
    output_results()
