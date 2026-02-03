let dragTask = null;      // оригинальный блок
let ghost = null;         // призрак
let shadow = null;        // серая тень
let shiftX = 0;
let shiftY = 0;
let taskHeight = 0;
let currentWeekStartIso = null;
let dragCandidate = null;
let candidateDownX = 0;
let candidateDownY = 0;
let dragStarted = false;
let dragOriginalParent = null;
let dragOriginalTop = null;
let dragOriginalLeft = null;

// --- Resize State ---
let isResizing = false;
let resizeDirection = null; // 'top' | 'bottom'
let resizeTask = null;
let resizeStartY = 0;
let resizeOriginalTopVal = 0;
let resizeOriginalHeightVal = 0;

// --- Create State ---
let isCreating = false;
let createStartY = 0;
let createColumn = null;
let createGhost = null;


function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function placeShadow(dayColumn, clientY) {
    if (!shadow) return;

    const colRect = dayColumn.getBoundingClientRect();
    let desiredTop = clientY - colRect.top - taskHeight / 2;
    let top = desiredTop;

    const colHeight = colRect.height;
    top = clamp(top, 0, Math.max(0, colHeight - taskHeight));

    const tasks = Array.from(dayColumn.querySelectorAll('.cal-task-block'))
        .filter(t => !t.classList.contains('cal-task-hidden'));

    const margin = 2; // как в cal-task-block

    let changed = true;
    let iter = 0;
    const maxIter = 20; // защита от бесконечных циклов

    while (changed && iter < maxIter) {
        iter++;
        changed = false;

        const shadowTop = top;
        const shadowBottom = shadowTop + taskHeight;

        for (const task of tasks) {
            const r = task.getBoundingClientRect();
            const taskTop = r.top - colRect.top;
            const taskBottom = taskTop + r.height;

            const overlap = shadowTop < taskBottom && shadowBottom > taskTop;
            if (overlap) {
                const taskCenter = (taskTop + taskBottom) / 2;
                const shadowCenter = (shadowTop + shadowBottom) / 2;

                if (shadowCenter < taskCenter) {
                    // вверх
                    top = taskTop - taskHeight - margin;
                } else {
                    // вниз
                    top = taskBottom + margin;
                }

                top = clamp(top, 0, Math.max(0, colHeight - taskHeight));
                changed = true;
                break;
            }
        }
    }

    // если дошли до лимита — просто прячем тень, чтобы не висло
    if (iter >= maxIter) {
        shadow.style.display = 'none';
        return;
    }

    shadow.style.top = top + 'px';
    shadow.style.display = 'flex';

    if (window.CALENDAR_PX_PER_MINUTE) {
        var minutesTotal = Math.round(top / window.CALENDAR_PX_PER_MINUTE);
        var hh = Math.floor(minutesTotal / 60);
        var mm = minutesTotal % 60;

        var hhStr = String(hh).padStart(2, '0');
        var mmStr = String(mm).padStart(2, '0');
        shadow.innerText = hhStr + ':' + mmStr;
    }

    shadow.style.display = 'flex';
}

function onMouseMove(e) {
    if (!ghost || !dragTask) return;

    // двигаем призрак
    ghost.style.left = (e.clientX - shiftX) + 'px';
    ghost.style.top  = (e.clientY - shiftY) + 'px';

    // временно прячем призрак для elementFromPoint
    ghost.style.pointerEvents = 'none';
    const elem = document.elementFromPoint(e.clientX, e.clientY);
    ghost.style.pointerEvents = '';

    if (!elem) return;

    const dayColumn = elem.closest('.day-column');
    if (!dayColumn) {
        if (shadow) shadow.style.display = 'none';
        return;
    }

    if (!shadow) return;

    // если тень в другой колонке — перенесём
    if (shadow.parentElement !== dayColumn) {
        dayColumn.appendChild(shadow);
    }

    placeShadow(dayColumn, e.clientY);
}

