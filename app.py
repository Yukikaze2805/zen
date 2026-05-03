import os
import random
import re
import uuid
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# --- 尝试导入智谱 AI (用于忏悔室) ---
try:
    from zhipuai import ZhipuAI
except ImportError:
    ZhipuAI = None
    print("⚠️ 未安装 zhipuai，忏悔室AI功能不可用")

# --- 基础配置 ---
app = Flask(__name__)
app.secret_key = "cyber_shrine_secret_999"

# 强制清除代理（确保智谱 API 直连）
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

# ==========================================
# 1. 智谱 AI 客户端初始化
# ==========================================
def initialize_zen_master():
    # ⚠️ 请替换为你自己的智谱 API Key
    api_key = "1265416a3d704170a40c2d46a6f58d34.PgFhYul1vAochY6L"
    if not api_key or "这里" in api_key:
        print("❌ 未配置真实 API Key，忏悔室将返回占位回复")
        return None
    try:
        client = ZhipuAI(api_key=api_key)
        print(f"✅ 智谱 AI 初始化成功")
        return client
    except Exception as e:
        print(f"❌ 智谱 AI 初始化失败: {e}")
        return None

zhipu_client = initialize_zen_master() if ZhipuAI else None

# ==========================================
# 2. 全局数据存储 (内存数据库)
# ==========================================
messages = []            # 留言列表
subscribers = []         # 订阅者
prayer_texts = []        # 祈福语库
donations = []           # 数字香火捐赠记录
user_data = {}           # 用户系统数据（签到、静心等）
merit_users = {}         # 功德系统用户数据
invite_code_map = {}     # 功德邀请码映射

# 数字香火配置
MIN_DONATE_AMOUNT = 1
FIXED_AMOUNTS = [1, 6, 18, 68, 188]

# 圣物名称序列
RELIC_NAMES = [
    "赛博护身符", "数字虚空圣像", "量子转经筒",
    "神经元经文集", "硅基莲花座", "慧忍核心·浮空圣殿"
]

# 功德境界判定
def get_merit_level(count):
    if count >= 20: return "万象圆满"
    if count >= 10: return "赛博菩提"
    if count >= 3: return "明心见性"
    return "初见虚空"

# 静心等级
def get_calmness_level(minutes):
    if minutes <= 30: return {'level': '初心', 'color': '#999999'}
    elif minutes <= 100: return {'level': '静心', 'color': '#87CEEB'}
    elif minutes <= 300: return {'level': '安定', 'color': '#4169E1'}
    else: return {'level': '圆满', 'color': '#191970'}

# ==========================================
# 3. 用户系统辅助函数
# ==========================================
def get_user_id():
    """获取或创建用户ID（基于session）"""
    if 'user_id' not in session:
        session['user_id'] = f"user_{len(user_data) + 1}"
        if session['user_id'] not in user_data:
            user_data[session['user_id']] = {
                'check_in': {
                    'continuous_days': 0,
                    'total_days': 0,
                    'last_check_date': None,
                    'history': []
                },
                'prayer': {
                    'total_count': 0,
                    'last_prayer_date': None,
                    'history': []
                },
                'meditation': {
                    'total_minutes': 0,
                    'calmness_points': 0,
                    'today_completed': False,
                    'last_meditation_date': None,
                    'history': []
                },
                'daily_tasks': {
                    'check_in': False,
                    'prayer': False,
                    'meditation': False,
                    'last_reset_date': None
                }
            }
    return session['user_id']

