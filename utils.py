import json
import os
from datetime import datetime, timedelta
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from config import REMINDER_TIMES

DATA_DIR = 'data'

def load_json(file_name):
    filepath = os.path.join(DATA_DIR, file_name)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(file_name, data):
    filepath = os.path.join(DATA_DIR, file_name)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_by_id(user_id):
    users = load_json('users.json')
    return users.get(str(user_id))

def get_user_by_username(username):
    users = load_json('users.json')
    for uid, user in users.items():
        if user.get('username') == username:
            return user
    return None

def get_user_by_email(email):
    users = load_json('users.json')
    for uid, user in users.items():
        if user.get('email') == email:
            return user
    return None

def create_user(username, password, email, verified=False):
    users = load_json('users.json')
    # Generate new user id
    user_id = 1
    if users:
        user_id = max(map(int, users.keys())) + 1
    users[str(user_id)] = {
        'id': user_id,
        'username': username,
        'password': generate_password_hash(password),  # hashed password
        'email': email,
        'verified': verified,
        'nickname': username,
        'bio': '',
        'avatar': '',
        'created_at': datetime.now().isoformat(),
        'followers': [],
        'following': [],
        'email_verification_code': '',
        'email_verification_sent_at': '',
        'email_verification_attempts': 0,
        'test_email_sent_count': 0,
        'test_email_last_date': ''
    }
    save_json('users.json', users)
    return user_id

def check_password(user, password):
    """验证用户密码是否正确"""
    if not user or 'password' not in user:
        return False
    stored = user['password']
    # 如果存储的密码包含 : 或 $，认为是哈希格式
    if ':' in stored or stored.startswith('$'):
        return check_password_hash(stored, password)
    else:
        # 明文密码，直接比较
        if stored == password:
            # 升级为哈希密码并保存
            hashed = generate_password_hash(password)
            update_user(user['id'], {'password': hashed})
            return True
        else:
            return False

def update_user(user_id, updates):
    users = load_json('users.json')
    if str(user_id) in users:
        users[str(user_id)].update(updates)
        save_json('users.json', users)
        return True
    return False

def determine_task_status(start_time_str):
    """根据开始时间确定任务状态"""
    if not start_time_str:
        return 'pending'
    try:
        # 处理可能的时区信息
        if start_time_str.endswith('Z'):
            start_time_str = start_time_str[:-1] + '+00:00'
        start = datetime.fromisoformat(start_time_str)
        now = datetime.now()
        # 如果 start 有时区信息而 now 没有，将 start 转换为本地 naive datetime
        if start.tzinfo is not None:
            # 转换为本地时区并移除时区信息
            start = start.astimezone(None).replace(tzinfo=None)
        if now < start:
            return 'pending'
        else:
            return 'in_progress'
    except ValueError:
        return 'pending'

def update_task_status_if_needed(task):
    """根据开始时间自动更新任务状态"""
    start_time = task.get('start_time')
    if not start_time:
        return task
    try:
        # 处理可能的时区信息
        if start_time.endswith('Z'):
            start_time = start_time[:-1] + '+00:00'
        start = datetime.fromisoformat(start_time)
        now = datetime.now()
        # 如果 start 有时区信息而 now 没有，将 start 转换为本地 naive datetime
        if start.tzinfo is not None:
            start = start.astimezone(None).replace(tzinfo=None)
        
        if now < start:
            # 当前时间在开始时间之前
            if task.get('status') in ('in_progress', 'completed'):
                # 进行中或已完成的任务应重置为待开始
                update_task(task['id'], {'status': 'pending'})
                task['status'] = 'pending'
        else:
            # 当前时间已到达或超过开始时间
            if task.get('status') == 'pending':
                # 待开始的任务应更新为进行中
                update_task(task['id'], {'status': 'in_progress'})
                task['status'] = 'in_progress'
    except ValueError:
        pass
    return task