function onMouseUp(e) {
    if (!dragTask) return;

    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);

    if (shadow && shadow.parentElement) {
        const col = shadow.parentElement;
        dragTask.style.top = shadow.style.top;
        dragTask.style.left = '0px';
        dragTask.style.width = 'calc(100% - 4px)';
        dragTask.style.margin = '2px';
        col.appendChild(dragTask);
    }

    dragTask.classList.remove('cal-task-hidden');

    if (ghost && ghost.parentElement) ghost.parentElement.removeChild(ghost);
    if (shadow && shadow.parentElement) shadow.parentElement.removeChild(shadow);

    var droppedTask = dragTask;
    var droppedParent = droppedTask.parentElement;
    var droppedTop = droppedTask.style.top;
    var originalParent = dragOriginalParent;
    var originalTop = dragOriginalTop;
    var originalLeft = dragOriginalLeft;

    dragTask = null;
    ghost = null;
    shadow = null;
    dragOriginalParent = null;
    dragOriginalTop = null;
    dragOriginalLeft = null;

    persistDroppedTiming(droppedTask, droppedParent, droppedTop, originalParent, originalTop, originalLeft);
}

function startDrag(task, e) {
    dragTask = task;
    dragStarted = true;

    const rect = task.getBoundingClientRect();
    shiftX = e.clientX - rect.left;
    shiftY = e.clientY - rect.top;
    taskHeight = rect.height;

    dragOriginalParent = task.parentElement;
    dragOriginalTop = task.style.top || "";
    dragOriginalLeft = task.style.left || "";

    dragTask.classList.add('cal-task-hidden');

    ghost = dragTask.cloneNode(true);
    ghost.classList.add('cal-task-ghost');
    ghost.style.position = 'fixed';
    ghost.style.left = rect.left + 'px';
    ghost.style.top = rect.top + 'px';
    ghost.style.width = rect.width + 'px';
    ghost.style.height = rect.height + 'px';
    ghost.style.margin = '0';
    document.body.appendChild(ghost);

    shadow = document.createElement('div');
    shadow.className = 'cal-task-shadow glass-block';
    shadow.style.position = 'absolute';
    shadow.style.left = '0px';
    shadow.style.width = 'calc(100% - 4px)';
    shadow.style.height = rect.height + 'px';
    shadow.style.margin = '2px';

    const col = dragTask.closest('.day-column');
    if (col) {
        col.appendChild(shadow);
        const colRect = col.getBoundingClientRect();
        const initialTop = rect.top - colRect.top;
        shadow.style.top = initialTop + 'px';
    }
}

function extractTaskIdFromElement(taskEl) {
    if (!taskEl) return null;
    var raw = taskEl.dataset.sourceId || taskEl.dataset.id;
    if (!raw) return null;
    raw = String(raw);
    if (raw.includes(':')) raw = raw.split(':')[0];
    var idNum = parseInt(raw, 10);
    if (Number.isNaN(idNum)) return null;
    return idNum;
}

function openTaskFromCalendar(taskEl) {
    var id = extractTaskIdFromElement(taskEl);
    if (!id) return;
    if (typeof window.open_task_by_id === 'function') {
        window.open_task_by_id(id);
    }
}

function parseDateKeyToIsoDate(dateKey) {
    var parts = String(dateKey || "").split(".");
    if (parts.length !== 3) return null;
    var dd = parseInt(parts[0], 10);
    var mm = parseInt(parts[1], 10);
    var yyyy = parseInt(parts[2], 10);
    if (!yyyy || !mm || !dd) return null;
    return String(yyyy).padStart(4, "0") + "-" + String(mm).padStart(2, "0") + "-" + String(dd).padStart(2, "0");
}

function toLocalIsoDateTime(isoDate, minutesFromMidnight) {
    var date = isoToDate(isoDate);
    if (!date) return null;
    var hh = Math.floor(minutesFromMidnight / 60);
    var mm = minutesFromMidnight % 60;
    return formatIsoDate(date) + "T" + pad2(hh) + ":" + pad2(mm) + ":00";
}

async function patchTaskTiming(taskId, startedAtIso, finishedAtIso) {
    var csrfEl = document.querySelector('input[name=csrfmiddlewaretoken]');
    var csrf = csrfEl ? csrfEl.value : "";

    var resp = await fetch("/task/" + taskId + "/timing/", {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
        },
        body: JSON.stringify({
            started_at: startedAtIso,
            finished_at: finishedAtIso,
        }),
    });

    var contentType = (resp.headers.get("content-type") || "").toLowerCase();
    var data = null;
    if (contentType.includes("application/json")) {
        data = await resp.json();
    } else {
        var txt = await resp.text();
        throw new Error(txt || "Сервер вернул не-JSON ответ");
    }

    if (!resp.ok) {
        var msg = (data && data.detail) ? data.detail : "Ошибка сохранения";
        throw new Error(msg);
    }

    return data;
}

