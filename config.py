# Flask configuration
SECRET_KEY = 'your-secret-key-change-this'
DEBUG = True

# Email settings (for email verification and notifications)
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = ''
MAIL_PASSWORD = ''
MAIL_DEFAULT_SENDER = 'noreply@smarttodo.com'

# Feature flags
EMAIL_VERIFICATION_ENABLED = False  # Admin can toggle this

# Limits
MAX_MESSAGES_PER_DAY_UNFOLLOWED = 10

# Task reminder times (minutes before start)
REMINDER_TIMES = [30, 5]

# Secret key for reminder check endpoint (optional)
REMINDER_CHECK_SECRET = 'change_this_secret'