def add_task(user_id, task_data):
    tasks = load_json('tasks.json')
    task_id = 1
    if tasks:
        task_id = max(map(int, tasks.keys())) + 1
    task_data['id'] = task_id
    task_data['user_id'] = user_id
    task_data['created_at'] = datetime.now().isoformat()
    # 根据开始时间确定状态
    start_time = task_data.get('start_time')
    task_data['status'] = determine_task_status(start_time)
    task_data['completion_rate'] = 0
    task_data['show_on_homepage'] = task_data.get('show_on_homepage', False)
    # 设置提醒时间，默认为全局配置
    reminder_times = task_data.get('reminder_times')
    if reminder_times is None:
        task_data['reminder_times'] = REMINDER_TIMES
    else:
        # 确保 reminder_times 是整数列表
        if isinstance(reminder_times, str):
            # 尝试解析逗号分隔的字符串
            try:
                task_data['reminder_times'] = [int(t.strip()) for t in reminder_times.split(',') if t.strip()]
            except ValueError:
                task_data['reminder_times'] = REMINDER_TIMES
        elif isinstance(reminder_times, list):
            task_data['reminder_times'] = [int(t) for t in reminder_times if str(t).isdigit()]
        else:
            task_data['reminder_times'] = REMINDER_TIMES
    task_data['sent_reminders'] = []
    tasks[str(task_id)] = task_data
    save_json('tasks.json', tasks)
    return task_id

def get_tasks_by_user(user_id):
    tasks = load_json('tasks.json')
    user_tasks = []
    for tid, task in tasks.items():
        if task.get('user_id') == user_id:
            # 自动更新状态
            task = update_task_status_if_needed(task)
            user_tasks.append(task)
    return user_tasks

def get_task_by_id(task_id):
    tasks = load_json('tasks.json')
    return tasks.get(str(task_id))

def update_task(task_id, updates):
    tasks = load_json('tasks.json')
    if str(task_id) in tasks:
        tasks[str(task_id)].update(updates)
        save_json('tasks.json', tasks)
        return True
    return False

def delete_task(task_id):
    tasks = load_json('tasks.json')
    if str(task_id) in tasks:
        del tasks[str(task_id)]
        save_json('tasks.json', tasks)
        return True
    return False

def add_notification(user_id, title, content, ntype='system'):
    notifications = load_json('notifications.json')
    notif_id = 1
    if notifications:
        notif_id = max(map(int, notifications.keys())) + 1
    notifications[str(notif_id)] = {
        'id': notif_id,
        'user_id': user_id,
        'title': title,
        'content': content,
        'type': ntype,
        'read': False,
        'created_at': datetime.now().isoformat()
    }
    save_json('notifications.json', notifications)
    return notif_id

def get_user_notifications(user_id):
    notifications = load_json('notifications.json')
    user_notifs = []
    for nid, notif in notifications.items():
        if notif.get('user_id') == user_id:
            user_notifs.append(notif)
    user_notifs.sort(key=lambda x: x['created_at'], reverse=True)
    return user_notifs

def get_user_notifications_paginated(user_id, page=1, per_page=20):
    """获取用户通知的分页列表"""
    notifications = load_json('notifications.json')
    user_notifs = []
    for nid, notif in notifications.items():
        if notif.get('user_id') == user_id:
            user_notifs.append(notif)
    user_notifs.sort(key=lambda x: x['created_at'], reverse=True)
    total = len(user_notifs)
    total_pages = (total + per_page - 1) // per_page
    # 确保页码在有效范围内
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    paginated = user_notifs[start:end]
    return {
        'notifications': paginated,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages
    }

def generate_pagination_range(current_page, total_pages, left_edge=2, right_edge=2, left_current=2, right_current=2):
    """
    生成用于分页显示的页码列表，包含省略号占位符。
    返回一个列表，其中整数表示页码，字符串 '...' 表示省略号。
    """
    if total_pages <= 1:
        return []
    pages = []
    # 左侧边缘页码
    for i in range(1, min(left_edge, total_pages) + 1):
        pages.append(i)
    # 当前页左侧的页码
    left_start = max(left_edge + 1, current_page - left_current)
    left_end = current_page - 1
    if left_start <= left_end:
        # 如果左侧边缘与当前页左侧之间有间隙，添加省略号
        if left_start > left_edge + 1:
            pages.append('...')
        for i in range(left_start, left_end + 1):
            pages.append(i)
    # 当前页
    pages.append(current_page)
    # 当前页右侧的页码
    right_start = current_page + 1
    right_end = min(total_pages - right_edge, current_page + right_current)
    if right_start <= right_end:
        for i in range(right_start, right_end + 1):
            pages.append(i)
        # 如果当前页右侧与右侧边缘之间有间隙，添加省略号
        if right_end < total_pages - right_edge:
            pages.append('...')
    # 右侧边缘页码
    for i in range(max(total_pages - right_edge + 1, right_end + 1), total_pages + 1):
        if i not in pages:
            pages.append(i)
    # 去重并保持顺序
    seen = set()
    unique_pages = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            unique_pages.append(p)
    return unique_pages