function computeTimingFromElement(taskEl) {
    if (!taskEl) return null;
    var col = taskEl.closest(".day-column");
    if (!col) return null;
    var dateKey = col.dataset.date;
    var isoDate = parseDateKeyToIsoDate(dateKey);
    if (!isoDate) return null;

    var topPx = parseFloat(String(taskEl.style.top || "0").replace("px", "")) || 0;
    var pxPerMinute = window.CALENDAR_PX_PER_MINUTE;
    if (!pxPerMinute) return null;

    var startedMinutes = Math.max(0, Math.min(1439, Math.round(topPx / pxPerMinute)));
    var durationMinutes = Math.max(15, Math.round((taskEl.getBoundingClientRect().height || 0) / pxPerMinute));
    var finishedMinutes = startedMinutes + durationMinutes;

    if (finishedMinutes > 1440) {
        finishedMinutes = 1440;
        startedMinutes = Math.max(0, finishedMinutes - durationMinutes);
    }

    var startedAtIso = toLocalIsoDateTime(isoDate, startedMinutes);
    var finishedAtIso = toLocalIsoDateTime(isoDate, finishedMinutes);
    if (!startedAtIso || !finishedAtIso) return null;

    return {
        startedAtIso: startedAtIso,
        finishedAtIso: finishedAtIso,
    };
}

async function persistDroppedTiming(taskEl, droppedParent, droppedTop, originalParent, originalTop, originalLeft) {
    if (!taskEl) return;

    var taskId = extractTaskIdFromElement(taskEl);
    if (!taskId) return;

    var timing = computeTimingFromElement(taskEl);
    if (!timing) return;

    try {
        await patchTaskTiming(taskId, timing.startedAtIso, timing.finishedAtIso);
    } catch (err) {
        if (originalParent) originalParent.appendChild(taskEl);
        if (typeof originalTop === "string") taskEl.style.top = originalTop;
        if (typeof originalLeft === "string") taskEl.style.left = originalLeft;

        alert(String(err && err.message ? err.message : err));
    }
}

// --- Resize Implementation ---
function startResize(e, task, direction) {
    isResizing = true;
    resizeTask = task;
    resizeDirection = direction;
    resizeStartY = e.clientY;
    
    // Parse current geometry
    const style = window.getComputedStyle(task);
    resizeOriginalTopVal = parseFloat(style.top) || 0;
    resizeOriginalHeightVal = parseFloat(style.height) || 0;
    
    // Disable transition for instant response
    task.style.transition = 'none';

    document.addEventListener('mousemove', onResizeMove);
    document.addEventListener('mouseup', onResizeEnd);
}

function onResizeMove(e) {
    if (!isResizing || !resizeTask) return;
    
    const deltaY = e.clientY - resizeStartY;
    const pxPerMin = window.CALENDAR_PX_PER_MINUTE || 1;
    const minHeight = 15 * pxPerMin; // 15 minutes minimum
    
    let currentTop = resizeOriginalTopVal;
    let currentHeight = resizeOriginalHeightVal;
    
    if (resizeDirection === 'bottom') {
        let newHeight = resizeOriginalHeightVal + deltaY;
        newHeight = Math.max(newHeight, minHeight);
        
        // Check column bounds
        const col = resizeTask.parentElement;
        if (col) {
            const colHeight = col.clientHeight;
            if (resizeOriginalTopVal + newHeight > colHeight) {
                newHeight = colHeight - resizeOriginalTopVal;
            }
        }
        
        resizeTask.style.height = newHeight + 'px';
        currentHeight = newHeight;
        
    } else if (resizeDirection === 'top') {
        let newTop = resizeOriginalTopVal + deltaY;
        let newHeight = resizeOriginalHeightVal - deltaY;
        
        // Constraints
        if (newHeight < minHeight) {
            newTop = resizeOriginalTopVal + (resizeOriginalHeightVal - minHeight);
            newHeight = minHeight;
        }
        
        if (newTop < 0) {
            newHeight += newTop; // increase height by negative overlap
            newTop = 0;
        }
        
        resizeTask.style.top = newTop + 'px';
        resizeTask.style.height = newHeight + 'px';
        
        currentTop = newTop;
        currentHeight = newHeight;
    }

    // Update text immediately
    const startMins = Math.round(currentTop / pxPerMin);
    const endMins = Math.round((currentTop + currentHeight) / pxPerMin);
    
    const sHH = Math.floor(startMins / 60);
    const sMM = startMins % 60;
    const eHH = Math.floor(endMins / 60);
    const eMM = endMins % 60;
    
    const timeStr = 
        String(sHH).padStart(2, '0') + ':' + String(sMM).padStart(2, '0') + 
        ' – ' + 
        String(eHH).padStart(2, '0') + ':' + String(eMM).padStart(2, '0');
        
    const timeEl = resizeTask.querySelector('.cal-task-time');
    if (timeEl) {
        timeEl.innerText = timeStr;
    }
}

