import time
import requests
import re
import hashlib
import json
import uuid
from ebooklib import epub
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= 字典加载与环境配置 =================
charMap = {}
dict_file = "dict.json"

# 动态加载外部字典以解耦数据与代码
if os.path.exists(dict_file):
    try:
        with open(dict_file, "r", encoding="utf-8") as f:
            charMap = json.load(f)
        print(f"[*] 成功从 {dict_file} 加载字符替换映射表。")
    except Exception as e:
        print(f"[!] 读取 {dict_file} 解析失败，将跳过字符替换环节。错误: {e}")
else:
    print(f"[!] 未发现同级目录下的 {dict_file}，特殊字符将保留原样输出。")

device_token = "910D166A-736E-3231-8B21-8D12DFD75F16"
headers = {
    'Host': 'api.sfacg.com',
    'accept-charset': 'UTF-8',
    'authorization': 'Basic YW5kcm9pZHVzZXI6MWEjJDUxLXl0Njk7KkFjdkBxeHE=',
    'accept': 'application/vnd.sfacg.api+json;version=1',
    'user-agent': f'boluobao/5.1.54(android;35)/OPPO/{device_token.lower()}/OPPO',
    'accept-encoding': 'gzip',
    'Content-Type': 'application/json; charset=UTF-8'
}
SALT = "lPQDb9AKO7$LjkPG"

# ================= 签名与认证体系 =================
def get_sign(nonce, timestamp, device_token):
    long_nonce = (nonce * 4).encode("ascii")
    def index_calc(x):
        x0 = long_nonce[x]
        x17 = x0 // 0x24
        return x0 - x17 * 0x24

    offset1 = index_calc(1)
    offset2 = index_calc(2)
    offset3 = index_calc(3)
    offset4 = index_calc(4)

    nonce_reorder = (
        long_nonce[offset1:offset1 + 13] +
        long_nonce[offset2:offset2 + 16] +
        long_nonce[offset3:offset3 + 36] +
        long_nonce[offset4:offset4 + 36]
    )
    auth_string = (str(timestamp) + SALT + device_token + nonce).encode("ascii")

    result = ""
    for i in range(101):
        result += chr((auth_string[i] + nonce_reorder[i]) >> 1)

    lens = [13, 16, 36, 36]
    A = result[0:lens[0]]
    B = result[lens[0]:lens[0] + lens[1]]
    C = result[lens[0] + lens[1]:lens[0] + lens[1] + lens[2]]
    D = result[lens[0] + lens[1] + lens[2]:]

    string_after_reorder = D + A + C + B
    final = ""

    for i in range(101):
        char_code = ord(string_after_reorder[i])
        if char_code < 0x30:
            if 0x39 < char_code + 19 < 0x41:
                final += chr(0x39)
            else:
                final += chr(char_code + 19)
        elif 0x39 < char_code < 0x41:
            final += chr(char_code + 19)
        elif 0x5A < char_code < 0x61:
            final += chr(char_code + 19)
        else:
            final += string_after_reorder[i]

    return hashlib.md5(final.encode("utf-8")).hexdigest().upper()

# 初始化全局凭证变量 nonce
nonce = ""
resp_init = {"status":{"httpCode":417}}
while (resp_init['status']['httpCode']==417):
    nonce = str(uuid.uuid4()).upper()
    timestamp = int(time.time() * 1000)
    sign = get_sign(nonce, timestamp, device_token)
    headers['sfsecurity'] = f'nonce={nonce}&timestamp={timestamp}&devicetoken={device_token}&sign={sign}'
    url_init = f"https://api.sfacg.com/Chaps/8436696?expand=content%2Cexpand.content"
    try:
        resp_init = requests.get(url_init, headers=headers, timeout=10).json()
    except Exception:
        pass


def get_catalog(novel):
    chapters = {}
    title = ""
    author = ""
    cover = ""
    try:
        timestamp = int(time.time() * 1000)
        sign = get_sign(nonce, timestamp, device_token)
        headers['sfsecurity'] = f'nonce={nonce}&timestamp={timestamp}&devicetoken={device_token}&sign={sign}'
        resp = requests.get(f'https://api.sfacg.com/novels/{novel}?expand=bigNovelCover', headers=headers, timeout=10).json()
        title = resp['data']['novelName']
        author = resp['data']['authorName']
        cover = resp['data']['expand']['bigNovelCover']
    except Exception:
        print("标题获取失败")
        title = "标题获取失败"

    try:
        timestamp = int(time.time() * 1000)
        sign = get_sign(nonce, timestamp, device_token)
        headers['sfsecurity'] = f'nonce={nonce}&timestamp={timestamp}&devicetoken={device_token}&sign={sign}'
        catalog = requests.get(f'https://api.sfacg.com/novels/{novel}/dirs?expand=originNeedFireMoney', headers=headers, timeout=10).json()
        for volume in catalog['data']['volumeList']:
            chapters[volume['title']] = []
            for chapter in volume['chapterList']:
                chapters[volume['title']].append(chapter['chapId'])
    except Exception:
        print("目录获取失败")
        title = "目录获取失败"
    return title, author, cover, chapters


