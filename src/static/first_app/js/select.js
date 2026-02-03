/**
 * Modern "Linear-style" Custom Select
 * Replaces the old glass-morphism style with a clean, professional look.
 */

function initGlassSelect({
    selector = null,
    selectors = [],
    items = [],
    title = "",
    multiple = false,
    value = null,
    values = null,
    dynamicCreate = false,
    url = null,
}) {
    if (selector) {
        const el = document.querySelector(selector);
        if (el) return initInterface({ select: el, title, items, multiple, value, values, dynamicCreate, url });
    } else if (selectors.length > 0) {
        selectors.forEach(s => {
            const el = document.querySelector(s);
            if (el) initInterface({ select: el, title, items, multiple, value, values, dynamicCreate, url });
        });
    }
}

function initInterface({
    select,
    title,
    items,
    multiple = false,
    value = null,
    values = null,
    dynamicCreate = false,
    url = null,
}) {
    // Clear previous content if re-initializing
    select.innerHTML = '';
    select.className = ''; // Reset classes if any

    // Container
    const container = document.createElement('div');
    container.className = 'custom-select-container';
    container.id = select.id ? `select-${select.id}` : '';
    
    // State
    container.items = Array.isArray(items) ? [...items] : [];
    container.values = multiple ? (values || []) : (value ? [value] : []);
    container.multiple = multiple;

    // Label
    if (title) {
        const label = document.createElement('label');
        label.className = 'custom-select-label';
        label.textContent = title;
        container.appendChild(label);
    }

    // Trigger (The box you click)
    const trigger = document.createElement('div');
    trigger.className = 'custom-select-trigger';
    trigger.tabIndex = 0; // Make focusable
    
    const contentSpan = document.createElement('div');
    contentSpan.className = 'custom-select-content';
    trigger.appendChild(contentSpan);

    const arrow = document.createElement('div');
    arrow.className = 'custom-select-arrow';
    arrow.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>`;
    trigger.appendChild(arrow);

    container.appendChild(trigger);

    // Dropdown Menu
    const dropdown = document.createElement('div');
    dropdown.className = 'custom-select-dropdown';
    
    // Search Input
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'custom-select-search';
    searchInput.placeholder = 'Поиск...';
    dropdown.appendChild(searchInput);

    // List Container
    const listContainer = document.createElement('div');
    listContainer.className = 'custom-select-list';
    dropdown.appendChild(listContainer);

    container.appendChild(dropdown);

    // Render Content in Trigger
    const renderTrigger = () => {
        contentSpan.innerHTML = '';
        
        if (container.values.length === 0 || (container.values.length === 1 && container.values[0] === null)) {
            contentSpan.innerHTML = `<span class="placeholder" style="color:var(--text-secondary)">Выбрать...</span>`;
            return;
        }

        if (multiple) {
            container.values.forEach(val => {
                const item = container.items.find(i => i.id == val);
                if (item) {
                    const tag = document.createElement('span');
                    tag.className = 'custom-select-tag';
                    tag.innerHTML = `
                        ${item.name}
                        <span class="tag-remove" data-id="${val}" onclick="event.stopPropagation();">×</span>
                    `;
                    // Add click handler for remove button directly here or delegate
                    tag.querySelector('.tag-remove').addEventListener('click', (e) => {
                        e.stopPropagation();
                        selectItem(val);
                    });
                    contentSpan.appendChild(tag);
                }
            });
        } else {
            const val = container.values[0];
            const item = container.items.find(i => i.id == val);
            if (item) {
                contentSpan.textContent = item.name;
            } else {
                contentSpan.innerHTML = `<span class="placeholder" style="color:var(--text-secondary)">Выбрать...</span>`;
            }
        }
    };

    // Render List
    const renderList = (filterText = '') => {
        listContainer.innerHTML = '';
        const filter = filterText.toLowerCase();
        
        const filtered = container.items.filter(i => (i.name || '').toLowerCase().includes(filter));

        if (filtered.length === 0) {
            if (dynamicCreate && filterText && url) {
                const createOption = document.createElement('div');
                createOption.className = 'custom-select-option create-option';
                createOption.style.color = 'var(--accent-primary)';
                createOption.textContent = `Создать "${filterText}"`;
                createOption.onclick = async (e) => {
                    e.stopPropagation();
                    if (typeof request === 'function') {
                        try {
                            const res = await request({ url, method: 'POST', body: { name: filterText } });
                            if (res && res.id) {
                                container.items.push(res);
                                selectItem(res.id);
                                searchInput.value = '';
                                renderList('');
                            }
                        } catch (err) { console.error(err); }
                    }
                };
                listContainer.appendChild(createOption);
            } else {
                const empty = document.createElement('div');
                empty.className = 'custom-select-empty';
                empty.textContent = 'Нет данных';
                listContainer.appendChild(empty);
            }
            return;
        }

        filtered.forEach(item => {
            const option = document.createElement('div');
            option.className = 'custom-select-option';
            if (container.values.includes(item.id)) {
                option.classList.add('selected');
            }
            option.textContent = item.name;
            option.onclick = (e) => {
                e.stopPropagation();
                selectItem(item.id);
            };
            listContainer.appendChild(option);
        });
    };

    // Select Item Logic
    const selectItem = (id) => {
        if (multiple) {
            const idx = container.values.indexOf(id);
            if (idx > -1) {
                container.values.splice(idx, 1);
            } else {
                container.values.push(id);
            }
        } else {
            container.values = [id];
            closeDropdown();
        }
        renderTrigger();
        renderList(searchInput.value);
    };

    // Open/Close Logic
    const openDropdown = () => {
        document.querySelectorAll('.custom-select-container').forEach(el => el.classList.remove('open'));
        container.classList.add('open');
        searchInput.focus();
        renderList(searchInput.value);
    };

    const closeDropdown = () => {
        container.classList.remove('open');
    };

    const toggleDropdown = () => {
        if (container.classList.contains('open')) closeDropdown();
        else openDropdown();
    };

    // Event Listeners
    trigger.onclick = (e) => {
        // Prevent toggle if clicking on tag remove (handled in renderTrigger)
        if (e.target.closest('.tag-remove')) return;
        toggleDropdown();
    };

    searchInput.onclick = (e) => e.stopPropagation();
    
    searchInput.oninput = (e) => {
        renderList(e.target.value);
    };

    // Initial Render
    renderTrigger();

    // Replace original element with new container
    select.replaceWith(container);

    return container; // Return container to access .values
}

// Global Click Listener to close dropdowns
if (!window.customSelectListenerAdded) {
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            document.querySelectorAll('.custom-select-container.open').forEach(el => {
                el.classList.remove('open');
            });
        }
    });
    window.customSelectListenerAdded = true;
}
