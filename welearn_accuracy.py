import base64
from random import randint
import time
import tls_client

from keyboard_tree_selector import select_tree
from welearn_tree import build_course_tree, resolve_selected_chapters

session = tls_client.Session(client_identifier="chrome_120", debug=False)

def printline():
    print('-'*51)

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
                        # print(f"Redirecting to: {next_url} (status: {resp.status_code})")
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

def welearn_accuracy_run():
    user = input("请输入用户名=>")
    pwd = input("请输入密码=>")
    login(user, pwd)
    printline()
    print("查询课程中...")
    course_tree = build_course_tree(session)
    selected_nodes = select_tree("选择要刷正确率的课程/单元/小节", course_tree)
    selected_chapters = resolve_selected_chapters(session, selected_nodes)
    if not selected_chapters:
        print("未获取到可处理的小节。")
        return

    inputcrate = input(
        '模式1:每个练习指定正确率，请直接输入指定的正确率\n如:希望每个练习正确率均为100，则输入 100\n\n模式2:每个练习随机正确率，请输入正确率上下限并用英文逗号隔开\n如:希望每个练习正确率为70～100，则输入 70,100\n\n请严格按照以上格式输入每个练习的正确率: '
    )
    if ',' in inputcrate:
        mycrate = [int(item.strip()) for item in inputcrate.split(',', 1)]
        randommode = True
    else:
        mycrate = inputcrate.strip()
        randommode = False
    printline()

    way1Succeed, way2Succeed, way1Failed, way2Failed = 0, 0, 0, 0
    ajaxUrl = "https://welearn.sflep.com/Ajax/SCO.aspx"

    for selected in selected_chapters:
        context = selected.context
        course = selected.chapter
        cid = context.cid
        uid = context.uid
        classid = context.classid

        if course['isvisible'] == 'false':
            print(f'[!!跳过!!]    {course["location"]}')
            continue

        print(f'[强制重刷]    {course["location"]}')
        crate = str(randint(mycrate[0], mycrate[1])) if randommode else mycrate
        data = '{"cmi":{"completion_status":"completed","interactions":[],"launch_data":"","progress_measure":"1","score":{"scaled":"' + crate + '","raw":"100"},"session_time":"0","success_status":"unknown","total_time":"0","mode":"normal"},"adl":{"data":[]},"cci":{"data":[],"service":{"dictionary":{"headword":"","short_cuts":""},"new_words":[],"notes":[],"writing_marking":[],"record":{"files":[]},"play":{"offline_media_id":"9999"}},"retry_count":"0","submit_time":""}}[INTERACTIONINFO]'
        id = course["id"]
        session.post(
            ajaxUrl,
            data={"action": "startsco160928", "cid": cid, "scoid": id, "uid": uid},
            headers={"Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={id}"},
        )
        response = session.post(
            ajaxUrl,
            data={"action": "setscoinfo", "cid": cid, "scoid": id, "uid": uid, "data": data, "isend": "False"},
            headers={"Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={id}"},
        )
        print(f'>>>>>>>>>>>>>>正确率:{crate:>3}%', end='  ')
        if '"ret":0' in response.text:
            print("方式1:成功!!!", end="  ")
            way1Succeed += 1
        else:
            print("方式1:失败!!!", end="  ")
            way1Failed += 1

        response = session.post(
            ajaxUrl,
            data={
                "action": "savescoinfo160928",
                "cid": cid,
                "scoid": id,
                "uid": uid,
                "progress": "100",
                "crate": crate,
                "status": "unknown",
                "cstatus": "completed",
                "trycount": "0",
            },
            headers={"Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={id}"},
        )
        if '"ret":0' in response.text:
            print("方式2:成功!!!")
            way2Succeed += 1
        else:
            print("方式2:失败!!!")
            way2Failed += 1

    printline()
    print(f"""
    ***************************************************
    全部完成!!

    总计:
    方式1: {way1Succeed} 成功, {way1Failed} 失败
    方式2: {way2Succeed} 成功, {way2Failed} 失败

    https://github.com/Avenshy/WELearnToSleep
    本软件遵守GPLv3协议，且免费、开源，禁止售卖!
    本软件遵守GPLv3协议，且免费、开源，禁止售卖!
    本软件遵守GPLv3协议，且免费、开源，禁止售卖!
    **********  Created By Avenshy & SSmJaE  **********""")
    input("Press any key to exit...")
