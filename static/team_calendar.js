/**
 * Team dashboard calendar: prev/next month, day click to show day detail (assignments + announcements).
 * Uses CALENDAR_DATA from the page (assignments, announcements, today).
 */
(function() {
    var DATA = window.CALENDAR_DATA;
    if (!DATA) return;

    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    var state = {
        year: parseInt(DATA.today.slice(0, 4), 10),
        month: parseInt(DATA.today.slice(5, 7), 10),
        view: 'grid' // 'grid' | 'day'
    };

    var todayY = parseInt(DATA.today.slice(0, 4), 10);
    var todayM = parseInt(DATA.today.slice(5, 7), 10);
    var todayD = parseInt(DATA.today.slice(8, 10), 10);

    function daysInMonth(y, m) {
        return new Date(y, m, 0).getDate();
    }

    function firstWeekday(y, m) {
        // Sunday-based: 0 = Sunday, 1 = Monday, ... 6 = Saturday
        return new Date(y, m - 1, 1).getDay();
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

            var key = dateKey(y, m, d);
            var preview = null;
            for (var iAssign = 0; iAssign < DATA.assignments.length; iAssign++) {
                var a = DATA.assignments[iAssign];
                if (a.due_date === key) {
                    preview = a.title || '';
                    break;
                }
            }

            html += '<div class="' + classes + '" data-year="' + y + '" data-month="' + m + '" data-day="' + d + '"' +
                ' tabindex="0" role="button" aria-label="View ' + MONTHS[m - 1] + ' ' + d + ', ' + y + '">';
            html += '<span class="calendar-day-num">' + d + '</span>';
            if (preview) {
                var shortTitle = preview.length > 18 ? preview.slice(0, 18) + '\u2026' : preview;
                html += '<div class="calendar-preview">' + escapeHtml(shortTitle) + '</div>';
            }
            if (hasActivity) {
                html += '<span class="calendar-dot"></span>';
            }
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
                    cell.addEventListener('keydown', function(ev) {
                        if (ev.key === 'Enter' || ev.key === ' ') {
                            ev.preventDefault();
                            var yr = parseInt(cell.getAttribute('data-year'), 10);
                            var mo = parseInt(cell.getAttribute('data-month'), 10);
                            var da = parseInt(cell.getAttribute('data-day'), 10);
                            showDayView(yr, mo, da);
                        }
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

        var monthTitleEl = document.getElementById('calendar-month-title');
        if (monthTitleEl) monthTitleEl.textContent = dateLabel;

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
                    var autoClass = ann.is_auto ? ' announcement-card-auto' : '';
                    return '<div class="announcement-card' + autoClass + '">' +
                        '<p class="announcement-content">' + escapeHtml(ann.content) + '</p>' +
                        '<p class="announcement-meta">' + escapeHtml(time) + '</p>' +
                        '</div>';
                }).join('');
            }
        }

        document.getElementById('calendar-view').classList.add('hidden');
        document.getElementById('calendar-day-view').classList.remove('hidden');
    }

    function formatTimeAgo(iso) {
        if (!iso) return '';
        var then = new Date(iso);
        if (isNaN(then.getTime())) return '';
        var now = new Date();
        var diffMs = now - then;
        if (diffMs < 0) diffMs = 0;
        var seconds = Math.floor(diffMs / 1000);
        var minutes = Math.floor(seconds / 60);
        var hours = Math.floor(minutes / 60);
        var days = Math.floor(hours / 24);
        if (seconds < 45) return 'Just now';
        if (minutes < 60) return minutes === 1 ? '1 minute ago' : minutes + ' minutes ago';
        if (hours < 24) return hours === 1 ? '1 hour ago' : hours + ' hours ago';
        if (days < 7) return days === 1 ? '1 day ago' : days + ' days ago';
        var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return months[then.getMonth()] + ' ' + then.getDate() + ', ' + then.getFullYear();
    }

    function formatAnnouncementTime(iso) {
        return formatTimeAgo(iso);
    }

    function escapeHtml(s) {
        if (!s) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function goToPrevDay() {
        var y = state.dayYear;
        var m = state.dayMonth;
        var d = state.dayDay - 1;
        if (d < 1) {
            m--;
            if (m < 1) {
                m = 12;
                y--;
            }
            d = daysInMonth(y, m);
        }
        state.dayYear = y;
        state.dayMonth = m;
        state.dayDay = d;
        showDayView(y, m, d);
    }

    function goToNextDay() {
        var y = state.dayYear;
        var m = state.dayMonth;
        var d = state.dayDay + 1;
        var maxD = daysInMonth(y, m);
        if (d > maxD) {
            d = 1;
            m++;
            if (m > 12) {
                m = 1;
                y++;
            }
        }
        state.dayYear = y;
        state.dayMonth = m;
        state.dayDay = d;
        showDayView(y, m, d);
    }

    function backToCalendar() {
        if (state.view === 'day' && state.dayYear != null && state.dayMonth != null) {
            state.year = state.dayYear;
            state.month = state.dayMonth;
        }
        state.view = 'grid';
        renderGrid();
        document.getElementById('calendar-view').classList.remove('hidden');
        document.getElementById('calendar-day-view').classList.add('hidden');
    }

    function onPrevClick() {
        if (state.view === 'day') {
            goToPrevDay();
        } else {
            state.month--;
            if (state.month < 1) { state.month = 12; state.year--; }
            renderGrid();
        }
    }

    function onNextClick() {
        if (state.view === 'day') {
            goToNextDay();
        } else {
            state.month++;
            if (state.month > 12) { state.month = 1; state.year++; }
            renderGrid();
        }
    }

    function goToToday() {
        state.year = todayY;
        state.month = todayM;
        if (state.view === 'day') {
            showDayView(todayY, todayM, todayD);
        } else {
            renderGrid();
        }
    }

    function init() {
        renderGrid();

        var prevBtn = document.getElementById('calendar-prev');
        var nextBtn = document.getElementById('calendar-next');
        if (prevBtn) prevBtn.addEventListener('click', onPrevClick);
        if (nextBtn) nextBtn.addEventListener('click', onNextClick);

        var backBtn = document.getElementById('back-to-calendar');
        if (backBtn) backBtn.addEventListener('click', backToCalendar);

        var todayBtn = document.getElementById('calendar-today');
        if (todayBtn) todayBtn.addEventListener('click', goToToday);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