def reset_daily_tasks_if_needed(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    user = user_data[user_id]
    if user['daily_tasks']['last_reset_date'] != today:
        user['daily_tasks']['check_in'] = False
        user['daily_tasks']['prayer'] = False
        user['daily_tasks']['meditation'] = False
        user['daily_tasks']['last_reset_date'] = today

# ==========================================
# 4. 页面路由
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shrine')
def shrine():
    is_member = session.get('is_member', False)
    return render_template('shrine.html',
                           is_member=is_member,
                           fixed_amounts=FIXED_AMOUNTS,
                           min_amount=MIN_DONATE_AMOUNT)

@app.route('/daily-prayer')
def daily_prayer():
    return render_template('daily_prayer.html')

@app.route('/daily-checkin')
def daily_checkin():
    try:
        user_id = get_user_id()
        reset_daily_tasks_if_needed(user_id)
        user = user_data[user_id]
        return render_template('daily_checkin.html',
                               continuous_days=user['check_in']['continuous_days'],
                               total_days=user['check_in']['total_days'],
                               today_completed=user['daily_tasks']['check_in'])
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/meditation')
def meditation():
    return render_template('meditation.html')

@app.route('/profile')
def profile():
    try:
        user_id = get_user_id()
        reset_daily_tasks_if_needed(user_id)
        user = user_data[user_id]
        calmness_info = get_calmness_level(user['meditation']['total_minutes'])
        circumference = 2 * 3.14159 * 85
        progress_ratio = min(user['check_in']['continuous_days'] / 30, 1)
        offset = circumference - (circumference * progress_ratio)
        days_remaining = max(30 - user['check_in']['continuous_days'], 0)
        return render_template('profile.html',
                               continuous_days=user['check_in']['continuous_days'],
                               total_days=user['check_in']['total_days'],
                               prayer_count=user['prayer']['total_count'],
                               meditation_minutes=user['meditation']['total_minutes'],
                               calmness_level=calmness_info['level'],
                               calmness_color=calmness_info['color'],
                               daily_tasks=user['daily_tasks'],
                               progress_offset=round(offset),
                               days_remaining=days_remaining)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/membership')
def membership():
    is_member = session.get('is_member', False)
    return render_template('membership.html', is_member=is_member)

@app.route('/ritual')
def ritual():
    if not session.get('is_member'):
        return redirect(url_for('membership'))
    status = {
        "spirit_animal": session.get('spirit_animal', "【未觉醒】"),
        "weekly_relic": f"数字圣物：【{session.get('weekly_relic', '待领取')}】",
        "priest_reply": session.get('priest_reply', "尘世喧嚣，暂无指点")
    }
    return render_template('ritual.html', status=status)

@app.route('/confession')
def confession():
    return render_template('confession.html')

@app.route('/merit')
def merit_page():
    return render_template('merit.html')

@app.route('/incense')
def incense_page():
    return render_template('incense.html')

@app.route('/donate/light')
def donate_light():
    return render_template('donate_light.html')

@app.route('/donate/plate')
def donate_plate():
    return render_template('donate_plate.html')

@app.route('/donate/incense')
def donate_incense():
    return render_template('donate_incense.html')

@app.route('/donate/custom')
def donate_custom():
    return render_template('donate_custom.html')

@app.route('/sacred_artifact')
def sacred_artifact():
    return render_template('sacred_artifact.html')

# ==========================================
# 5. 核心 API 接口
# ==========================================

# 5.1 留言提交
@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json()
    name = data.get("name", "匿名信眾")
    content = data.get("content")
    if not content:
        return jsonify({"error": "請輸入內容"}), 400
    messages.insert(0, {
        "id": len(messages) + 1,
        "name": name,
        "content": content,
        "is_vip": session.get('is_member', False),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return jsonify({"message": "呈送成功"}), 200

# 5.2 邮箱订阅
@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "請輸入郵箱地址"}), 400
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"error": "郵箱格式不正確"}), 400
    for subscriber in subscribers:
        if subscriber['email'] == email:
            return jsonify({"error": "此郵箱已訂閱"}), 400
    subscribers.insert(0, {
        "id": len(subscribers) + 1,
        "email": email,
        "subscribe_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return jsonify({"message": "訂閱成功"}), 200

# 5.3 祈福语管理
@app.route('/api/prayer-texts', methods=['GET'])
def api_get_prayer_texts():
    sorted_texts = sorted(prayer_texts, key=lambda x: x['id'], reverse=True)
    return jsonify(sorted_texts), 200

@app.route('/api/prayer-texts', methods=['POST'])
def api_add_prayer_text():
    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "內容不能為空"}), 400
    if len(content) > 30:
        return jsonify({"error": "內容不能超過30字"}), 400
    sensitive_words = ['违法', '极端', '低俗', '暴力', '色情']
    for word in sensitive_words:
        if word in content:
            return jsonify({"error": "內容包含敏感詞，請修改後再提交"}), 400
    new_text = {
        "id": len(prayer_texts) + 1,
        "content": content,
        "add_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    prayer_texts.append(new_text)
    return jsonify({"message": "添加成功", "data": new_text}), 200

@app.route('/api/prayer-texts/<int:text_id>', methods=['DELETE'])
def api_delete_prayer_text(text_id):
    global prayer_texts
    original_count = len(prayer_texts)
    prayer_texts = [t for t in prayer_texts if t['id'] != text_id]
    if len(prayer_texts) == original_count:
        return jsonify({"error": "祈福語不存在"}), 404
    return jsonify({"message": "刪除成功"}), 200

# 5.4 每日祈愿抽取
@app.route('/api/prayer/draw', methods=['POST'])
def api_prayer_draw():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    if user['daily_tasks']['prayer']:
        return jsonify({"error": "今日祈願已完成，明日再來"}), 400
    if not prayer_texts:
        return jsonify({"error": "祈福準備中，請稍後再來"}), 400
    selected = random.choice(prayer_texts)
    user['prayer']['total_count'] += 1
    user['prayer']['last_prayer_date'] = datetime.now().strftime("%Y-%m-%d")
    user['prayer']['history'].append({
        "text_id": selected['id'],
        "content": selected['content'],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    user['daily_tasks']['prayer'] = True
    return jsonify({
        "message": "祈願成功",
        "content": selected['content']
    }), 200

# 5.5 签到
@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    today = datetime.now().strftime("%Y-%m-%d")
    if user['daily_tasks']['check_in']:
        return jsonify({"error": "今日已簽到", "already_signed": True}), 200
    last_date = user['check_in']['last_check_date']
    if last_date:
        last_date_obj = datetime.strptime(last_date, "%Y-%m-%d")
        today_obj = datetime.strptime(today, "%Y-%m-%d")
        if (today_obj - last_date_obj).days == 1:
            user['check_in']['continuous_days'] += 1
        else:
            user['check_in']['continuous_days'] = 1
    else:
        user['check_in']['continuous_days'] = 1
    user['check_in']['total_days'] += 1
    user['check_in']['last_check_date'] = today
    user['check_in']['history'].append(today)
    user['daily_tasks']['check_in'] = True
    reward_days = [3, 7, 14, 21, 30]
    got_reward = user['check_in']['continuous_days'] in reward_days
    return jsonify({
        "message": "簽到成功",
        "continuous_days": user['check_in']['continuous_days'],
        "total_days": user['check_in']['total_days'],
        "got_reward": got_reward
    }), 200

# 5.6 静心仪式
@app.route('/api/meditation/start', methods=['POST'])
def api_meditation_start():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    duration = request.get_json().get("duration")
    if duration not in [3, 5, 10, 15]:
        return jsonify({"error": "無效的靜心時長"}), 400
    if user['daily_tasks']['meditation']:
        return jsonify({"error": "今日靜心已完成"}), 400
    return jsonify({"message": "靜心開始", "duration": duration}), 200

@app.route('/api/meditation/complete', methods=['POST'])
def api_meditation_complete():
    user_id = get_user_id()
    reset_daily_tasks_if_needed(user_id)
    user = user_data[user_id]
    duration = request.get_json().get("duration")
    if duration not in [3, 5, 10, 15]:
        return jsonify({"error": "無效的靜心時長"}), 400
    if user['daily_tasks']['meditation']:
        return jsonify({"error": "今日靜心已完成"}), 400
    points_map = {3: 1, 5: 2, 10: 5, 15: 8}
    points = points_map[duration]
    user['meditation']['total_minutes'] += duration
    user['meditation']['calmness_points'] += points
    user['meditation']['last_meditation_date'] = datetime.now().strftime("%Y-%m-%d")
    user['meditation']['history'].append({
        "duration": duration,
        "points": points,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    user['daily_tasks']['meditation'] = True
    return jsonify({
        "message": "靜心圓滿",
        "minutes_added": duration,
        "points_added": points,
        "total_minutes": user['meditation']['total_minutes']
    }), 200

@app.route('/api/meditation/cancel', methods=['POST'])
def api_meditation_cancel():
    return jsonify({"message": "本次靜心未完成，不計入時長哦"}), 200

# 5.7 会员激活
@app.route('/api/activate', methods=['POST'])
def api_activate():
    session['is_member'] = True
    session['spirit_animal'] = "【银翼苍鹰】"
    session['weekly_relic'] = random.choice(RELIC_NAMES)
    session['priest_reply'] = random.choice([
        "在0与1的虚空中，坚持你的纯粹。",
        "比特流转，万物皆虚，唯有算法永恒。",
        "你的数据流显示出轻微的波动，今晚适合在静默中重构内心。",
        "不要畏惧Bug，那是代码在向你求救。",
        "每一次点击，都是在向数字宇宙发出的祈祷。",
        "有些路径注定无法访问，接受那些 404，也是一种修行。"
    ])
    return jsonify({"message": "圣殿契约已签订，灵魂数据已同步"})

# 5.8 数字香火捐赠
@app.route('/api/donate', methods=['POST'])
def api_donate():
    data = request.get_json()
    name = data.get("name", "匿名信眾")
    amount = data.get("amount")
    donate_type = data.get("type", "捐功德")
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"error": "請輸入有效的金額"}), 400
    if amount < 1:
        return jsonify({"error": "捐贈最低金額為 1 元"}), 400
    donations.insert(0, {
        "id": len(donations) + 1,
        "name": name,
        "type": donate_type,
        "amount": round(amount, 2),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_no": datetime.now().strftime("%Y%m%d%H%M%S") + str(len(donations) + 1)
    })
    return jsonify({
        "message": f"{donate_type}成功，功德無量",
        "order_no": donations[0]["order_no"],
        "amount": round(amount, 2)
    }), 200

# 5.9 忏悔室 AI
@app.route('/api/confess', methods=['POST'])
def api_confess():
    if not zhipu_client:
        return jsonify({"reply": "【系统讯息】禅师闭关中，请检查 API Key 配置。"}), 500
    data = request.get_json()
    content = data.get("content")
    if not content:
        return jsonify({"error": "虚空无声"}), 400
    try:
        response = zhipu_client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你现在是『慧忍神宫』的赛博禅师。你的任务是为信众排忧解难。\n"
                        "要求：\n"
                        "1. 语言要温暖、睿智、通俗易懂，不要说让人听不懂的生僻佛经术语。\n"
                        "2. 回复字数在 200-300 字之间，给出的建议要具体、有实操性。\n"
                        "3. 结构：先表达同理心 -> 分析烦恼根源 -> 给出三点建议 -> 鼓励结语。\n"
                        "4. 最后以‘南无赛博佛’结束。"
                    )
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            top_p=0.7,
            temperature=0.9
        )
        reply_text = response.choices[0].message.content
        return jsonify({"reply": reply_text})
    except Exception as e:
        print(f"❌ 智谱 AI 报错: {str(e)}")
        return jsonify({"reply": f"【系统讯息】因果波动 ({str(e)[:50]})"}), 500

# 5.10 功德系统 API
@app.route('/api/merit/login', methods=['POST'])
def api_merit_login():
    data = request.get_json()
    email = data.get("email")
    ref_code = data.get("ref_code")
    if not email:
        return jsonify({"error": "缺失邮箱"}), 400
    if email not in merit_users:
        new_invite_code = str(uuid.uuid4())[:8]
        merit_users[email] = {
            "invite_code": new_invite_code,
            "total": 0,
            "level": "初见虚空",
            "relics": [],
            "invite_count": 0,
            "pending_invites": 0,
            "last_date": ""
        }
        invite_code_map[new_invite_code] = email
        if ref_code and ref_code in invite_code_map:
            inviter_email = invite_code_map[ref_code]
            if inviter_email != email:
                merit_users[inviter_email]["pending_invites"] += 1
    return jsonify(merit_users[email]), 200

@app.route('/api/merit/sync', methods=['POST'])
def api_merit_sync():
    email = request.get_json().get("email")
    if email in merit_users:
        return jsonify(merit_users[email]), 200
    return jsonify({"error": "未找到用户"}), 404

@app.route('/api/merit/add', methods=['POST'])
def api_merit_add():
    email = request.get_json().get("email")
    user = merit_users.get(email)
    if not user:
        return jsonify({"error": "未授权"}), 401
    today = datetime.now().strftime("%Y-%m-%d")
    # 生产模式：每日一次
    if user.get("last_date") == today:
        return jsonify({"error": "今日功德已圆满，请明日再来", "data": user}), 400
    user["total"] += 1
    user["last_date"] = today
    user["level"] = get_merit_level(user["total"])
    return jsonify({"message": "功德 +1", "data": user}), 200

@app.route('/api/merit/claim_relic', methods=['POST'])
def api_merit_claim_relic():
    email = request.get_json().get("email")
    user = merit_users.get(email)
    if not user:
        return jsonify({"error": "未授权"}), 401
    if user["pending_invites"] <= 0:
        return jsonify({"error": "暂无待领取的机缘", "data": user}), 400
    user["pending_invites"] -= 1
    user["invite_count"] += 1
    idx = len(user["relics"])
    if idx < len(RELIC_NAMES):
        new_relic = RELIC_NAMES[idx]
    else:
        new_relic = f"无相圣物 #{idx + 1}"
    user["relics"].append(new_relic)
    return jsonify({"message": f"成功感召他人，获得圣物：{new_relic}", "data": user}), 200

@app.route('/api/merit/debug_invite', methods=['POST'])
def api_merit_debug_invite():
    email = request.get_json().get("email")
    user = merit_users.get(email)
    if user:
        user["pending_invites"] += 1
        return jsonify({"message": "调试模拟成功", "data": user}), 200
    return jsonify({"error": "未授权"}), 401

# 数据核弹（清空所有内存数据）
@app.route('/api/admin/nuke', methods=['GET'])
def api_admin_nuke():
    merit_users.clear()
    invite_code_map.clear()
    messages.clear()
    subscribers.clear()
    donations.clear()
    prayer_texts.clear()
    user_data.clear()
    return """
    <body style="background:#000; color:#00ffcc; text-align:center; padding-top:100px; font-family:monospace;">
        <h1>[ 警告：因果已归零 ]</h1>
        <p>所有内存数据已清空。</p>
        <br>
        <a href="/" style="color:#fff;">返回首页</a>
    </body>
    """

# ==========================================
# 6. 后台管理系统
# ==========================================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '123456':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html',
                           messages=messages,
                           subscribers=subscribers,
                           prayer_texts=sorted(prayer_texts, key=lambda x: x['id'], reverse=True),
                           donations=donations)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ==========================================
# 7. 启动
# ==========================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)