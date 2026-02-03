function pad2(n) {
    return String(n).padStart(2, '0');
}

function formatTime(ts) {
    const d = new Date(ts * 1000);
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function formatDate(iso) {
    const parts = String(iso || '').split('-');
    if (parts.length !== 3) return String(iso || '');
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

function clearNode(node) {
    if (!node) return;
    node.innerHTML = '';
}

function renderEmpty(target, text) {
    if (!target) return;
    const el = document.createElement('div');
    el.style.color = 'var(--text-secondary)';
    el.style.fontSize = 'var(--text-sm)';
    el.textContent = text;
    target.appendChild(el);
}

function isCompletedStatus(value) {
    return value === 'completed' || value === 2 || value === '2';
}

function renderAgendaItem(target, { id, title, dotColor, timeText, metaText, isNow }) {
    const item = document.createElement('div');
    item.className = `today2-item${isNow ? ' today2-item-now' : ''}`;
    item.addEventListener('click', () => {
        if (typeof open_task_by_id === 'function') open_task_by_id(id);
    });

    const dot = document.createElement('div');
    dot.className = 'today2-dot';
    if (dotColor) dot.style.background = dotColor;

    const main = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'today2-item-title';
    name.textContent = title || '—';

    const meta = document.createElement('div');
    meta.className = 'today2-item-meta';
    meta.textContent = metaText || '';
    main.appendChild(name);
    if (metaText) main.appendChild(meta);

    const time = document.createElement('div');
    time.className = 'today2-item-time';
    time.textContent = timeText || '';

    item.appendChild(dot);
    item.appendChild(main);
    item.appendChild(time);
    target.appendChild(item);
}

function renderToday(data) {
    const fill = document.getElementById('today-progress-fill');
    const stats = document.getElementById('today-progress-stats');
    const dateLabel = document.getElementById('today-date-label');
    const remainingEl = document.getElementById('today-remaining');
    const remainingSubEl = document.getElementById('today-remaining-sub');
    const scheduledCountEl = document.getElementById('today-scheduled-count');
    const deadlinesCountEl = document.getElementById('today-deadlines-count');
    const agendaEl = document.getElementById('today-agenda');
    const inboxEl = document.getElementById('today-inbox');
    const inboxCountEl = document.getElementById('today-inbox-count');

    if (dateLabel) dateLabel.textContent = formatDate(data.date);

    const timed = Array.isArray(data.timed) ? data.timed : [];
    const deadlines = Array.isArray(data.deadlines) ? data.deadlines : [];
    const loose = Array.isArray(data.loose) ? data.loose : [];

    const total = timed.length + deadlines.length;
    const completed =
        timed.filter((t) => t && isCompletedStatus(t.status_type)).length +
        deadlines.filter((t) => t && isCompletedStatus(t.status_type)).length;
    const remaining = Math.max(0, total - completed);
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

    if (remainingEl) remainingEl.textContent = String(remaining);
    if (remainingSubEl) remainingSubEl.textContent = `${completed}/${total} · ${percent}%`;
    if (scheduledCountEl) scheduledCountEl.textContent = String(timed.length);
    if (deadlinesCountEl) deadlinesCountEl.textContent = String(deadlines.length);

    if (fill) fill.style.width = `${percent}%`;
    if (stats) stats.textContent = `Готово: ${completed}/${total} · Прогресс: ${percent}%`;

    clearNode(agendaEl);
    clearNode(inboxEl);
    if (inboxCountEl) inboxCountEl.textContent = String(loose.length);

    const nowTs = data.now_ts || Math.floor(Date.now() / 1000);

    const agenda = [];
    timed.forEach((t) => {
        agenda.push({
            kind: 'timed',
            id: t.id,
            title: t.title,
            dotColor: t.status_color,
            startTs: t.start_ts,
            endTs: t.end_ts,
            sortTs: t.start_ts || 0,
            isNow: (t.start_ts && t.end_ts) ? (nowTs >= t.start_ts && nowTs <= t.end_ts) : false,
        });
    });
    deadlines.forEach((t) => {
        agenda.push({
            kind: 'deadline',
            id: t.id,
            title: t.title,
            dotColor: t.status_color,
            deadlineTs: t.deadline_ts,
            sortTs: t.deadline_ts || 0,
            isNow: false,
        });
    });
    agenda.sort((a, b) => (a.sortTs || 0) - (b.sortTs || 0));

    if (!agenda.length) {
        renderEmpty(agendaEl, 'На сегодня слотов и дедлайнов нет');
    } else {
        agenda.forEach((it) => {
            const timeText = it.kind === 'timed'
                ? `${formatTime(it.startTs)}–${formatTime(it.endTs)}`
                : `до ${formatTime(it.deadlineTs)}`;
            const metaText = it.kind === 'timed' ? 'Слот' : 'Дедлайн';
            renderAgendaItem(agendaEl, {
                id: it.id,
                title: it.title,
                dotColor: it.dotColor,
                timeText,
                metaText,
                isNow: it.isNow,
            });
        });
    }

    if (!loose.length) {
        renderEmpty(inboxEl, 'Пусто');
    } else {
        loose.slice(0, 30).forEach((t) => {
            renderAgendaItem(inboxEl, {
                id: t.id,
                title: t.title,
                dotColor: t.status_color,
                timeText: '',
                metaText: 'Без времени',
                isNow: false,
            });
        });
    }
}

function createDebouncer(delayMs) {
    let t = null;
    return (fn) => {
        if (t) clearTimeout(t);
        t = setTimeout(fn, delayMs);
    };
}

async function loadToday() {
    const data = await request({ url: '/task/today/', method: 'GET' });
    if (!data) return null;
    renderToday(data);
    return data;
}

document.addEventListener('DOMContentLoaded', () => {
    const debounce = createDebouncer(250);
    let lastData = null;

    const refresh = async () => {
        lastData = await loadToday();
    };

    const refreshBtn = document.getElementById('today-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => refresh());

    const createBtn = document.getElementById('today-create-btn');
    if (createBtn) {
        createBtn.addEventListener('click', () => {
            if (typeof open_create_task === 'function') open_create_task(null);
        });
    }

    const inboxToggle = document.getElementById('today-inbox-toggle');
    const inboxEl = document.getElementById('today-inbox');
    if (inboxToggle && inboxEl) {
        inboxToggle.addEventListener('click', () => {
            inboxEl.classList.toggle('hide');
        });
    }

    refresh();

    window.addEventListener('resize', () => {
        debounce(() => {
            if (lastData) renderToday(lastData);
        });
    });

    document.addEventListener('taskUpdate', () => {
        debounce(() => refresh());
    });

    setInterval(() => {
        if (!lastData) return;
        lastData.now_ts = Math.floor(Date.now() / 1000);
        renderToday(lastData);
    }, 60000);
});
