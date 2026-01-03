from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
import json
import os
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
import utils
from config import EMAIL_VERIFICATION_ENABLED, MAX_MESSAGES_PER_DAY_UNFOLLOWED, REMINDER_TIMES, REMINDER_CHECK_SECRET

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Load configuration
app.config.from_pyfile('config.py', silent=True)

# Override EMAIL_VERIFICATION_ENABLED from config.json if present
config = utils.load_config()
if 'email_verification_enabled' in config:
    EMAIL_VERIFICATION_ENABLED = config['email_verification_enabled']

# Custom template filters
from datetime import datetime

@app.template_filter('time_ago')
def time_ago_filter(date_str):
    """将ISO时间字符串转换为相对时间描述"""
    if not date_str:
        return ''
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        return date_str
    now = datetime.now()
    delta = now - date
    seconds = delta.total_seconds()
    if seconds < 60:
        return '刚刚'
    minutes = seconds / 60
    if minutes < 60:
        return f'{int(minutes)}分钟前'
    hours = minutes / 60
    if hours < 24:
        return f'{int(hours)}小时前'
    days = hours / 24
    if days < 30:
        return f'{int(days)}天前'
    months = days / 30
    if months < 12:
        return f'{int(months)}个月前'
    years = months / 12
    return f'{int(years)}年前'

@app.template_filter('format_date')
def format_date_filter(date_str):
    """格式化日期时间"""
    if not date_str:
        return ''
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date.strftime('%Y-%m-%d %H:%M')
    except ValueError:
        return date_str

@app.template_filter('format_time')
def format_time_filter(date_str):
    """仅格式化时间部分"""
    if not date_str:
        return ''
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date.strftime('%H:%M')
    except ValueError:
        return date_str

@app.template_filter('truncate')
def truncate_filter(text, length=200):
    """截断文本，并在末尾添加省略号"""
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length] + '...'

@app.template_filter('post_content')
def post_content_filter(content):
    """将内容中的 [图片URL] 转换为 img 标签"""
    if not content:
        return ''
    import re
    # 匹配 [任意非]字符] 格式，假定为图片URL
    def replace(match):
        url = match.group(1)
        # 如果URL以常见图片扩展名结尾，或任意URL都视为图片
        return f'<img src="{url}" class="img-fluid rounded my-2" alt="图片" style="max-width: 100%; height: auto;">'
    # 使用正则替换 [URL] 模式
    content = re.sub(r'\[([^]]+)\]', replace, content)
    # 将换行符转换为 <br>
    content = content.replace('\n', '<br>')
    return content

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator (assuming admin user id is 1)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_id') != 1:
            flash('需要管理员权限')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor to inject variables into templates