def mark_notification_read(notif_id):
    notifications = load_json('notifications.json')
    if str(notif_id) in notifications:
        notifications[str(notif_id)]['read'] = True
        save_json('notifications.json', notifications)
        return True
    return False

# Friendship functions
def follow_user(follower_id, followee_id):
    friendships = load_json('friendships.json')
    key = f"{follower_id}_{followee_id}"
    if key not in friendships:
        friendships[key] = {
            'follower_id': follower_id,
            'followee_id': followee_id,
            'created_at': datetime.now().isoformat()
        }
        save_json('friendships.json', friendships)
        # Update user's followers/following lists
        users = load_json('users.json')
        if str(follower_id) in users:
            if followee_id not in users[str(follower_id)].get('following', []):
                users[str(follower_id)]['following'].append(followee_id)
        if str(followee_id) in users:
            if follower_id not in users[str(followee_id)].get('followers', []):
                users[str(followee_id)]['followers'].append(follower_id)
        save_json('users.json', users)
        return True
    return False

def unfollow_user(follower_id, followee_id):
    friendships = load_json('friendships.json')
    key = f"{follower_id}_{followee_id}"
    if key in friendships:
        del friendships[key]
        save_json('friendships.json', friendships)
        # Update user's followers/following lists
        users = load_json('users.json')
        if str(follower_id) in users:
            if followee_id in users[str(follower_id)].get('following', []):
                users[str(follower_id)]['following'].remove(followee_id)
        if str(followee_id) in users:
            if follower_id in users[str(followee_id)].get('followers', []):
                users[str(followee_id)]['followers'].remove(follower_id)
        save_json('users.json', users)
        return True
    return False

def are_mutual_followers(user_id1, user_id2):
    friendships = load_json('friendships.json')
    key1 = f"{user_id1}_{user_id2}"
    key2 = f"{user_id2}_{user_id1}"
    return key1 in friendships and key2 in friendships

def get_following(user_id):
    """获取用户关注的用户列表（关注对象）"""
    users = load_json('users.json')
    user = users.get(str(user_id))
    if not user:
        return []
    following_ids = user.get('following', [])
    following = []
    for uid in following_ids:
        u = users.get(str(uid))
        if u:
            following.append(u)
    return following

def get_followers(user_id):
    """获取用户的粉丝列表"""
    users = load_json('users.json')
    user = users.get(str(user_id))
    if not user:
        return []
    follower_ids = user.get('followers', [])
    followers = []
    for uid in follower_ids:
        u = users.get(str(uid))
        if u:
            followers.append(u)
    return followers

def search_users(query, current_user_id):
    """根据关键词搜索用户，返回分类结果"""
    users = load_json('users.json')
    current_user = users.get(str(current_user_id))
    following_ids = set(current_user.get('following', [])) if current_user else set()
    follower_ids = set(current_user.get('followers', [])) if current_user else set()
    
    results = []
    query_lower = query.lower()
    for uid, user in users.items():
        if uid == str(current_user_id):
            continue  # 排除自己
        name = user.get('nickname') or user.get('username', '')
        if query_lower in name.lower() or query_lower in user.get('username', '').lower():
            # 判断关系
            is_following = int(uid) in following_ids
            is_follower = int(uid) in follower_ids
            category = 'all'
            if is_following and is_follower:
                category = 'mutual'
            elif is_following:
                category = 'following'
            elif is_follower:
                category = 'followers'
            results.append({
                'id': int(uid),
                'username': user.get('username'),
                'nickname': user.get('nickname'),
                'avatar': user.get('avatar'),
                'category': category
            })
    return results

def is_following(follower_id, followee_id):
    """检查 follower_id 是否关注了 followee_id"""
    users = load_json('users.json')
    follower = users.get(str(follower_id))
    if not follower:
        return False
    return followee_id in follower.get('following', [])