def get_cookie(username, password):
    timestamp = int(time.time() * 1000)
    sign = get_sign(nonce, timestamp, device_token)
    headers['sfsecurity'] = f'nonce={nonce}&timestamp={timestamp}&devicetoken={device_token}&sign={sign}'
    data = json.dumps({"password": password, "shuMeiId": "", "username": username})
    try:
        resp = requests.post("https://api.sfacg.com/sessions", headers=headers, data=data, timeout=10)
        if resp.json()["status"]["httpCode"] == 200:
            cookie = requests.utils.dict_from_cookiejar(resp.cookies)
            return f'.SFCommunity={cookie[".SFCommunity"]}; session_APP={cookie["session_APP"]}'
    except Exception:
        pass
    return "error"

def check(check_headers):
    try:
        resp = requests.get('https://api.sfacg.com/user?', headers=check_headers, timeout=5)
        data = resp.json()
        if data["status"]["httpCode"] == 200:
            return False
        return True
    except Exception:
        return True

# ================= 核心下载控制引擎 =================
def download_single_chapter(chapter_id, max_retries):
    """
    单章节并发下载器，内置重试策略与上下文隔离
    """
    local_headers = headers.copy() 
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            timestamp = int(time.time() * 1000)
            sign = get_sign(nonce, timestamp, device_token)
            local_headers['sfsecurity'] = f'nonce={nonce}&timestamp={timestamp}&devicetoken={device_token}&sign={sign}'
            url = f"https://api.sfacg.com/Chaps/{chapter_id}?expand=content%2Cexpand.content"
            
            resp = requests.get(url, headers=local_headers, timeout=10).json()
            
            if resp['status']['httpCode'] == 200:
                title = resp['data']['title']
                tmp = ""
                if 'content' in resp['data']:
                    tmp += resp['data']['content']
                    if 'expand' in resp['data'] and 'content' in resp['data']['expand']:
                        tmp += resp['data']['expand']['content']
                else:
                    tmp += resp['data']['expand']['content']
                
                # 遍历映射字典恢复反爬文本
                text = ''.join([charMap.get(c, c) for c in tmp])
                print(f"{title} 已下载")
                return {'success': True, 'title': title, 'content': text, 'id': chapter_id}
                
            elif resp['status']['httpCode'] == 403:
                print(f"[{chapter_id}] 403拦截：该章节未订阅/需付费。")
                return {'success': False, 'id': chapter_id, 'reason': '403_Forbidden'}
            else:
                print(f"[{chapter_id}] 异常状态码: {resp['status']['httpCode']}，准备重试 ({retry_count+1}/{max_retries})...")
        
        except Exception as e:
            print(f"[{chapter_id}] 网络波动或连接断开，准备重试 ({retry_count+1}/{max_retries})...")
            
        retry_count += 1
        time.sleep(1)
        
    print(f"[{chapter_id}] 已达到最大重试次数，章节获取彻底失败。")
    return {'success': False, 'id': chapter_id, 'reason': 'max_retries_exceeded'}

def download_volume_concurrent(chapters_list, max_threads, max_retries):
    """
    卷级并发控制器
    """
    results = {chap_id: None for chap_id in chapters_list}
    failed_chapters = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_chap = {
            executor.submit(download_single_chapter, chap_id, max_retries): chap_id 
            for chap_id in chapters_list
        }
        
        for future in as_completed(future_to_chap):
            chap_id = future_to_chap[future]
            res = future.result()
            results[chap_id] = res
            if not res['success']:
                failed_chapters.append(chap_id)

    return results, failed_chapters

