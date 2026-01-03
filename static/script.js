// Common JavaScript for Smart To-Do

$(document).ready(function() {
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);


    // Toggle task completion
    $('.task-complete-toggle').change(function() {
        const taskId = $(this).data('task-id');
        const completed = $(this).is(':checked');
        $.post(`/tasks/${taskId}/toggle`, { completed: completed }, function(response) {
            if (response.success) {
                location.reload();
            }
        });
    });

    // Mark notification as read when clicked
    $('.notification-item').click(function() {
        const notifId = $(this).data('notif-id');
        $.post(`/notifications/${notifId}/read`, function(response) {
            if (response.success) {
                $(this).removeClass('list-group-item-primary');
            }
        });
    });

    // Send message with Enter key (Ctrl+Enter for new line)
    $('#message-input').keydown(function(e) {
        if (e.keyCode === 13 && !e.ctrlKey) {
            e.preventDefault();
            $('#send-message').click();
        }
    });

    // Calendar day click
    $('.calendar-day').click(function() {
        const date = $(this).data('date');
        $('#tasks-modal .modal-title').text('任务 - ' + date);
        // Fetch tasks for this date via AJAX
        $.get(`/api/tasks?date=${date}`, function(tasks) {
            const list = $('#tasks-list');
            list.empty();
            if (tasks.length) {
                tasks.forEach(task => {
                    list.append(`<li class="list-group-item">${task.name}</li>`);
                });
            } else {
                list.append('<li class="list-group-item text-muted">当天没有任务</li>');
            }
        });
        $('#tasks-modal').modal('show');
    });

    // Update current time every second
    function updateCurrentTime() {
        const now = new Date();
        const formatted = now.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        $('#current-time').text('当前时间: ' + formatted);
    }
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);

    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();

    // Initialize popovers
    $('[data-bs-toggle="popover"]').popover();
});

// Utility function to format date
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Utility function to time ago
function timeAgo(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    if (seconds < 60) return '刚刚';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}天前`;
    const months = Math.floor(days / 30);
    if (months < 12) return `${months}个月前`;
    const years = Math.floor(months / 12);
    return `${years}年前`;
}

// Register as global filters for Jinja (if using inline JS)
if (typeof window !== 'undefined') {
    window.timeAgo = timeAgo;
    window.formatDate = formatDate;
}