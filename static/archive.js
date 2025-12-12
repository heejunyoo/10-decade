document.addEventListener('DOMContentLoaded', async () => {
    // --- 1. Read Configuration ---
    const configEl = document.getElementById('archive-config');
    let skip = 0;
    let limit = 20;
    let totalCount = 0;
    let mediaType = '';

    if (configEl) {
        skip = parseInt(configEl.dataset.limit || 0);
        limit = parseInt(configEl.dataset.limit || 20);
        totalCount = parseInt(configEl.dataset.total || 0);
        mediaType = configEl.dataset.type || '';
    }

    // --- 2. Fetch Event Dates (Calendar) ---
    let eventDates = [];
    try {
        const res = await fetch('/api/archive-dates');
        if (res.ok) {
            eventDates = await res.json();
        } else {
            console.warn("Failed to fetch archive dates for calendar.");
        }
    } catch (e) {
        console.error("Error fetching dates:", e);
    }

    // --- 3. Calendar Logic ---
    const calendar = document.getElementById('calendar');
    const currentMonthEl = document.getElementById('currentMonth');
    const prevBtn = document.getElementById('prevMonth');
    const nextBtn = document.getElementById('nextMonth');
    const resetBtn = document.getElementById('resetFilter');
    const galleryItems = document.querySelectorAll('.masonry-item'); // Initial items
    const noPhotosMsg = document.getElementById('noPhotosMsg');

    let currentDate = new Date();
    let selectedDate = null;

    function renderCalendar() {
        if (!calendar) return;

        calendar.innerHTML = '';
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();

        if (currentMonthEl) currentMonthEl.textContent = `${year}.${String(month + 1).padStart(2, '0')}`;

        const firstDay = new Date(year, month, 1).getDay();
        const lastDate = new Date(year, month + 1, 0).getDate();

        // Weekday headers
        const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        weekdays.forEach(day => {
            const el = document.createElement('div');
            el.className = 'calendar-day header';
            el.textContent = day;
            calendar.appendChild(el);
        });

        // Empty slots
        for (let i = 0; i < firstDay; i++) {
            const el = document.createElement('div');
            el.className = 'calendar-day empty';
            calendar.appendChild(el);
        }

        // Days
        for (let i = 1; i <= lastDate; i++) {
            const el = document.createElement('div');
            el.className = 'calendar-day';
            el.textContent = i;

            // Construct strictly as YYYY-MM-DD local string
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;

            // Robust check against string list (No Date object conversion for check)
            if (eventDates.includes(dateStr)) {
                el.classList.add('has-event');
            }

            if (selectedDate === dateStr) {
                el.classList.add('selected');
            }

            el.addEventListener('click', () => {
                selectedDate = dateStr;
                renderCalendar(); // Update UI logic to highlight selected

                if (resetBtn) resetBtn.style.display = 'block';

                filterGallery(dateStr);
            });

            calendar.appendChild(el);
        }
    }

    function filterGallery(date) {
        // Re-query in case more loaded
        const allItems = document.querySelectorAll('.masonry-item');
        let count = 0;

        allItems.forEach(item => {
            if (item.dataset.date === date) {
                item.style.display = 'block';
                count++;
            } else {
                item.style.display = 'none';
            }
        });

        if (noPhotosMsg) {
            noPhotosMsg.style.display = count === 0 ? 'block' : 'none';
        }
    }

    function resetFilter() {
        selectedDate = null;
        renderCalendar();

        const allItems = document.querySelectorAll('.masonry-item');
        allItems.forEach(item => {
            item.style.display = 'block';
        });

        if (noPhotosMsg) noPhotosMsg.style.display = 'none';
        if (resetBtn) resetBtn.style.display = 'none';
    }

    if (prevBtn) prevBtn.addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar();
    });

    if (nextBtn) nextBtn.addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar();
    });

    if (resetBtn) resetBtn.addEventListener('click', resetFilter);

    // Initial Render
    renderCalendar();


    // --- 4. Load More Logic ---
    const loadMoreBtn = document.getElementById('loadMoreArchiveBtn');
    const loadingText = document.getElementById('loadingArchiveText');
    const galleryGrid = document.getElementById('galleryGrid');
    const loadMoreContainer = document.getElementById('loadMoreContainer');

    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            loadMoreBtn.style.display = 'none';
            if (loadingText) loadingText.style.display = 'inline-block';

            const url = `/api/archive-items?skip=${skip}&limit=${limit}${mediaType ? '&media_type=' + mediaType : ''}`;

            fetch(url)
                .then(response => response.text())
                .then(html => {
                    if (html.trim()) {
                        if (galleryGrid) galleryGrid.insertAdjacentHTML('beforeend', html);
                        skip += limit;

                        if (skip >= totalCount) {
                            if (loadMoreContainer) loadMoreContainer.style.display = 'none';
                        } else {
                            loadMoreBtn.style.display = 'inline-block';
                            if (loadingText) loadingText.style.display = 'none';
                        }
                    } else {
                        if (loadMoreContainer) loadMoreContainer.style.display = 'none';
                    }
                })
                .catch(err => {
                    console.error('Error loading more items:', err);
                    loadMoreBtn.style.display = 'inline-block';
                    if (loadingText) loadingText.style.display = 'none';
                });
        });
    }
});