# Message functions
def send_message(sender_id, receiver_id, content):
    messages = load_json('messages.json')
    msg_id = 1
    if messages:
        msg_id = max(map(int, messages.keys())) + 1
    messages[str(msg_id)] = {
        'id': msg_id,
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content,
        'read': False,
        'created_at': datetime.now().isoformat()
    }
    save_json('messages.json', messages)
    return msg_id

def get_messages_between(user1_id, user2_id, limit=None, offset=0, reverse=True):
    """获取两个用户之间的消息列表，支持分页和排序"""
    messages = load_json('messages.json')
    conversation = []
    for mid, msg in messages.items():
        if (msg['sender_id'] == user1_id and msg['receiver_id'] == user2_id) or \
           (msg['sender_id'] == user2_id and msg['receiver_id'] == user1_id):
            conversation.append(msg)
    # Sort by time
    conversation.sort(key=lambda x: x['created_at'], reverse=reverse)
    # Apply pagination if limit is specified
    if limit is not None:
        start = offset
        end = offset + limit
        conversation = conversation[start:end]
    return conversation

def count_messages_today(sender_id, receiver_id):
    today = datetime.now().date()
    messages = load_json('messages.json')
    count = 0
    for mid, msg in messages.items():
        if msg['sender_id'] == sender_id and msg['receiver_id'] == receiver_id:
            msg_date = datetime.fromisoformat(msg['created_at']).date()
            if msg_date == today:
                count += 1
    return count

# Post functions
def create_post(user_id, content, images=None):
    posts = load_json('posts.json')
    post_id = 1
    if posts:
        post_id = max(map(int, posts.keys())) + 1
    posts[str(post_id)] = {
        'id': post_id,
        'user_id': user_id,
        'content': content,
        'images': images or [],
        'likes': [],
        'comments': [],
        'created_at': datetime.now().isoformat()
    }
    save_json('posts.json', posts)
    return post_id

def get_posts_by_user(user_id):
    posts = load_json('posts.json')
    user_posts = []
    for pid, post in posts.items():
        if post.get('user_id') == user_id:
            user_posts.append(post)
    return user_posts

def get_all_posts():
    posts = load_json('posts.json')
    enriched = []
    for post in posts.values():
        post_copy = post.copy()
        user = get_user_by_id(post['user_id'])
        if user:
            post_copy['user_name'] = user.get('nickname') or user.get('username')
            post_copy['user_avatar'] = user.get('avatar')
        else:
            post_copy['user_name'] = '未知用户'
            post_copy['user_avatar'] = ''
        # 为评论添加用户信息
        comments_with_user = []
        for comment in post_copy.get('comments', []):
            comment_copy = comment.copy()
            comment_user = get_user_by_id(comment['user_id'])
            if comment_user:
                comment_copy['user_name'] = comment_user.get('nickname') or comment_user.get('username')
                comment_copy['user_avatar'] = comment_user.get('avatar')
            else:
                comment_copy['user_name'] = '未知用户'
                comment_copy['user_avatar'] = ''
            comments_with_user.append(comment_copy)
        post_copy['comments'] = comments_with_user
        enriched.append(post_copy)
    return enriched

def get_post_by_id(post_id):
    posts = load_json('posts.json')
    return posts.get(str(post_id))

def update_post(post_id, updates):
    posts = load_json('posts.json')
    if str(post_id) in posts:
        posts[str(post_id)].update(updates)
        save_json('posts.json', posts)
        return True
    return False

def delete_post(post_id):
    posts = load_json('posts.json')
    if str(post_id) in posts:
        del posts[str(post_id)]
        save_json('posts.json', posts)
        return True
    return False

def toggle_like(post_id, user_id):
    """切换用户对帖子的点赞状态（如果已点赞则取消，否则点赞）"""
    posts = load_json('posts.json')
    if str(post_id) not in posts:
        return False
    post = posts[str(post_id)]
    likes = post.get('likes', [])
    if user_id in likes:
        likes.remove(user_id)
    else:
        likes.append(user_id)
    post['likes'] = likes
    save_json('posts.json', posts)
    return True