# ================= 主控制流 =================
if __name__ == "__main__":
    cookie_file = "cookie.txt"
    config = {
        "cookie": "",
        "max_retries": 3,
        "max_threads": 5
    }

    # 读取及向前兼容配置格式
    if not os.path.exists(cookie_file):
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print("配置文件 cookie.txt 已自动创建。")
    else:
        with open(cookie_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            try:
                config = json.loads(content)
                print("加载配置文件成功。")
            except json.JSONDecodeError:
                config["cookie"] = content
                with open(cookie_file, "w", encoding="utf-8") as fw:
                    json.dump(config, fw, indent=4)
                print("已将旧版 cookie 文件转换为 JSON 格式配置。")

    headers['cookie'] = config.get("cookie", "")
    
    while check(headers):
        username = input("凭证无效，请输入手机号: ")
        password = input("输入密码: ")
        new_cookie = get_cookie(username, password)
        if new_cookie != "error":
            config["cookie"] = new_cookie
            headers['cookie'] = new_cookie
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)

    novel = input("输入小说ID: ")
    headers['user-agent'] = f'boluobao/5.2.16(android;35)/OPPO/{device_token.lower()}/OPPO'
    
    title, author, cover, chapters = get_catalog(novel)
    if title in ['标题获取失败', '目录获取失败']:
        exit()
        
    print(f"\n书名: {title}")
    i = 0
    for volume in chapters:
        i += 1
        print(f"{i} : {volume}")
        
    tot = i
    tr = True
    while tr:
        down = input("\n请输入需要下载的卷号(如 1,3-5，不输入则全下载): ")
        try:
            downList = []
            if down == '':
                downList = list(range(1, tot + 1))
            else:
                for part in down.split(','):
                    if '-' in part:
                        start, end = map(int, part.split('-'))
                        downList.extend(range(start, end + 1))
                    else:
                        downList.append(int(part))
            downList = list(set(downList))
            tr = False
        except Exception:
            print('卷号输入错误，请重新输入规则格式。')
            
    print("计划执行下载卷:", downList)
    
    all_volume_results = {} 
    all_failed_chapters = {}

    # === 执行并发拉取 ===
    i = 0
    for volume in chapters:
        i += 1
        if i in downList:
            print(f'\n=== 开始拉取卷: {volume} ===')
            res_dict, failed_list = download_volume_concurrent(
                chapters[volume], 
                config.get("max_threads", 5), 
                config.get("max_retries", 3)
            )
            all_volume_results[volume] = res_dict
            all_failed_chapters[volume] = failed_list

    # === 校验与后置重试 ===
    while True:
        total_failed = sum(len(f_list) for f_list in all_failed_chapters.values())
        if total_failed == 0:
            break
            
        print(f"\n[!] 数据拉取阶段结束，检测到有 {total_failed} 个章节下载失败。")
        for vol_name, f_list in all_failed_chapters.items():
            if f_list:
                print(f" -> [{vol_name}]: {len(f_list)} 章失败")
                
        retry_choice = input("是否针对失败章节发起定向复试？(输入 y 重试，其他键跳过进入打包环节): ")
        if retry_choice.lower() != 'y':
            break

        for volume, f_list in all_failed_chapters.items():
            if f_list:
                print(f'\n--- 正在定点复试卷: {volume} 的失败清单 ---')
                retry_res_dict, new_failed_list = download_volume_concurrent(
                    f_list, 
                    config.get("max_threads", 5), 
                    config.get("max_retries", 3)
                )
                for chap_id in f_list:
                    all_volume_results[volume][chap_id] = retry_res_dict[chap_id]
                all_failed_chapters[volume] = new_failed_list

    # === 构建封装 (EPUB & TXT) ===
    print("\n准备对已拉取数据执行渲染打包...")
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language('zh')
    book.add_author(author)
    
    try:
        img_cover_bytes = requests.get(cover, timeout=15).content
        book.set_cover('cover.jpg', img_cover_bytes)
    except Exception:
        print("[警告] 封面图片获取失败，以无封面格式继续...")
    
    content_text = title + '\n\n'
    toc = []
    spine = ['nav']
    
    i = 0
    for volume in chapters:
        i += 1
        if i in downList:
            content_text += volume + '\n\n'
            vol_toc = []
            vol_c = epub.EpubHtml(title=volume, file_name=f'vol_{i}.xhtml', lang='zh')
            vol_c.content = f"<h2>{volume}</h2>"
            book.add_item(vol_c)
            spine.append(vol_c)
            
            # 使用源有序ID队列重组
            for chapter_id in chapters[volume]:
                chap_data = all_volume_results[volume].get(chapter_id)
                
                if chap_data and chap_data.get('success'):
                    content_text += f"{chap_data['title']}\n{chap_data['content']}\n\n"
                    c = epub.EpubHtml(title=chap_data['title'], file_name=f"chap_{chap_data['id']}.xhtml", lang='zh')
                    c.content = f"<h2>{chap_data['title']}</h2>"
                    
                    for line in chap_data['content'].splitlines():
                        if '[img=' in line:
                            img_url_match = re.search(r'https?://.*?(?=\[\/img\]|$)', line)
                            if img_url_match:
                                img_url = img_url_match.group()
                                img_name = img_url.split('/')[-1]
                                try:
                                    img_bytes = requests.get(img_url, timeout=15).content
                                    print(f"图片 {img_name} 下载完成")
                                    img_item = epub.EpubImage(uid=str(uuid.uuid4()), file_name=f"img/{img_name}", media_type='image/jpg', content=img_bytes)
                                    c.content += f'<img src="img/{img_name}"/>'
                                    book.add_item(img_item)
                                except Exception:
                                    print(f"[警告] 图片 {img_name} 拉取失败，写入占位文本。")
                                    c.content += f"<p>[图片 {img_name} 加载失败]</p>"
                        else:
                            c.content += f"<p>{line}</p>"
                            
                    book.add_item(c)
                    vol_toc.append(c)
                    spine.append(c)
                else:
                    warning_msg = f"[系统标记：该章节 (ID:{chapter_id}) 拉取失败，内容已被强制跳过]"
                    print(warning_msg)
                    content_text += warning_msg + '\n\n'
                    
            toc.append((vol_c, tuple(vol_toc)))

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # 落盘
    title_clean = re.sub(r'[\\/:*?"<>|]', ' ', title)        
    epub.write_epub(f"{title_clean}{downList}.epub", book, {})
    with open(f'{title_clean}{downList}.txt', 'w', encoding="utf-8") as f:
        f.write(content_text)

    print(f"\n[执行完毕] 资源已持久化保存：{title_clean}{downList}.txt / {title_clean}{downList}.epub")