function onResizeEnd(e) {
    if (!isResizing) return;
    
    document.removeEventListener('mousemove', onResizeMove);
    document.removeEventListener('mouseup', onResizeEnd);
    
    const task = resizeTask;
    
    // Reset state
    isResizing = false;
    resizeTask = null;
    resizeDirection = null;
    
    // Restore transition
    task.style.transition = '';

    // Persist changes
    // Reuse logic from drag-n-drop persistence
    // We pass nulls for originalParent/Top/Left because if it fails, 
    // we might just want to revert to visual state or reload, 
    // but here we can just let it stay visually or reload the week.
    // Ideally we should revert visually on error.
    
    const taskId = extractTaskIdFromElement(task);
    if (!taskId) return;

    const timing = computeTimingFromElement(task);
    if (!timing) return;

    patchTaskTiming(taskId, timing.startedAtIso, timing.finishedAtIso)
        .then(() => {
            // Update UI text immediately?
            // renderTasksOnCalendar uses server data usually. 
            // We can update text locally for responsiveness.
            const nameTimeEl = task.querySelector('.cal-task-time');
            if (nameTimeEl) {
                const s = timing.startedAtIso.split('T')[1].substring(0, 5);
                const f = timing.finishedAtIso.split('T')[1].substring(0, 5);
                nameTimeEl.innerText = `${s} – ${f}`;
            }
        })
        .catch(err => {
            alert('Ошибка при изменении времени: ' + err.message);
            // Revert visual
            task.style.top = resizeOriginalTopVal + 'px';
            task.style.height = resizeOriginalHeightVal + 'px';
        });
}

function onMouseDown(e) {
    // console.log('onMouseDown', e.target, e.button);

    // 1. Check Resize
    if (e.target.classList.contains('resize-handle')) {
        const task = e.target.closest('.cal-task-block');
        if (task) {
            e.preventDefault();
            e.stopPropagation();
            const direction = e.target.classList.contains('top') ? 'top' : 'bottom';
            startResize(e, task, direction);
            return;
        }
    }

    // 2. Drag & Drop Logic (Existing Task)
    const task = e.target.closest('.cal-task-block');
    if (task) {
        // console.log('Task clicked', task);
        if (e.button !== 0) return; // только ЛКМ

        e.preventDefault();

        dragCandidate = task;
        candidateDownX = e.clientX;
        candidateDownY = e.clientY;
        dragStarted = false;

        function onCandidateMove(ev) {
            if (isResizing) return; // Don't drag if resizing

            if (dragTask) {
                onMouseMove(ev);
                return;
            }
            if (!dragCandidate) return;
            if (dragCandidate.dataset && dragCandidate.dataset.sourceId) return;
            var dx = Math.abs(ev.clientX - candidateDownX);
            var dy = Math.abs(ev.clientY - candidateDownY);
            if (dx + dy < 6) return;

            const candidate = dragCandidate;
            dragCandidate = null;
            startDrag(candidate, ev);
            onMouseMove(ev);
        }

        function onCandidateUp(ev) {
            document.removeEventListener('mousemove', onCandidateMove);
            document.removeEventListener('mouseup', onCandidateUp);

            if (dragTask) {
                onMouseUp(ev);
                return;
            }

            if (dragCandidate && !dragStarted) {
                var dx = Math.abs(ev.clientX - candidateDownX);
                var dy = Math.abs(ev.clientY - candidateDownY);
                if (dx + dy < 6) {
                    openTaskFromCalendar(dragCandidate);
                }
            }

            dragCandidate = null;
        }

        document.addEventListener('mousemove', onCandidateMove);
        document.addEventListener('mouseup', onCandidateUp);
        return;
    }

    // 3. Create Task Logic (Empty Space)
    const dayColumn = e.target.closest('.day-column');
    // console.log('Day column check:', dayColumn);
    
    if (dayColumn) {
        if (e.button !== 0) return;
        e.preventDefault();
        startCreation(e, dayColumn);
    }
}

