document.addEventListener('DOMContentLoaded', () => {
    // 1. Smooth scroll for anchor links (Optional, CSS scroll-behavior: smooth covers most)
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // 2. Lightbox Logic (Legacy, consider moving to Alpine later)
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox';
    lightbox.innerHTML = `
        <span class="close-lightbox">&times;</span>
        <img class="lightbox-content" id="lightbox-img">
    `;
    document.body.appendChild(lightbox);

    const lightboxImg = document.getElementById('lightbox-img');
    const closeBtn = document.querySelector('.close-lightbox');

    // Event Delegation for Lightbox (Works for new HTMX items too)
    document.body.addEventListener('click', (e) => {
        if (e.target.classList.contains('timeline-image') || e.target.classList.contains('gallery-image')) {
            // Fix: Don't open simple lightbox if it's an Archive item OR Timeline item (both have their own modal now)
            if (e.target.closest('.masonry-item') || e.target.closest('.timeline-item')) {
                return;
            }

            lightbox.style.display = 'block';
            lightboxImg.src = e.target.src;
            document.body.style.overflow = 'hidden';
        }
    });

    const closeLightbox = () => {
        lightbox.style.display = 'none';
        document.body.style.overflow = 'auto';
    };

    if (closeBtn) closeBtn.addEventListener('click', closeLightbox);

    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLightbox();
        }
    });
});

// Helper for 'On This Day' link (scrollToEvent)
function scrollToEvent(dateStr) {
    const element = document.querySelector(`.timeline-item[data-date="${dateStr}"]`);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.classList.add('highlight-glow');
        setTimeout(() => element.classList.remove('highlight-glow'), 2000);
    } else {
        window.location.href = `/?date=${dateStr}#timeline`;
    }
}

// --- Detailed Modal Logic (Global) ---
async function openDetailModal(eventId) {
    const modal = document.getElementById('detailModal');
    if (!modal) return;

    // Show Loading
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch(`/api/events/${eventId}`);
        const data = await res.json();

        // Populate Data
        const dateEl = document.getElementById('detailDate');
        if (dateEl) dateEl.textContent = data.date;

        const locEl = document.getElementById('detailLocation');
        if (locEl) {
            locEl.textContent = data.location || "";
            // Reset state
            locEl.style.cursor = 'default';
            locEl.onclick = null;
            locEl.classList.remove('has-coords');

            // Interactive Map Trigger
            if (data.lat && data.lng) {
                locEl.style.cursor = 'pointer';
                locEl.title = "Click to view on map";
                locEl.classList.add('has-coords');
                locEl.onclick = (e) => {
                    e.stopPropagation(); // Prevent propagation if needed
                    // defined in map_modal.html
                    if (typeof openMapModal === 'function') {
                        openMapModal(data.lat, data.lng, data.id);
                    } else {
                        console.error("Map Modal function not found");
                    }
                };
            }
        }

        const weatherEl = document.getElementById('detailWeather');
        if (weatherEl) weatherEl.textContent = data.weather || "";

        // Media
        const mediaContainer = document.getElementById('modalMedia');
        if (mediaContainer) {
            mediaContainer.innerHTML = '';
            if (data.media_type === 'video') {
                mediaContainer.innerHTML = `<video src="${data.image_url}" controls autoplay style="width:100%; height:100%"></video>`;
            } else {
                mediaContainer.innerHTML = `<img src="${data.image_url}" alt="${data.title || ''}">`;
            }
        }

        // Story Logic
        const storyEl = document.getElementById('detailStory');
        const authorEl = document.getElementById('detailAuthor');
        const summaryEl = document.getElementById('detailSummary');

        if (storyEl) {
            if (data.user_memory) {
                storyEl.textContent = data.user_memory;
                if (authorEl) {
                    authorEl.textContent = data.user_memory_author ? `- ${data.user_memory_author} -` : "";
                    authorEl.style.display = 'block';
                }
                if (summaryEl) {
                    summaryEl.style.display = 'none';
                    if (data.summary) {
                        summaryEl.textContent = "AI Analysis: " + data.summary.split('\n')[0];
                        summaryEl.style.display = 'block';
                    }
                }
            } else {
                // AI Caption Only
                storyEl.textContent = data.summary ? (data.summary.split('\n\n')[1] || data.summary) : "No details.";
                if (authorEl) authorEl.style.display = 'none';
                if (summaryEl) summaryEl.style.display = 'none';
            }
        }

        // People
        const peopleWrapper = document.getElementById('detailPeopleWrapper');
        const peopleContainer = document.getElementById('detailPeople');

        if (peopleContainer) {
            peopleContainer.innerHTML = '';
            if (data.people && data.people.length > 0) {
                if (peopleWrapper) peopleWrapper.style.display = 'block';
                if (peopleWrapper) peopleWrapper.style.display = 'block';

                // Emotion Mapping
                const emotionMap = {
                    'happy': '😄',
                    'sad': '😢',
                    'angry': '😠',
                    'surprise': '😲',
                    'fear': '😱',
                    'disgust': '🤢',
                    'neutral': ''
                };

                data.people.forEach(person => {
                    const chip = document.createElement('span');
                    chip.className = 'people-tag';

                    // Handle Object {name, emotion} or legacy string
                    let name = typeof person === 'string' ? person : person.name;
                    let emotion = (typeof person === 'object' && person.emotion) ? person.emotion : null;

                    let emoji = "";
                    if (emotion && emotionMap[emotion]) {
                        emoji = ` <span title="${emotion}">${emotionMap[emotion]}</span>`;
                    }

                    chip.innerHTML = `${name}${emoji}`;
                    peopleContainer.appendChild(chip);
                });
            } else {
                if (peopleWrapper) peopleWrapper.style.display = 'none';
            }
        }

        // Weather Wrapper Visibility
        const weatherWrapper = document.getElementById('detailWeatherWrapper');
        if (weatherWrapper) {
            if (data.weather) {
                weatherWrapper.style.display = 'block';
            } else {
                weatherWrapper.style.display = 'none';
            }
        }

    } catch (e) {
        console.error("Failed to load details", e);
        alert("Details not available.");
        closeModal();
    }
}

function closeModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
        const mediaContainer = document.getElementById('modalMedia');
        if (mediaContainer) mediaContainer.innerHTML = ''; // Stop video
    }
}

// Close on click outside
window.addEventListener('click', function (event) {
    const modal = document.getElementById('detailModal');
    if (event.target == modal) {
        closeModal();
    }
});

// Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});
// --- Stack Modal Logic ---
async function openStackModal(stackId, e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    const modal = document.getElementById('stackModal');
    const container = document.getElementById('stackGridContainer');

    if (!modal || !container) return;

    // Show Modal & Loader
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    container.innerHTML = '<div class="spinner"></div> Loading stack...';

    try {
        const res = await fetch(`/api/events/stack/${stackId}`);
        if (res.ok) {
            const html = await res.text();
            container.innerHTML = html;
        } else {
            container.innerHTML = '<p class="text-center text-red-500">Failed to load stack.</p>';
        }
    } catch (err) {
        console.error("Stack load error:", err);
        container.innerHTML = '<p class="text-center text-red-500">Error loading stack.</p>';
    }
}