def add_comment(post_id, user_id, content):
    """为帖子添加评论"""
    posts = load_json('posts.json')
    if str(post_id) not in posts:
        return False
    post = posts[str(post_id)]
    comments = post.get('comments', [])
    # 生成新评论ID
    comment_id = 1
    if comments:
        comment_id = max(c.get('id', 0) for c in comments) + 1
    new_comment = {
        'id': comment_id,
        'user_id': user_id,
        'content': content,
        'likes': [],
        'created_at': datetime.now().isoformat()
    }
    comments.append(new_comment)
    post['comments'] = comments
    save_json('posts.json', posts)
    return comment_id

def toggle_comment_like(post_id, comment_id, user_id):
    """切换用户对评论的点赞状态"""
    posts = load_json('posts.json')
    if str(post_id) not in posts:
        return False
    post = posts[str(post_id)]
    comments = post.get('comments', [])
    for comment in comments:
        if comment['id'] == comment_id:
            likes = comment.get('likes', [])
            if user_id in likes:
                likes.remove(user_id)
            else:
                likes.append(user_id)
            comment['likes'] = likes
            save_json('posts.json', posts)
            return True
    return False

def delete_comment(post_id, comment_id, user_id):
    """删除评论（仅评论发布者或帖子所有者可删除）"""
    posts = load_json('posts.json')
    if str(post_id) not in posts:
        return False
    post = posts[str(post_id)]
    comments = post.get('comments', [])
    for i, comment in enumerate(comments):
        if comment['id'] == comment_id:
            # 检查权限：评论发布者或帖子所有者
            if comment['user_id'] == user_id or post['user_id'] == user_id:
                del comments[i]
                post['comments'] = comments
                save_json('posts.json', posts)
                return True
            else:
                return False
    return False

def check_task_reminders():
    """检查即将开始的任务，并发送通知和邮件提醒"""
    tasks = load_json('tasks.json')
    now = datetime.now()
    print(f"[提醒检查] 开始检查，当前时间: {now}")
    for tid, task in tasks.items():
        if not task.get('start_time'):
            continue
        try:
            start = datetime.fromisoformat(task['start_time'])
        except ValueError:
            continue
        # 计算距离开始还有多少分钟
        delta = start - now
        minutes = delta.total_seconds() / 60
        print(f"[提醒检查] 任务 {task['name']} 开始时间 {start}，距离开始 {minutes:.1f} 分钟")
        
        # 获取提醒时间列表，如果没有则使用全局配置
        reminder_times = task.get('reminder_times', REMINDER_TIMES)
        if not isinstance(reminder_times, list):
            # 如果格式不对，回退到默认
            reminder_times = REMINDER_TIMES
        print(f"[提醒检查] 提醒时间列表: {reminder_times}")
        
        user_id = task['user_id']
        user = get_user_by_id(user_id)
        user_email = user.get('email') if user else None
        
        # 获取已发送提醒列表
        sent_reminders = task.get('sent_reminders', [])
        # 检查每个提醒时间
        for remind_minutes in reminder_times:
            if remind_minutes <= 0:
                continue
            # 检查当前分钟是否在提醒时间窗口内（考虑到检查可能不是精确的每分钟）
            if remind_minutes - 2 <= minutes <= remind_minutes + 2:
                # 检查是否已发送过该提醒
                if remind_minutes in sent_reminders:
                    print(f"[提醒检查] 提醒已发送过，跳过: 任务 {task['name']} 在 {remind_minutes} 分钟后开始")
                    continue
                print(f"[提醒检查] 触发提醒！任务 {task['name']} 将在 {remind_minutes} 分钟后开始")
                # 发送通知
                add_notification(user_id, '任务即将开始',
                                 f"任务「{task['name']}」将在{remind_minutes}分钟后开始。",
                                 'reminder')
                # 发送邮件
                if user_email:
                    subject = f'Smart To-Do 任务提醒：{task["name"]}'
                    body = f'''您的任务「{task['name']}」将在{remind_minutes}分钟后开始。
开始时间：{task['start_time']}
地点：{task.get('location', '未设置')}
备注：{task.get('notes', '无')}
请做好准备！
'''
                    try:
                        send_email(user_email, subject, body)
                        print(f"[提醒检查] 提醒邮件已发送至 {user_email}")
                    except Exception as e:
                        print(f"[提醒检查] 发送提醒邮件失败: {e}")
                else:
                    print(f"[提醒检查] 用户无邮箱，跳过邮件发送")
                # 记录已发送提醒
                sent_reminders.append(remind_minutes)
                update_task(int(tid), {'sent_reminders': sent_reminders})
                break  # 只触发一个提醒（避免同一任务多个提醒同时触发）
        
        # 如果任务已经开始，自动更新状态为进行中
        if minutes <= 0 and task.get('status') == 'pending':
            print(f"[提醒检查] 任务 {task['name']} 已开始，更新状态为进行中")
            update_task(int(tid), {'status': 'in_progress'})