// --- Creation Implementation ---
function startCreation(e, col) {
    isCreating = true;
    createColumn = col;
    const rect = col.getBoundingClientRect();
    createStartY = e.clientY - rect.top;
    
    // Create ghost
    createGhost = document.createElement('div');
    createGhost.className = 'cal-task-block glass-block small-border';
    createGhost.style.position = 'absolute';
    createGhost.style.left = '2px';
    createGhost.style.width = 'calc(100% - 4px)';
    createGhost.style.zIndex = '100';
    createGhost.style.pointerEvents = 'none';
    createGhost.style.backgroundColor = 'rgba(50, 150, 255, 0.3)'; // Semi-transparent blue
    
    // Initial style
    createGhost.style.top = createStartY + 'px';
    createGhost.style.height = '0px';
    
    // Add time label inside
    createGhost.innerHTML = '<div class="cal-task-time" style="padding: 2px; font-size: 10px; color: var(--text-main);"></div>';
    
    col.appendChild(createGhost);
    
    document.addEventListener('mousemove', onCreateMove);
    document.addEventListener('mouseup', onCreateEnd);
}

function onCreateMove(e) {
    if (!isCreating || !createColumn) return;
    
    const clientY = e.clientY;
    
    if (!window.createRaf) {
        window.createRaf = requestAnimationFrame(() => {
            handleCreateMove(clientY);
            window.createRaf = null;
        });
    }
}

function handleCreateMove(clientY) {
    if (!isCreating || !createColumn) return;

    const rect = createColumn.getBoundingClientRect();
    let currentY = clientY - rect.top;
    
    // Clamp to column bounds
    currentY = Math.max(0, Math.min(rect.height, currentY));
    
    let top = Math.min(createStartY, currentY);
    let height = Math.abs(currentY - createStartY);
    
    createGhost.style.top = top + 'px';
    createGhost.style.height = height + 'px';
    
    updateCreateGhostTime(top, height);
}

function updateCreateGhostTime(top, height) {
    const pxPerMin = window.CALENDAR_PX_PER_MINUTE || 1;
    const startMins = Math.round(top / pxPerMin);
    const durationMins = Math.round(height / pxPerMin);
    const endMins = startMins + durationMins;
    
    const sHH = Math.floor(startMins / 60);
    const sMM = startMins % 60;
    const eHH = Math.floor(endMins / 60);
    const eMM = endMins % 60;
    
    const timeStr = 
        String(sHH).padStart(2, '0') + ':' + String(sMM).padStart(2, '0') + 
        ' – ' + 
        String(eHH).padStart(2, '0') + ':' + String(eMM).padStart(2, '0');
        
    const timeEl = createGhost.querySelector('.cal-task-time');
    if (timeEl) timeEl.innerText = timeStr;
}

function onCreateEnd(e) {
    if (!isCreating) return;
    
    document.removeEventListener('mousemove', onCreateMove);
    document.removeEventListener('mouseup', onCreateEnd);
    
    // Calculate final times
    const rect = createColumn.getBoundingClientRect();
    let currentY = e.clientY - rect.top;
    currentY = Math.max(0, Math.min(rect.height, currentY));
    
    let top = Math.min(createStartY, currentY);
    let height = Math.abs(currentY - createStartY);
    
    const pxPerMin = window.CALENDAR_PX_PER_MINUTE || 1;
    // Minimum 15 mins if just a click
    if (height < 5) {
        height = 15 * pxPerMin;
    }
    
    const startMins = Math.round(top / pxPerMin);
    const durationMins = Math.round(height / pxPerMin);
    const endMins = startMins + durationMins;
    
    // Get Date
    const dateKey = createColumn.dataset.date; // "dd.mm.yyyy"
    const isoDate = parseDateKeyToIsoDate(dateKey); // "yyyy-mm-dd"
    
    if (isoDate) {
        // toLocalIsoDateTime returns "YYYY-MM-DDTHH:MM:SS"
        // We need "YYYY-MM-DDTHH:MM" for datetime-local input
        const startedAt = toLocalIsoDateTime(isoDate, startMins).substring(0, 16);
        const finishedAt = toLocalIsoDateTime(isoDate, endMins).substring(0, 16);
        
        if (typeof window.open_create_task === 'function') {
            window.open_create_task({
                started_at: startedAt,
                finished_at: finishedAt,
                deadline_at: finishedAt
            });
        }
    }
    
    if (createGhost) createGhost.remove();
    createGhost = null;
    createColumn = null;
    isCreating = false;
}

