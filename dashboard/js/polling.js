(function() {
    const POLL_INTERVAL_MS = 3000;
    const locationToElementId = {
        // Fill in map as needed
    };

    function updateElementTextById(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function updateElementsByDataLocation(location, text) {
        const els = document.querySelectorAll('[data-location="' + location + '"]');
        els.forEach(e => e.textContent = text);
    }

    async function fetchAndUpdate() {
        try {
            const res = await fetch('/api/current_counts', { cache: 'no-store' });
            if (!res.ok) return;
            const counts = await res.json();
            counts.forEach(c => {
                const loc = c.location_id;
                const val = (c.count != null) ? c.count : '';
                if (locationToElementId[loc]) updateElementTextById(locationToElementId[loc], val);
                updateElementTextById('count-' + loc, val);
                updateElementTextById(loc, val);
                updateElementsByDataLocation(loc, val);
            });
        } catch (err) {
            console.error('Error polling current_counts:', err);
        }
    }

    fetchAndUpdate();
    setInterval(fetchAndUpdate, POLL_INTERVAL_MS);
})();