def get_user_stats(user_id, days=7):
    """获取用户统计数据"""
    tasks = get_tasks_by_user(user_id)
    now = datetime.now()
    
    # 基础统计
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get('status') == 'completed')
    in_progress = sum(1 for t in tasks if t.get('status') == 'in_progress')
    pending = sum(1 for t in tasks if t.get('status') == 'pending')
    
    # 计算平均完成率，确保完成率为数字
    completion_rates = []
    for t in tasks:
        rate = t.get('completion_rate', 0)
        if isinstance(rate, (int, float)):
            completion_rates.append(rate)
        elif isinstance(rate, str):
            try:
                completion_rates.append(float(rate))
            except ValueError:
                pass
    avg_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0
    
    # 按日期统计完成率
    date_rates = {}
    for task in tasks:
        if task.get('created_at'):
            try:
                date = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00')).date()
            except ValueError:
                continue
            rate = task.get('completion_rate', 0)
            if isinstance(rate, str):
                try:
                    rate = float(rate)
                except ValueError:
                    rate = 0
            if date not in date_rates:
                date_rates[date] = []
            date_rates[date].append(rate)
    
    # 计算每天的平均完成率
    dates = []
    rates = []
    for i in range(days):
        day = now.date() - timedelta(days=i)
        if day in date_rates and date_rates[day]:
            avg = sum(date_rates[day]) / len(date_rates[day])
        else:
            avg = None
        dates.append(day.isoformat())
        rates.append(avg if avg is not None else 0)
    
    dates.reverse()
    rates.reverse()
    
    return {
        'total_tasks': total,
        'completed_tasks': completed,
        'in_progress_tasks': in_progress,
        'pending_tasks': pending,
        'avg_completion_rate': round(avg_rate, 1),
        'dates': dates,
        'rates': rates,
    }