// ---------------------------------

// парсим "16.11.2025 10:00" или "2025-11-16T10:00:00" -> { dateKey: "16.11.2025", minutesFromMidnight: 600 }
function parseDateTime(str) {
    if (!str) return { dateKey: "", minutesFromMidnight: 0 };

    if (str.includes('T')) {
        // ISO format: YYYY-MM-DDTHH:MM:SS
        var dateObj = new Date(str);
        var dd = String(dateObj.getDate()).padStart(2, '0');
        var mm = String(dateObj.getMonth() + 1).padStart(2, '0');
        var yyyy = dateObj.getFullYear();
        var dateKey = `${dd}.${mm}.${yyyy}`;
        
        var minutes = dateObj.getHours() * 60 + dateObj.getMinutes();
        return {
            dateKey: dateKey,
            minutesFromMidnight: minutes
        };
    }

    var parts = str.split(' ');
    var datePart = parts[0];       // "16.11.2025"
    var timePart = parts[1];       // "10:00"

    var timePieces = timePart.split(':');
    var hh = parseInt(timePieces[0], 10);
    var mm = parseInt(timePieces[1], 10);

    return {
        dateKey: datePart,
        minutesFromMidnight: hh * 60 + mm,
    };
}

function drawSingleTask(task) {
    // Log info as requested
    console.log("WebSocket Info received for task:", task);

    // Handle different field names from API (ended_at) vs DTO (finished_at)
    var startedAt = task.started_at;
    var endedAt = task.ended_at || task.finished_at;

    if (!startedAt || !endedAt) {
        console.warn("Task missing timing info", task);
        return;
    }

    var startInfo = parseDateTime(startedAt);
    var endInfo   = parseDateTime(endedAt);

    // пока считаем, что задача не переходит через сутки
    if (startInfo.dateKey !== endInfo.dateKey) {
        return;
    }

    var dayColumn = document.querySelector(
        '.day-column[data-date="' + startInfo.dateKey + '"]'
    );
    if (!dayColumn) {
        // нет такой даты в текущей неделе — пропускаем
        return;
    }
    
    // Remove existing if updating
    var existing = dayColumn.querySelector(`.cal-task-block[data-id="${task.id}"]`);
    if (existing) existing.remove();

    var pxPerMinute = window.CALENDAR_PX_PER_MINUTE || (60.0 / 60.0); // fallback

    var durationMinutes = Math.max(15, endInfo.minutesFromMidnight - startInfo.minutesFromMidnight);
    var topPx = startInfo.minutesFromMidnight * pxPerMinute;
    var heightPx = durationMinutes * pxPerMinute;

    // создаём DOM-элемент задачи
    var el = document.createElement('div');
    el.className = 'cal-task-block glass-block small-border';
    el.dataset.id = task.id;
    if (task.source_id) {
        el.dataset.sourceId = task.source_id;
    }

    el.style.top = topPx + 'px';
    el.style.height = heightPx + 'px';

    // Форматируем время для отображения
    var startTimeStr = "";
    if (startedAt.includes('T')) {
        startTimeStr = startedAt.split('T')[1].substring(0, 5);
    } else {
        startTimeStr = startedAt.split(' ')[1];
        if (startTimeStr && startTimeStr.length > 5) startTimeStr = startTimeStr.substring(0, 5);
    }

    var endTimeStr = "";
    if (endedAt.includes('T')) {
        endTimeStr = endedAt.split('T')[1].substring(0, 5);
    } else {
        endTimeStr = endedAt.split(' ')[1];
        if (endTimeStr && endTimeStr.length > 5) endTimeStr = endTimeStr.substring(0, 5);
    }

    // простое содержание: заголовок + время
    el.innerHTML = `
        <div class="resize-handle top"></div>
        <div class="cal-task-info">
            <hr class="cal-task-status">
            <div class="cal-task-name-n-time">
                <div class="cal-task-name">${task.name || task.title}</div>
                <div class="cal-task-time">${startTimeStr} – ${endTimeStr}</div>                                            
            </div>
        </div>
        <div class="resize-handle bottom"></div>
    `;

    dayColumn.appendChild(el);
}

