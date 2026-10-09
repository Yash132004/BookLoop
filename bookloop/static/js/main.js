// Close the mobile navigation after a visitor selects a page link.
document.addEventListener('DOMContentLoaded', () => {
    const navigation = document.getElementById('mainNavigation');

    if (navigation && window.bootstrap) {
        navigation.querySelectorAll('a.nav-link').forEach((link) => {
            link.addEventListener('click', () => {
                if (window.matchMedia('(max-width: 991.98px)').matches) {
                    window.bootstrap.Collapse.getOrCreateInstance(navigation).hide();
                }
            });
        });
    }

    setupLiveBookSearch();
    setupLiveBookImageSearch();
});

function setupLiveBookSearch() {
    const form = document.getElementById('book-search-form');
    const results = document.getElementById('book-results');
    const status = document.getElementById('book-search-status');
    const clearLink = document.getElementById('book-search-clear');

    if (!form || !results || !status || !window.fetch || !window.AbortController) {
        return;
    }

    const searchInput = form.querySelector('[name="q"]');
    const clearButton = form.querySelector('#book-search-clear');
    let debounceTimer;
    let activeController;
    let requestVersion = 0;
    let imageSearchActive = false;

    window.setBookImageSearchActive = (active) => {
        imageSearchActive = active;
        if (active) {
            window.clearTimeout(debounceTimer);
            requestVersion += 1;
            activeController?.abort();
            activeController = null;
            results.setAttribute('aria-busy', 'false');
        }
    };

    const syncUrl = () => {
        const query = new URLSearchParams(new FormData(form));
        const queryString = query.toString();
        const nextUrl = `${window.location.pathname}${queryString ? `?${queryString}` : ''}`;
        window.history.replaceState(null, '', nextUrl);
    };

    const updateClearButton = () => {
        const hasFilters = Array.from(form.elements).some((field) => (
            field.name && field.value.trim()
        ));
        clearButton?.classList.toggle('d-none', !hasFilters);
    };

    const search = async (version) => {
        if (imageSearchActive) {
            return;
        }
        const controller = new AbortController();
        activeController = controller;
        results.setAttribute('aria-busy', 'true');
        status.textContent = 'Searching books…';

        const query = new URLSearchParams(new FormData(form));
        const endpoint = new URL(results.dataset.searchUrl, window.location.origin);
        endpoint.search = query.toString();

        try {
            const response = await fetch(endpoint, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'text/html',
                },
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error('Search request failed.');
            }

            const resultHtml = await response.text();
            if (version !== requestVersion) {
                return;
            }

            results.replaceChildren();
            results.insertAdjacentHTML('afterbegin', resultHtml);
            status.textContent = '';
        } catch (error) {
            if (error.name === 'AbortError' || version !== requestVersion) {
                return;
            }
            status.textContent = 'Search is temporarily unavailable. Please try again.';
        } finally {
            if (version === requestVersion) {
                results.setAttribute('aria-busy', 'false');
                activeController = null;
            }
        }
    };

    const scheduleSearch = (delay = 400) => {
        imageSearchActive = false;
        document.dispatchEvent(new Event('bookloop:text-search-start'));
        window.clearTimeout(debounceTimer);
        requestVersion += 1;
        activeController?.abort();
        syncUrl();
        updateClearButton();
        const version = requestVersion;
        debounceTimer = window.setTimeout(() => search(version), delay);
    };

    searchInput?.addEventListener('input', () => scheduleSearch());
    form.querySelectorAll('select, input:not([type="search"])').forEach((field) => {
        field.addEventListener('change', () => scheduleSearch());
        if (field.type === 'text') {
            field.addEventListener('input', () => scheduleSearch());
        }
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        scheduleSearch(0);
    });

    clearLink?.addEventListener('click', (event) => {
        event.preventDefault();
        form.querySelectorAll('input').forEach((field) => {
            field.value = '';
        });
        form.querySelectorAll('select').forEach((field) => {
            field.selectedIndex = 0;
        });
        scheduleSearch(0);
    });

    window.addEventListener('popstate', () => {
        const query = new URLSearchParams(window.location.search);
        form.querySelectorAll('[name]').forEach((field) => {
            field.value = query.get(field.name) || '';
        });
        updateClearButton();
        scheduleSearch(0);
    });
}

function setupLiveBookImageSearch() {
    const form = document.getElementById('book-image-search-form');
    const input = document.getElementById('book-image-search');
    const filterForm = document.getElementById('book-search-form');
    const results = document.getElementById('book-results');
    const status = document.getElementById('book-search-status');

    if (!form || !input || !filterForm || !results || !status || !window.fetch) {
        return;
    }

    let activeController;
    let requestVersion = 0;

    document.addEventListener('bookloop:text-search-start', () => {
        requestVersion += 1;
        activeController?.abort();
        activeController = null;
        input.value = '';
    });

    input.addEventListener('change', () => {
        if (input.files && input.files.length) {
            searchSelectedImage();
        }
    });

    async function searchSelectedImage() {
        const file = input.files[0];
        const version = ++requestVersion;
        activeController?.abort();
        activeController = new AbortController();
        window.setBookImageSearchActive?.(true);

        // Make the active search mode visible in the URL and form controls.
        filterForm.querySelector('[name="q"]').value = '';
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.delete('q');
        window.history.replaceState(null, '', `${nextUrl.pathname}${nextUrl.search}`);

        const payload = new FormData(form);
        input.value = '';
        const condition = filterForm.querySelector('[name="condition"]');
        const location = filterForm.querySelector('[name="location"]');
        if (condition) payload.append('condition', condition.value);
        if (location) payload.append('location', location.value);

        results.setAttribute('aria-busy', 'true');
        status.textContent = 'Searching BookLoop covers…';

        try {
            const response = await fetch(results.dataset.imageSearchUrl, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'text/html',
                },
                body: payload,
                signal: activeController.signal,
            });
            if (!response.ok) {
                throw new Error('Image search request failed.');
            }
            const resultHtml = await response.text();
            if (version !== requestVersion) return;

            results.replaceChildren();
            results.insertAdjacentHTML('afterbegin', resultHtml);
            status.textContent = results.querySelector('.empty-books')
                ? 'No matching books found. Try another cover image.'
                : `Image matches for ${file.name}`;
        } catch (error) {
            if (error.name !== 'AbortError' && version === requestVersion) {
                status.textContent = 'Image search is temporarily unavailable. Please try again.';
            }
        } finally {
            if (version === requestVersion) {
                results.setAttribute('aria-busy', 'false');
                activeController = null;
            }
        }
    }
}