def load_config():
    """加载配置文件"""
    filepath = os.path.join(DATA_DIR, 'config.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """保存配置文件"""
    filepath = os.path.join(DATA_DIR, 'config.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_deepseek_config():
    """获取DeepSeek API配置"""
    config = load_config()
    api_key = config.get('deepseek_api_key', '')
    api_url = config.get('deepseek_api_url', 'https://api.deepseek.com/chat/completions')
    ai_enabled = config.get('ai_enabled', False)
    return api_key, api_url, ai_enabled

def update_deepseek_config(api_key=None, api_url=None, ai_enabled=None):
    """更新DeepSeek API配置"""
    config = load_config()
    if api_key is not None:
        config['deepseek_api_key'] = api_key
    if api_url is not None:
        config['deepseek_api_url'] = api_url
    if ai_enabled is not None:
        config['ai_enabled'] = ai_enabled
    save_config(config)

def parse_task_with_ai(text):
    """使用DeepSeek API解析自然语言任务文本，返回结构化数据"""
    api_key, api_url, ai_enabled = get_deepseek_config()
    if not api_key or not ai_enabled:
        return None
    import requests
    import json
    from datetime import datetime
    # 获取当前时间（北京时间 UTC+8）
    now = datetime.now()
    current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    # 构造提示词
    prompt = f"""请从以下文本中提取任务信息，并以JSON格式返回。字段包括：name（任务名称）, description（任务描述）, start_time（开始时间，ISO格式，如2025-12-24T15:00:00），如果时间是模糊的（例如“明天下午3点”、“下周一上午”），请基于当前日期时间推断出具体的日期时间，并以ISO格式表示（假设时区为UTC+8）。如果无法推断，请留空字符串。, location（地点）, duration（预计用时，单位分钟）, notes（备注）。如果某个字段无法确定，请留空字符串。
文本：{text}

请只返回JSON对象，不要有其他解释。"""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': f'你是一个任务信息提取助手，请准确提取任务信息并返回JSON。当前日期时间是：{current_time_str}（北京时间UTC+8）。请将文本中的模糊时间转换为基于当前日期时间的ISO格式（YYYY-MM-DDTHH:MM:SS）。如果文本中没有提到时间，请留空。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        # 尝试解析JSON
        # 有时响应可能包含markdown代码块，需要清理
        if content.startswith('```json'):
            content = content[7:-3]  # 去除 ```json 和 ```
        elif content.startswith('```'):
            content = content[3:-3]
        parsed = json.loads(content)
        # 确保字段存在
        task_data = {
            'name': parsed.get('name', ''),
            'description': parsed.get('description', ''),
            'start_time': parsed.get('start_time', ''),
            'location': parsed.get('location', ''),
            'duration': parsed.get('duration', ''),
            'notes': parsed.get('notes', '')
        }
        return task_data
    except Exception as e:
        print(f"AI解析错误: {e}")
        return None

# Email verification functions
def generate_verification_code():
    """生成6位数字验证码"""
    import random
    return ''.join(random.choices('0123456789', k=6))

def get_email_config():
    """获取邮箱配置（SMTP设置）"""
    config = load_config()
    return {
        'mail_server': config.get('mail_server', 'smtp.gmail.com'),
        'mail_port': config.get('mail_port', 587),
        'mail_use_tls': config.get('mail_use_tls', True),
        'mail_username': config.get('mail_username', ''),
        'mail_password': config.get('mail_password', ''),
        'mail_default_sender': config.get('mail_default_sender', 'noreply@smarttodo.com')
    }

def update_email_config(mail_server=None, mail_port=None, mail_use_tls=None,
                        mail_username=None, mail_password=None, mail_default_sender=None):
    """更新邮箱配置"""
    config = load_config()
    if mail_server is not None:
        config['mail_server'] = mail_server
    if mail_port is not None:
        config['mail_port'] = mail_port
    if mail_use_tls is not None:
        config['mail_use_tls'] = mail_use_tls
    if mail_username is not None:
        config['mail_username'] = mail_username
    if mail_password is not None:
        config['mail_password'] = mail_password
    if mail_default_sender is not None:
        config['mail_default_sender'] = mail_default_sender
    save_config(config)

def send_email(to_email, subject, body):
    """发送邮件"""
    config = get_email_config()
    mail_server = config['mail_server']
    mail_port = config['mail_port']
    mail_use_tls = config['mail_use_tls']
    mail_username = config['mail_username']
    mail_password = config['mail_password']
    mail_default_sender = config['mail_default_sender']
    
    if not mail_username or not mail_password:
        raise ValueError('邮箱用户名或密码未配置，无法发送邮件')
    
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = mail_default_sender
    msg['To'] = to_email
    
    try:
        print(f"尝试发送邮件到 {to_email}，使用服务器 {mail_server}:{mail_port}，发件人 {mail_default_sender}")
        if mail_port == 465:
            print("使用 SSL (SMTP_SSL) 连接")
            with smtplib.SMTP_SSL(mail_server, mail_port, timeout=30) as server:
                server.ehlo()
                print(f"登录用户 {mail_username}")
                server.login(mail_username, mail_password)
                print("登录成功，正在发送邮件...")
                server.sendmail(mail_default_sender, [to_email], msg.as_string())
                print("邮件发送完成")
        else:
            with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
                server.ehlo()
                if mail_use_tls:
                    print("启用 TLS...")
                    server.starttls()
                    server.ehlo()
                print(f"登录用户 {mail_username}")
                server.login(mail_username, mail_password)
                print("登录成功，正在发送邮件...")
                server.sendmail(mail_default_sender, [to_email], msg.as_string())
                print("邮件发送完成")
        return True
    except Exception as e:
        print(f"发送邮件失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_verification_email(user_id):
    """向用户发送验证码邮件"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    email = user.get('email')
    if not email:
        return False
    
    # 生成验证码
    code = generate_verification_code()
    # 更新用户记录
    update_user(user_id, {
        'email_verification_code': code,
        'email_verification_sent_at': datetime.now().isoformat(),
        'email_verification_attempts': 0
    })
    
    subject = 'Smart To-Do 邮箱验证码'
    body = f'''您的邮箱验证码是：{code}，请在10分钟内完成验证。
如果您未请求此验证码，请忽略此邮件。'''
    
    success = send_email(email, subject, body)
    if success:
        return True
    else:
        # 发送失败，清除验证码
        update_user(user_id, {
            'email_verification_code': '',
            'email_verification_sent_at': ''
        })
        return False

def verify_email_code(user_id, code):
    """验证邮箱验证码"""
    user = get_user_by_id(user_id)
    if not user:
        return False, '用户不存在'
    stored_code = user.get('email_verification_code', '')
    sent_at_str = user.get('email_verification_sent_at', '')
    if not stored_code or not sent_at_str:
        return False, '未发送验证码或验证码已过期'
    
    # 检查过期时间（10分钟）
    try:
        sent_at = datetime.fromisoformat(sent_at_str)
        if datetime.now() - sent_at > timedelta(minutes=10):
            return False, '验证码已过期'
    except ValueError:
        return False, '验证码时间格式错误'
    
    # 检查尝试次数
    attempts = user.get('email_verification_attempts', 0)
    if attempts >= 5:
        return False, '尝试次数过多，请重新发送验证码'
    
    # 验证码匹配
    if stored_code == code:
        # 验证成功，更新用户验证状态
        update_user(user_id, {
            'verified': True,
            'email_verification_code': '',
            'email_verification_sent_at': '',
            'email_verification_attempts': 0
        })
        return True, '验证成功'
    else:
        # 增加尝试次数
        update_user(user_id, {
            'email_verification_attempts': attempts + 1
        })
        return False, '验证码错误'

def can_send_test_email(user_id):
    """检查用户今日是否还可以发送测试邮件（每天最多3条）"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    today = datetime.now().date()
    last_date_str = user.get('test_email_last_date', '')
    count = user.get('test_email_sent_count', 0)
    
    # 如果最后发送日期不是今天，重置计数
    if last_date_str:
        try:
            last_date = datetime.fromisoformat(last_date_str).date()
        except ValueError:
            last_date = None
    else:
        last_date = None
    
    if last_date != today:
        # 重置计数
        update_user(user_id, {
            'test_email_sent_count': 0,
            'test_email_last_date': today.isoformat()
        })
        return True
    else:
        # 检查是否超过限制
        return count < 3

def get_test_email_quota(user_id):
    """获取用户今日测试邮件的配额信息"""
    user = get_user_by_id(user_id)
    if not user:
        return {'sent': 0, 'limit': 3, 'remaining': 0, 'allowed': False}
    today = datetime.now().date()
    last_date_str = user.get('test_email_last_date', '')
    count = user.get('test_email_sent_count', 0)
    
    # 如果最后发送日期不是今天，重置计数（仅查询，不修改）
    if last_date_str:
        try:
            last_date = datetime.fromisoformat(last_date_str).date()
        except ValueError:
            last_date = None
    else:
        last_date = None
    
    if last_date != today:
        # 日期不是今天，剩余次数为限额
        remaining = 3
        sent = 0
    else:
        remaining = max(0, 3 - count)
        sent = count
    allowed = remaining > 0
    return {
        'sent': sent,
        'limit': 3,
        'remaining': remaining,
        'allowed': allowed
    }

def record_test_email_sent(user_id):
    """记录测试邮件发送"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    today = datetime.now().date()
    count = user.get('test_email_sent_count', 0) + 1
    update_user(user_id, {
        'test_email_sent_count': count,
        'test_email_last_date': today.isoformat()
    })
    return True

def send_test_email(user_id):
    """发送测试邮件给用户"""
    if not can_send_test_email(user_id):
        return False, '今日测试邮件发送次数已达上限（每天最多3条）'
    
    user = get_user_by_id(user_id)
    if not user:
        return False, '用户不存在'
    email = user.get('email')
    if not email:
        return False, '用户未绑定邮箱'
    
    subject = 'Smart To-Do 测试邮件'
    body = '''这是一封测试邮件，用于验证您的邮箱配置是否正确。
如果您收到此邮件，说明邮箱配置正常。
时间：''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    success = send_email(email, subject, body)
    if success:
        record_test_email_sent(user_id)
        return True, '测试邮件发送成功'
    else:
        return False, '发送失败，请检查邮箱配置'