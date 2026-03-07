/**
 * Team dashboard calendar: prev/next month, day click to show day detail (assignments + announcements).
 * Uses CALENDAR_DATA from the page (assignments, announcements, today).
 */
(function() {
    var DATA = window.CALENDAR_DATA;
    if (!DATA) return;

    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    var WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    var state = {
        year: parseInt(DATA.today.slice(0, 4), 10),
        month: parseInt(DATA.today.slice(5, 7), 10),
        view: 'grid' // 'grid' | 'day'
    };

    function daysInMonth(y, m) {
        return new Date(y, m, 0).getDate();
    }

    function firstWeekday(y, m) {
        return (new Date(y, m - 1, 1).getDay() + 6) % 7;
    }

    function dateKey(y, m, d) {
        var sy = String(y);
        var sm = m < 10 ? '0' + m : String(m);
        var sd = d < 10 ? '0' + d : String(d);
        return sy + '-' + sm + '-' + sd;
    }

    function getActivityDays(y, m) {
        var key = y + '-' + m;
        var days = {};
        DATA.assignments.forEach(function(a) {
            if (a.due_date) {
                var parts = a.due_date.split('-');
                if (parseInt(parts[0], 10) === y && parseInt(parts[1], 10) === m) {
                    var day = parseInt(parts[2], 10);
                    days[day] = true;
                }
            }
        });
        DATA.announcements.forEach(function(ann) {
            if (ann.created_at) {
                var d = ann.created_at.slice(0, 10);
                var parts = d.split('-');
                if (parseInt(parts[0], 10) === y && parseInt(parts[1], 10) === m) {
                    var day = parseInt(parts[2], 10);
                    days[day] = true;
                }
            }
        });
        return days;
    }

    function isToday(y, m, d) {
        return dateKey(y, m, d) === DATA.today;
    }

    function renderGrid() {
        var y = state.year;
        var m = state.month;
        var first = firstWeekday(y, m);
        var daysTotal = daysInMonth(y, m);
        var activityDays = getActivityDays(y, m);

        var todayY = parseInt(DATA.today.slice(0, 4), 10);
        var todayM = parseInt(DATA.today.slice(5, 7), 10);
        var todayD = parseInt(DATA.today.slice(8, 10), 10);

        var html = '';
        for (var i = 0; i < first; i++) {
            html += '<div class="calendar-day calendar-day-empty"></div>';
        }
        for (var d = 1; d <= daysTotal; d++) {
            var isTodayCell = (y === todayY && m === todayM && d === todayD);
            var hasActivity = !!activityDays[d];
            var classes = 'calendar-day';
            if (isTodayCell) classes += ' calendar-day-today';
            if (hasActivity) classes += ' calendar-day-has-activity';
            html += '<div class="calendar-day ' + classes + '" data-year="' + y + '" data-month="' + m + '" data-day="' + d + '">';
            html += '<span class="calendar-day-num">' + d + '</span>';
            if (hasActivity) html += '<span class="calendar-dot"></span>';
            html += '</div>';
        }

        var titleEl = document.getElementById('calendar-month-title');
        if (titleEl) titleEl.textContent = MONTHS[m - 1] + ' ' + y;

        var container = document.getElementById('calendar-days');
        if (container) {
            container.innerHTML = html;
            container.querySelectorAll('.calendar-day').forEach(function(cell) {
                if (cell.classList.contains('calendar-day-empty')) return;
                cell.addEventListener('click', function() {
                    var yr = parseInt(cell.getAttribute('data-year'), 10);
                    var mo = parseInt(cell.getAttribute('data-month'), 10);
                    var da = parseInt(cell.getAttribute('data-day'), 10);
                    showDayView(yr, mo, da);
                });
            });
        }
    }

    function showDayView(y, m, d) {
        state.view = 'day';
        state.dayYear = y;
        state.dayMonth = m;
        state.dayDay = d;

        var key = dateKey(y, m, d);
        var dateLabel = MONTHS[m - 1] + ' ' + d + ', ' + y;

        var assignList = DATA.assignments.filter(function(a) {
            return a.due_date === key;
        });
        var annList = DATA.announcements.filter(function(ann) {
            return ann.created_at && ann.created_at.slice(0, 10) === key;
        });

        var titleEl = document.getElementById('calendar-day-view-title');
        if (titleEl) titleEl.textContent = dateLabel;

        var assignEl = document.getElementById('calendar-day-assignments');
        if (assignEl) {
            if (assignList.length === 0) {
                assignEl.innerHTML = '<p class="empty-state empty-state-inline">No assignments due this day.</p>';
            } else {
                assignEl.innerHTML = '<h3 class="calendar-day-subheading">Assignments due</h3>' + assignList.map(function(a) {
                    var desc = a.description ? '<p class="assignment-desc">' + escapeHtml(a.description) + '</p>' : '';
                    var due = a.due_display ? '<p class="assignment-due">' + escapeHtml(a.due_display) + '</p>' : '';
                    return '<div class="assignment-card">' +
                        '<p class="assignment-title">' + escapeHtml(a.title) + '</p>' + desc + due +
                        '</div>';
                }).join('');
            }
        }

        var annEl = document.getElementById('calendar-day-announcements');
        if (annEl) {
            if (annList.length === 0) {
                annEl.innerHTML = '<p class="empty-state empty-state-inline">No announcements this day.</p>';
            } else {
                annEl.innerHTML = '<h3 class="calendar-day-subheading">Announcements</h3>' + annList.map(function(ann) {
                    var time = formatAnnouncementTime(ann.created_at);
                    return '<div class="announcement-card">' +
                        '<p class="announcement-content">' + escapeHtml(ann.content) + '</p>' +
                        '<p class="announcement-meta">' + escapeHtml(time) + '</p>' +
                        '</div>';
                }).join('');
            }
        }

        document.getElementById('calendar-view').classList.add('hidden');
        document.getElementById('calendar-day-view').classList.remove('hidden');
    }

    function formatAnnouncementTime(iso) {
        if (!iso) return '';
        var d = new Date(iso);
        var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear() + ' at ' + (d.getHours() < 10 ? '0' : '') + d.getHours() + ':' + (d.getMinutes() < 10 ? '0' : '') + d.getMinutes();
    }

    function escapeHtml(s) {
        if (!s) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function backToCalendar() {
        state.view = 'grid';
        document.getElementById('calendar-view').classList.remove('hidden');
        document.getElementById('calendar-day-view').classList.add('hidden');
    }

    function init() {
        renderGrid();

        var prevBtn = document.getElementById('calendar-prev');
        var nextBtn = document.getElementById('calendar-next');
        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                state.month--;
                if (state.month < 1) { state.month = 12; state.year--; }
                renderGrid();
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                state.month++;
                if (state.month > 12) { state.month = 1; state.year++; }
                renderGrid();
            });
        }

        var backBtn = document.getElementById('back-to-calendar');
        if (backBtn) backBtn.addEventListener('click', backToCalendar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