@app.context_processor
def inject_variables():
    def get_unread_count(user_id):
        notifications = utils.get_user_notifications(user_id)
        return sum(1 for n in notifications if not n.get('read'))
    return dict(get_unread_count=get_unread_count, EMAIL_VERIFICATION_ENABLED=EMAIL_VERIFICATION_ENABLED, REMINDER_TIMES=REMINDER_TIMES)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    tasks = utils.get_tasks_by_user(user_id)
    stats = {
        'total_tasks': len(tasks),
        'completed_tasks': sum(1 for t in tasks if t.get('status') == 'completed'),
        'in_progress_tasks': sum(1 for t in tasks if t.get('status') == 'in_progress'),
        'pending_tasks': sum(1 for t in tasks if t.get('status') == 'pending'),
    }
    recent_tasks = sorted(tasks, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    recent_notifications = utils.get_user_notifications(user_id)[:5]
    quota = utils.get_test_email_quota(user_id)
    return render_template('dashboard.html', stats=stats, recent_tasks=recent_tasks, recent_notifications=recent_notifications, quota=quota)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        user = None
        if '@' in identifier:
            user = utils.get_user_by_email(identifier)
        else:
            user = utils.get_user_by_username(identifier)
        if user and utils.check_password(user, password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('登录成功', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名/邮箱或密码错误', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        verification_code = request.form.get('verification_code')
        
        if password != confirm:
            flash('两次密码输入不一致', 'danger')
            return redirect(url_for('register'))
        
        if utils.get_user_by_username(username):
            flash('用户名已存在', 'danger')
            return redirect(url_for('register'))
        
        if utils.get_user_by_email(email):
            flash('邮箱已被注册', 'danger')
            return redirect(url_for('register'))
        
        verified = False
        if EMAIL_VERIFICATION_ENABLED:
            # 从 session 中获取验证码
            stored_code = session.get('verification_code')
            stored_email = session.get('verification_email')
            stored_sent_at = session.get('verification_sent_at')
            if not stored_code or not stored_email or stored_email != email:
                flash('验证码无效或已过期', 'danger')
                return redirect(url_for('register'))
            # 检查过期时间（10分钟）
            try:
                sent_at = datetime.fromisoformat(stored_sent_at)
                if datetime.now() - sent_at > timedelta(minutes=10):
                    flash('验证码已过期', 'danger')
                    return redirect(url_for('register'))
            except (ValueError, TypeError):
                flash('验证码时间错误', 'danger')
                return redirect(url_for('register'))
            if verification_code != stored_code:
                flash('验证码错误', 'danger')
                return redirect(url_for('register'))
            verified = True
            # 清除 session 中的验证码，防止重复使用
            session.pop('verification_code', None)
            session.pop('verification_email', None)
            session.pop('verification_sent_at', None)
        
        user_id = utils.create_user(username, password, email, verified)
        session['user_id'] = user_id
        session['username'] = username
        flash('注册成功', 'success')
        if not verified:
            utils.add_notification(user_id, '邮箱未验证', '您的邮箱尚未验证，部分功能受限。请尽快验证。')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html', email_verification_enabled=EMAIL_VERIFICATION_ENABLED)

@app.route('/register/send_verification_code', methods=['POST'])
def send_verification_code():
    if not EMAIL_VERIFICATION_ENABLED:
        return jsonify({'success': False, 'message': '邮箱验证功能未开启'}), 400
    email = request.form.get('email')
    if not email:
        return jsonify({'success': False, 'message': '邮箱不能为空'}), 400
    # 生成验证码
    code = utils.generate_verification_code()
    # 存储到 session（以邮箱为键）
    session['verification_code'] = code
    session['verification_email'] = email
    session['verification_sent_at'] = datetime.now().isoformat()
    # 发送邮件
    subject = 'Smart To-Do 注册验证码'
    body = f'''您的注册验证码是：{code}，请在10分钟内完成注册。
如果您未请求此验证码，请忽略此邮件。'''
    success = utils.send_email(email, subject, body)
    if success:
        return jsonify({'success': True, 'message': '验证码已发送到您的邮箱'})
    else:
        # 清除 session 中的验证码
        session.pop('verification_code', None)
        session.pop('verification_email', None)
        session.pop('verification_sent_at', None)
        return jsonify({'success': False, 'message': '发送失败，请检查邮箱配置或稍后重试'}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))

# Tasks routes
@app.route('/tasks')
@login_required
def tasks():
    user_id = session['user_id']
    task_list = utils.get_tasks_by_user(user_id)
    return render_template('tasks.html', tasks=task_list)

@app.route('/tasks/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_time = request.form.get('start_time')
        location = request.form.get('location')
        duration = request.form.get('duration')
        notes = request.form.get('notes')
        
        show_on_homepage = request.form.get('show_on_homepage') == 'on'
        reminder_times = []
        custom_times_str = request.form.get('custom_reminder_times', '').strip()
        if custom_times_str:
            for part in custom_times_str.split(','):
                part = part.strip()
                if part.isdigit():
                    reminder_times.append(int(part))
            # 去重
            reminder_times = list(set(reminder_times))
        task_data = {
            'name': name,
            'description': description,
            'start_time': start_time,
            'location': location,
            'duration': duration,
            'notes': notes,
            'show_on_homepage': show_on_homepage,
            'reminder_times': reminder_times,
        }
        task_id = utils.add_task(session['user_id'], task_data)
        flash('任务添加成功', 'success')
        return redirect(url_for('tasks'))
    return render_template('add_task.html')

@app.route('/tasks/ai_parse', methods=['POST'])
@login_required
def ai_parse_task():
    """解析自然语言文本为任务数据"""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': '缺少文本内容'}), 400
    text = data['text'].strip()
    if not text:
        return jsonify({'error': '文本为空'}), 400
    task_data = utils.parse_task_with_ai(text)
    if task_data is None:
        return jsonify({'error': 'AI解析失败，请检查API配置或稍后重试'}), 500
    return jsonify(task_data)

@app.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    task = utils.get_task_by_id(task_id)
    if not task:
        abort(404)
    is_owner = task['user_id'] == session['user_id']
    if not is_owner and not task.get('show_on_homepage', False):
        abort(404)
    # 自动更新状态（如果已开始）
    task = utils.update_task_status_if_needed(task)
    # 获取任务所有者的任务列表，用于计算索引和相似任务
    owner_tasks = utils.get_tasks_by_user(task['user_id'])
    # 按创建时间排序
    owner_tasks_sorted = sorted(owner_tasks, key=lambda x: x.get('created_at', ''))
    # 查找当前任务在所有者任务列表中的索引（1-based）
    task_index = None
    for i, t in enumerate(owner_tasks_sorted):
        if t['id'] == task_id:
            task_index = i + 1
            break
    # 相似任务：相同状态的任务数（在所有者任务中）
    similar_count = sum(1 for t in owner_tasks if t.get('status') == task.get('status'))
    return render_template('task_detail.html', task=task, task_index=task_index, similar_count=similar_count, is_owner=is_owner)

@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = utils.get_task_by_id(task_id)
    if not task or task['user_id'] != session['user_id']:
        abort(404)
    if request.method == 'POST':
        updates = {}
        # 如果任务状态为 pending，禁止修改状态
        if task.get('status') == 'pending':
            # 只允许修改非状态字段
            allowed_fields = ['name', 'description', 'start_time', 'location', 'duration', 'notes', 'show_on_homepage', 'reminder_times']
            for field in allowed_fields:
                if field in request.form:
                    updates[field] = request.form.get(field)
            # 如果尝试修改状态或完成率，忽略
        else:
            # 允许修改所有字段，但完成率仅当状态为 completed 时才可设置
            for field in ['name', 'description', 'start_time', 'location', 'duration', 'notes', 'status', 'completion_rate', 'show_on_homepage', 'reminder_times']:
                if field in request.form:
                    if field == 'completion_rate' and request.form.get('status') != 'completed' and updates.get('status') != 'completed':
                        # 如果新状态不是 completed，禁止设置完成率
                        continue
                    updates[field] = request.form.get(field)
        # 处理提醒时间
        reminder_times = []
        custom_times_str = request.form.get('custom_reminder_times', '').strip()
        if custom_times_str:
            for part in custom_times_str.split(','):
                part = part.strip()
                if part.isdigit():
                    reminder_times.append(int(part))
            # 去重
            reminder_times = list(set(reminder_times))
        updates['reminder_times'] = reminder_times
        updates['show_on_homepage'] = request.form.get('show_on_homepage') == 'on'
        utils.update_task(task_id, updates)
        flash('任务更新成功', 'success')
        return redirect(url_for('task_detail', task_id=task_id))
    return render_template('edit_task.html', task=task)

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = utils.get_task_by_id(task_id)
    if not task or task['user_id'] != session['user_id']:
        abort(404)
    utils.delete_task(task_id)
    flash('任务已删除', 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:task_id>/test_reminder', methods=['POST'])
@login_required
def test_reminder(task_id):
    """发送测试提醒通知和邮件"""
    task = utils.get_task_by_id(task_id)
    if not task or task['user_id'] != session['user_id']:
        abort(404)
    user_id = session['user_id']
    # 添加测试通知
    utils.add_notification(
        user_id,
        '测试提醒',
        f'任务「{task["name"]}」的测试提醒已发送。',
        'reminder'
    )
    # 发送测试邮件
    user = utils.get_user_by_id(user_id)
    if user and user.get('email'):
        subject = f'Smart To-Do 任务测试提醒：{task["name"]}'
        body = f'''任务「{task["name"]}」的测试提醒已发送。
开始时间：{task.get('start_time', '未设置')}
地点：{task.get('location', '未设置')}
备注：{task.get('notes', '无')}
这是一封测试邮件，用于验证提醒功能是否正常工作。
'''
        try:
            utils.send_email(user['email'], subject, body)
        except Exception as e:
            # 邮件发送失败不影响主要流程，仅记录
            print(f"发送测试提醒邮件失败: {e}")
    flash('测试提醒已发送，请查看通知和邮箱', 'success')
    return redirect(url_for('task_detail', task_id=task_id))

# Notifications
@app.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20
    paginated = utils.get_user_notifications_paginated(user_id, page=page, per_page=per_page)
    page_range = utils.generate_pagination_range(page, paginated['total_pages'])
    paginated['page_range'] = page_range
    return render_template('notifications.html', **paginated)

@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    utils.mark_notification_read(notif_id)
    return jsonify({'success': True})

# Messages
@app.route('/messages')
@login_required
def messages():
    user_id = session['user_id']
    following = utils.get_following(user_id)
    followers = utils.get_followers(user_id)
    
    # 获取选定的对话用户
    with_user = request.args.get('with_user', type=int)
    limit = request.args.get('limit', default=20, type=int)
    offset = request.args.get('offset', default=0, type=int)
    
    messages = []
    selected_user = None
    has_more = False
    
    if with_user:
        # 验证用户是否存在
        target_user = utils.get_user_by_id(with_user)
        if target_user:
            selected_user = target_user
            # 获取分页消息（按时间降序，最新的在前）
            messages = utils.get_messages_between(user_id, with_user, limit=limit, offset=offset, reverse=True)
            # 为每条消息添加发送者姓名
            for msg in messages:
                sender = utils.get_user_by_id(msg['sender_id'])
                msg['sender_name'] = sender.get('nickname') or sender.get('username') if sender else '未知用户'
            # 反转消息顺序，使最旧的消息在前，最新的在后（从上到下时间递增）
            messages = list(reversed(messages))
            # 检查是否还有更多消息
            total_messages = utils.get_messages_between(user_id, with_user, limit=None, offset=0, reverse=False)
            total_count = len(total_messages)
            has_more = (offset + limit) < total_count
        else:
            flash('用户不存在', 'danger')
    # 如果不指定 with_user，则 messages 为空，selected_user 为 None
    
    return render_template('messages.html',
                           following=following,
                           followers=followers,
                           messages=messages,
                           selected_user=selected_user,
                           with_user=with_user,
                           has_more=has_more,
                           limit=limit,
                           offset=offset)

@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    try:
        receiver_id = int(request.form.get('receiver_id'))
    except (ValueError, TypeError):
        flash('无效的接收者', 'danger')
        return redirect(url_for('messages'))
    content = request.form.get('content')
    sender_id = session['user_id']
    
    # Check if mutual follow
    mutual = utils.are_mutual_followers(sender_id, receiver_id)
    if not mutual:
        # Limit messages per day
        count = utils.count_messages_today(sender_id, receiver_id)
        if count >= MAX_MESSAGES_PER_DAY_UNFOLLOWED:
            flash('未互相关注，每日最多发送10条消息', 'danger')
            return redirect(url_for('messages', with_user=receiver_id))
    
    utils.send_message(sender_id, receiver_id, content)
    flash('消息发送成功', 'success')
    return redirect(url_for('messages', with_user=receiver_id))

@app.route('/api/search_users')
@login_required
def api_search_users():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': '缺少搜索关键词'}), 400
    user_id = session['user_id']
    results = utils.search_users(query, user_id)
    return jsonify({'users': results})

# Profile
@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = utils.get_user_by_id(user_id)
    if not user:
        abort(404)
    is_self = user_id == session['user_id']
    is_following = utils.is_following(session['user_id'], user_id) if not is_self else False
    user_tasks = utils.get_tasks_by_user(user_id)
    if not is_self:
        user_tasks = [task for task in user_tasks if task.get('show_on_homepage', False)]
    user_posts = utils.get_posts_by_user(user_id)
    return render_template('profile.html', user=user, is_self=is_self, is_following=is_following, user_tasks=user_tasks, user_posts=user_posts)

@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    follower_id = session['user_id']
    if follower_id == user_id:
        flash('不能关注自己', 'danger')
    else:
        if utils.is_following(follower_id, user_id):
            utils.unfollow_user(follower_id, user_id)
            flash('已取消关注', 'success')
        else:
            utils.follow_user(follower_id, user_id)
            flash('关注成功', 'success')
    return redirect(url_for('profile', user_id=user_id))

# Profile editing
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        bio = request.form.get('bio')
        avatar = request.form.get('avatar')
        updates = {}
        if nickname:
            updates['nickname'] = nickname
        if bio is not None:
            updates['bio'] = bio
        if avatar:
            updates['avatar'] = avatar
        if updates:
            utils.update_user(session['user_id'], updates)
            flash('资料更新成功', 'success')
        return redirect(url_for('profile', user_id=session['user_id']))
    # GET request: render edit form
    user = utils.get_user_by_id(session['user_id'])
    quota = utils.get_test_email_quota(session['user_id'])
    return render_template('edit_profile.html', user=user, quota=quota)

# Community
@app.route('/community')
@login_required
def community():
    posts = utils.get_all_posts()
    return render_template('community.html', posts=posts)

@app.route('/community/post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form.get('content')
        # 图片已通过 [图片URL] 格式嵌入正文，不再单独上传
        images = []
        post_id = utils.create_post(session['user_id'], content, images)
        flash('帖子发布成功', 'success')
        return redirect(url_for('community'))
    return render_template('create_post.html')

@app.route('/community/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = utils.get_post_by_id(post_id)
    if not post or post['user_id'] != session['user_id']:
        abort(404)
    if request.method == 'POST':
        content = request.form.get('content')
        # 图片已通过 [图片URL] 格式嵌入正文，不再单独存储
        updates = {'content': content, 'images': []}
        utils.update_post(post_id, updates)
        flash('帖子更新成功', 'success')
        return redirect(url_for('community'))
    return render_template('edit_post.html', post=post)

@app.route('/community/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = utils.get_post_by_id(post_id)
    if not post or post['user_id'] != session['user_id']:
        abort(404)
    utils.delete_post(post_id)
    flash('帖子已删除', 'success')
    return redirect(url_for('community'))

@app.route('/community/post/<int:post_id>/like', methods=['POST'])
@login_required
def toggle_like(post_id):
    user_id = session['user_id']
    utils.toggle_like(post_id, user_id)
    # 返回JSON响应以便前端更新
    post = utils.get_post_by_id(post_id)
    return jsonify({'likes_count': len(post.get('likes', [])), 'liked': user_id in post.get('likes', [])})

@app.route('/community/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    user_id = session['user_id']
    content = request.form.get('content')
    if not content:
        flash('评论内容不能为空', 'danger')
        return redirect(url_for('community'))
    comment_id = utils.add_comment(post_id, user_id, content)
    flash('评论发布成功', 'success')
    return redirect(url_for('community'))

@app.route('/community/post/<int:post_id>/comment/<int:comment_id>/like', methods=['POST'])
@login_required
def toggle_comment_like(post_id, comment_id):
    user_id = session['user_id']
    success = utils.toggle_comment_like(post_id, comment_id, user_id)
    if not success:
        return jsonify({'error': '操作失败'}), 400
    # 获取更新后的评论数据
    post = utils.get_post_by_id(post_id)
    comment = None
    for c in post.get('comments', []):
        if c['id'] == comment_id:
            comment = c
            break
    if comment:
        return jsonify({
            'likes_count': len(comment.get('likes', [])),
            'liked': user_id in comment.get('likes', [])
        })
    else:
        return jsonify({'error': '评论不存在'}), 404

@app.route('/community/post/<int:post_id>/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(post_id, comment_id):
    user_id = session['user_id']
    success = utils.delete_comment(post_id, comment_id, user_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': '删除失败，权限不足或评论不存在'}), 403

# Calendar
@app.route('/calendar')
@login_required
def calendar_view():
    tasks = utils.get_tasks_by_user(session['user_id'])
    events = []
    today_tasks = []
    today = datetime.now().date()
    for task in tasks:
        if task.get('start_time'):
            # 添加到事件列表
            events.append({
                'title': task['name'],
                'start': task['start_time'],
                'color': '#007bff',
                'extendedProps': {
                    'taskId': task['id'],
                    'location': task.get('location', ''),
                    'startTime': task['start_time']
                }
            })
            # 检查是否为今天任务
            try:
                start_date = datetime.fromisoformat(task['start_time'].replace('Z', '+00:00')).date()
                if start_date == today:
                    today_tasks.append(task)
            except ValueError:
                pass
    return render_template('calendar.html', events=events, today_tasks=today_tasks)

# Statistics
@app.route('/stats')
@login_required
def stats():
    user_id = session['user_id']
    stats_data = utils.get_user_stats(user_id, days=7)
    # For template, also compute period stats (simplified)
    period_stats = {
        'last7': {
            'total': stats_data['total_tasks'],
            'completed': stats_data['completed_tasks'],
            'avg_rate': stats_data['avg_completion_rate'],
            'max_rate': max(stats_data['rates']) if stats_data['rates'] else 0,
        },
        'last30': {
            'total': stats_data['total_tasks'],
            'completed': stats_data['completed_tasks'],
            'avg_rate': stats_data['avg_completion_rate'],
            'max_rate': max(stats_data['rates']) if stats_data['rates'] else 0,
        },
        'last365': {
            'total': stats_data['total_tasks'],
            'completed': stats_data['completed_tasks'],
            'avg_rate': stats_data['avg_completion_rate'],
            'max_rate': max(stats_data['rates']) if stats_data['rates'] else 0,
        }
    }
    return render_template('stats.html', stats=stats_data, dates=stats_data['dates'], rates=stats_data['rates'], period_stats=period_stats)

# Admin routes
@app.route('/admin')
@admin_required
def admin():
    users = utils.load_json('users.json')
    users_list = []
    for uid, user in users.items():
        users_list.append({
            'id': int(uid),
            'username': user.get('username'),
            'email': user.get('email'),
            'verified': user.get('verified', False),
            'created_at': user.get('created_at', ''),
        })
    # Sort by id
    users_list.sort(key=lambda x: x['id'])
    
    tasks = utils.load_json('tasks.json')
    posts = utils.load_json('posts.json')
    messages = utils.load_json('messages.json')
    
    stats = {
        'total_users': len(users_list),
        'total_tasks': len(tasks),
        'total_posts': len(posts),
        'total_messages': len(messages),
    }
    api_key, api_url, ai_enabled = utils.get_deepseek_config()
    email_config = utils.get_email_config()
    return render_template('admin.html', users=users_list, deepseek_api_key=api_key, deepseek_api_url=api_url, deepseek_ai_enabled=ai_enabled, email_config=email_config, **stats)

@app.route('/admin/toggle_email_verification', methods=['POST'])
@admin_required
def toggle_email_verification():
    global EMAIL_VERIFICATION_ENABLED
    EMAIL_VERIFICATION_ENABLED = not EMAIL_VERIFICATION_ENABLED
    # 持久化到 config.json
    config = utils.load_config()
    config['email_verification_enabled'] = EMAIL_VERIFICATION_ENABLED
    utils.save_config(config)
    flash('邮箱验证功能已{}'.format('开启' if EMAIL_VERIFICATION_ENABLED else '关闭'), 'success')
    return redirect(url_for('admin'))

@app.route('/admin/set_deepseek_config', methods=['POST'])
@admin_required
def set_deepseek_config():
    api_key = request.form.get('api_key', '').strip()
    api_url = request.form.get('api_url', '').strip()
    ai_enabled = request.form.get('ai_enabled') == 'on'
    # 如果URL为空，使用默认值
    if not api_url:
        api_url = 'https://api.deepseek.com/v1/chat/completions'
    utils.update_deepseek_config(api_key=api_key, api_url=api_url, ai_enabled=ai_enabled)
    flash('DeepSeek API配置已更新', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/set_email_config', methods=['POST'])
@admin_required
def set_email_config():
    mail_server = request.form.get('mail_server', '').strip()
    mail_port = request.form.get('mail_port', type=int)
    mail_use_tls = request.form.get('mail_use_tls') == 'on'
    mail_username = request.form.get('mail_username', '').strip()
    mail_password = request.form.get('mail_password', '').strip()
    mail_default_sender = request.form.get('mail_default_sender', '').strip()
    utils.update_email_config(
        mail_server=mail_server if mail_server else None,
        mail_port=mail_port if mail_port else None,
        mail_use_tls=mail_use_tls,
        mail_username=mail_username if mail_username else None,
        mail_password=mail_password if mail_password else None,
        mail_default_sender=mail_default_sender if mail_default_sender else None
    )
    flash('邮箱SMTP配置已更新', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/send_notification', methods=['POST'])
@admin_required
def admin_send_notification():
    title = request.form.get('title')
    content = request.form.get('content')
    if not title or not content:
        flash('标题和内容不能为空', 'danger')
        return redirect(url_for('admin'))
    # Send to all users
    users = utils.load_json('users.json')
    for uid in users.keys():
        utils.add_notification(int(uid), title, content, 'system')
    flash('全局通知发送成功', 'success')
    return redirect(url_for('admin'))

# 测试邮箱配置
@app.route('/admin/test_email_config', methods=['POST'])
@admin_required
def admin_test_email_config():
    user = utils.get_user_by_id(session['user_id'])
    if not user or not user.get('email'):
        flash('管理员邮箱未设置', 'danger')
        return redirect(url_for('admin'))
    email = user['email']
    subject = 'Smart To-Do 邮箱配置测试邮件'
    body = '''这是一封测试邮件，用于验证您的邮箱SMTP配置是否正确。
如果您收到此邮件，说明邮箱配置正常。
时间：''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    success = utils.send_email(email, subject, body)
    if success:
        flash('测试邮件发送成功，请检查您的邮箱', 'success')
    else:
        flash('测试邮件发送失败，请检查SMTP配置', 'danger')
    return redirect(url_for('admin'))

# Email verification endpoints
@app.route('/send_verification_email', methods=['POST'])
@login_required
def send_verification_email():
    """发送邮箱验证码"""
    user_id = session['user_id']
    if not EMAIL_VERIFICATION_ENABLED:
        return jsonify({'success': False, 'message': '邮箱验证功能未开启'}), 400
    success = utils.send_verification_email(user_id)
    if success:
        return jsonify({'success': True, 'message': '验证码已发送到您的邮箱'})
    else:
        return jsonify({'success': False, 'message': '发送失败，请检查邮箱配置或稍后重试'}), 500

@app.route('/verify_email_code', methods=['POST'])
@login_required
def verify_email_code():
    """验证邮箱验证码"""
    user_id = session['user_id']
    if not EMAIL_VERIFICATION_ENABLED:
        return jsonify({'success': False, 'message': '邮箱验证功能未开启'}), 400
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'success': False, 'message': '缺少验证码'}), 400
    code = data['code'].strip()
    success, message = utils.verify_email_code(user_id, code)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/send_test_email', methods=['POST'])
@login_required
def send_test_email():
    """发送测试邮件（每日限制3条）"""
    user_id = session['user_id']
    if not EMAIL_VERIFICATION_ENABLED:
        return jsonify({'success': False, 'message': '邮箱验证功能未开启'}), 400
    success, message = utils.send_test_email(user_id)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/check_reminders')
def check_reminders():
    """触发提醒检查（需要密钥验证）"""
    secret = request.args.get('secret')
    if secret != REMINDER_CHECK_SECRET:
        return jsonify({'success': False, 'message': '无效的密钥'}), 403
    try:
        utils.check_task_reminders()
        return jsonify({'success': True, 'message': '提醒检查完成'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def start_reminder_scheduler():
    """启动后台线程，每分钟检查一次任务提醒"""
    def reminder_worker():
        import time
        while True:
            try:
                utils.check_task_reminders()
            except Exception as e:
                print(f"提醒检查出错: {e}")
            time.sleep(60)  # 每分钟检查一次

    # 在应用主进程中启动线程（避免在重载器中重复启动）
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.environ.get('WERKZEUG_RUN_MAIN') is None:
        thread = threading.Thread(target=reminder_worker, daemon=True)
        thread.start()
        print(f"提醒检查调度器已启动 (WERKZEUG_RUN_MAIN={os.environ.get('WERKZEUG_RUN_MAIN')})")
    else:
        print(f"提醒检查调度器跳过 (WERKZEUG_RUN_MAIN={os.environ.get('WERKZEUG_RUN_MAIN')})")

if __name__ == '__main__':
    start_reminder_scheduler()
    app.run(debug=True)