// основная функция рендера задач
function renderTasksOnCalendar(tasks) {
    // 1) узнаём высоту одного часового ряда
    var firstRow = document.querySelector('.calendar--row');
    if (!firstRow) return;

    var rowHeight = firstRow.getBoundingClientRect().height; // px за 1 час
    var pxPerMinute = rowHeight / 60.0;

    window.CALENDAR_PX_PER_MINUTE = pxPerMinute;

    // 2) очищаем календарь от старых задач
    document.querySelectorAll('.day-column').forEach(function(col) {
        // удаляем только задачи, не тени/призраки
        Array.from(col.querySelectorAll('.cal-task-block')).forEach(function(taskEl) {
            taskEl.remove();
        });
    });

    // 3) рисуем новые задачи
    tasks.forEach(function(task) {
        drawSingleTask(task);
    });
}

// Listen for WebSocket updates
document.addEventListener('taskUpdate', function(e) {
    const data = e.detail;
    // data = { type: 'task_update', action: 'create'|'update', task: {...} }
    if (data.action === 'create' || data.action === 'update') {
        console.log("WebSocket Update Event:", data);
        if (data.task.started_at && (data.task.ended_at || data.task.finished_at)) {
            drawSingleTask(data.task);
        }
    }
});

// ---------------------------------

function isoToDate(iso) {
    var parts = String(iso || "").split("-");
    if (parts.length !== 3) return null;
    var y = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10) - 1;
    var d = parseInt(parts[2], 10);
    if (!y || m < 0 || d < 1) return null;
    return new Date(y, m, d);
}

function pad2(v) {
    return String(v).padStart(2, "0");
}

function formatIsoDate(date) {
    return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
}

function startOfWeekMonday(date) {
    var d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    var day = (d.getDay() + 6) % 7;
    d.setDate(d.getDate() - day);
    return d;
}

function shiftWeek(weekStartIso, deltaWeeks) {
    var d = isoToDate(weekStartIso);
    if (!d) return null;
    d.setDate(d.getDate() + deltaWeeks * 7);
    return formatIsoDate(d);
}

function setWeekStructure(days) {
    var daysRoot = document.getElementById("calendar-days");
    var columnsRoot = document.getElementById("calendar-times-columns");
    if (!daysRoot || !columnsRoot) return;

    daysRoot.innerHTML = "";

    Array.from(columnsRoot.children).forEach(function(child) {
        if (!child.classList.contains("time-column")) child.remove();
    });

    days.forEach(function(day) {
        var dayEl = document.createElement("div");
        dayEl.className = "day-number";
        dayEl.innerText = day.label;
        daysRoot.appendChild(dayEl);
    });

    days.forEach(function(day) {
        // Removed hr to prevent layout issues
        var col = document.createElement("div");
        col.className = "day-column";
        col.dataset.date = day.date_key;
        columnsRoot.appendChild(col);
    });
}

function setWeekLabel(days) {
    var labelEl = document.getElementById("calendar-week-label");
    if (!labelEl || !days || !days.length) return;
    labelEl.innerText = days[0].date_key + " – " + days[days.length - 1].date_key;
}

async function loadWeek(weekStartIso) {
    if (!weekStartIso) return;
    currentWeekStartIso = weekStartIso;

    var data = await request({
        url: "/task/calendar/?week_start=" + encodeURIComponent(weekStartIso),
        method: "GET",
    });

    if (!data || !data.days) return;

    setWeekStructure(data.days);
    setWeekLabel(data.days);

    renderTasksOnCalendar(data.tasks || []);
}

document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener('mousedown', onMouseDown);

    var today = new Date();
    var weekStart = startOfWeekMonday(today);
    loadWeek(formatIsoDate(weekStart));

    var prevBtn = document.getElementById("calendar-prev-week");
    var nextBtn = document.getElementById("calendar-next-week");

    if (prevBtn) {
        prevBtn.addEventListener("click", function() {
            loadWeek(shiftWeek(currentWeekStartIso, -1));
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener("click", function() {
            loadWeek(shiftWeek(currentWeekStartIso, 1));
        });
    }
});
