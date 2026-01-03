# Smart To-Do 网站

一个智能的待办事项管理网站，具有任务管理、通知、私信、社区分享、日历视图和数据统计功能。

## 功能特性

- **用户认证**: 注册、登录、邮箱验证（可开关）
- **邮箱测试**: 用户可在仪表盘发送测试邮件验证邮箱配置，每日限3条
- **任务管理**: 添加、编辑、删除任务，设置开始时间、地点、完成率等
- **任务状态**: 待开始、进行中、已完成
- **提醒通知**: 任务开始前30分钟和5分钟发送站内通知（邮件待实现）
- **私信系统**: 用户间私信，非互关用户每日限10条
- **社区分享**: 发帖、图片上传、点赞评论
- **个人主页**: 显示用户信息、粉丝、关注、任务和帖子
- **日历视图**: 可视化查看任务日程，点击日期显示任务
- **数据统计**: 任务完成率折线图、状态分布饼图、时间段统计
- **管理员后台**: 管理用户、开关邮箱验证、发送系统通知

## 技术栈

- 后端: Python Flask
- 前端: HTML/CSS/JavaScript, Bootstrap 5, Chart.js, FullCalendar
- 数据存储: JSON 文件（用户、任务、消息、帖子等）
- 依赖: 见 requirements.txt

## 安装与运行

### 1. 克隆或下载项目

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# 或 source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 3. 配置

编辑 `config.py` 文件，设置邮箱服务器（如需发送邮件）和其他参数。

默认配置：
- `SECRET_KEY`: 建议修改
- `EMAIL_VERIFICATION_ENABLED`: False（关闭邮箱验证）
- `MAIL_*`: 邮箱相关配置，留空则不发邮件

### 4. 初始化数据

数据目录 `data/` 会自动创建，并包含空的 JSON 文件。

### 5. 运行开发服务器

```bash
python app.py
```

访问 http://localhost:5000

### 6. 管理员账号

第一个注册的用户 ID 为 1，自动成为管理员。访问 `/admin` 进入后台。

## 项目结构

```
.
├── app.py              # 主应用
├── config.py           # 配置文件
├── utils.py            # 数据操作工具函数
├── requirements.txt    # 依赖列表
├── data/               # JSON 数据文件
│   ├── users.json
│   ├── tasks.json
│   ├── messages.json
│   ├── notifications.json
│   ├── posts.json
│   └── friendships.json
├── static/             # 静态资源
│   ├── style.css
│   ├── script.js
│   └── images/
└── templates/          # HTML 模板
    ├── layout.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── tasks.html
    ├── add_task.html
    ├── task_detail.html
    ├── edit_task.html
    ├── notifications.html
    ├── messages.html
    ├── profile.html
    ├── community.html
    ├── calendar.html
    ├── stats.html
    └── admin.html
```

## 使用说明

1. **注册新账号**：访问首页点击注册，填写用户名、邮箱、密码。
2. **登录**：使用用户名或邮箱登录。
3. **添加任务**：在“任务”页面点击“添加任务”，填写详细信息。
4. **查看日历**：点击导航栏“日历”，查看有任务的日期（蓝色圆点）。
5. **私信**：在用户主页点击“发送私信”，或在“私信”页面选择联系人。
6. **社区发帖**：在“社区”页面编写帖子，可上传图片。
7. **数据统计**：查看“统计”页面了解任务完成情况。
8. **通知**：点击右上角铃铛图标查看系统通知。

## 注意事项

- 用户密码明文存储（仅演示用途，生产环境请加密）。
- 邮箱验证功能默认关闭，如需开启请在管理员后台切换。
- 任务提醒仅生成站内通知，如需邮件需配置 SMTP。
- 所有数据保存在 JSON 文件中，适合小规模使用。

## 部署到生产环境

1. 使用 WSGI 服务器（如 Gunicorn + Nginx）
2. 设置 `DEBUG = False`
3. 修改 `SECRET_KEY` 为强随机字符串
4. 配置真正的邮箱服务器
5. 考虑将 JSON 数据迁移到数据库（如 SQLite、PostgreSQL）

## 许可证

MIT