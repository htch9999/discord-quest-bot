/**
 * AutoQuest Live Stats Engine
 * Handles real-time data polling and smooth UI updates
 */
(function () {
    const POLLING_INTERVAL = 30000;
    const API_BASE = window.API_BASE || '';
    let questChart = null;

    // --- UTILITIES ---
    const formatNumber = (n) => {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return n.toLocaleString();
    };

    const formatUptime = (seconds) => {
        const d = Math.floor(seconds / 86400);
        const h = Math.floor((seconds % 86400) / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (d > 0) return `${d}d ${h}h`;
        if (h > 0) return `${h}h ${m}m`;
        return `${m}m`;
    };

    const formatTime = (date) => {
        return new Intl.DateTimeFormat(undefined, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    };

    // --- ANIMATIONS ---
    const animateValue = (id, end, prefix = '', suffix = '', formatter = formatNumber) => {
        const el = document.getElementById(id);
        if (!el) return;

        const start = parseInt(el.textContent.replace(/[^0-9]/g, '')) || 0;
        if (start === end) return;

        const duration = 1500;
        let startTimestamp = null;

        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const current = Math.floor(progress * (end - start) + start);
            
            el.textContent = `${prefix}${formatter(current)}${suffix}`;
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = `${prefix}${formatter(end)}${suffix}`;
            }
        };

        window.requestAnimationFrame(step);
    };

    const toggleSkeletons = (show) => {
        document.querySelectorAll('.stat-card, .dashboard-card').forEach(card => {
            if (show) card.classList.add('loading');
            else card.classList.remove('loading');
        });
    };

    const initChart = (ctx, data) => {
        if (questChart) questChart.destroy();
        
        const labels = Object.keys(data).map(k => k.replace(/_/g, ' ').toUpperCase());
        const values = Object.values(data);

        questChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: [
                        '#5865F2', // Discord Blue
                        '#3BA55D', // Discord Green
                        '#FAA61A', // Discord Yellow
                        '#EB459E', // Activity Pink
                        '#ED4245'  // Discord Red
                    ],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#b9bbbe',
                            padding: 20,
                            font: { size: 11, family: 'Inter' },
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: '#18191c',
                        titleFont: { size: 12 },
                        bodyFont: { size: 12 },
                        padding: 10,
                        displayColors: false
                    }
                },
                cutout: '75%'
            }
        });
    };

    // --- ENGINE ---
    const updateUI = (data) => {
        toggleSkeletons(false);

        // Core Statistics
        animateValue('stat-users', data.total_users || 0);
        animateValue('stat-quests', data.total_quests_completed || 0);
        animateValue('stat-servers', data.guild_count || 0);
        
        // Static strings
        const uptimeEl = document.getElementById('stat-uptime');
        if (uptimeEl) {
            uptimeEl.textContent = formatUptime(data.uptime_seconds || 0);
        }

        // Dashboard specific items
        if (data.quests_today !== undefined) animateValue('dash-today', data.quests_today);
        if (data.quests_this_week !== undefined) animateValue('dash-week', data.quests_this_week);
        
        // Ping handling
        const pingEl = document.getElementById('stat-ping');
        if (pingEl && data.bot_ping_ms !== undefined) {
            pingEl.textContent = data.bot_ping_ms >= 0 ? `${data.bot_ping_ms}ms` : 'N/A';
        }

        // Chart Rendering
        const chartCtx = document.getElementById('questBreakdownChart');
        if (chartCtx && data.quest_type_breakdown && Object.keys(data.quest_type_breakdown).length > 0) {
            initChart(chartCtx, data.quest_type_breakdown);
        } else if (chartCtx) {
            // Handle empty state - maybe clear chart or show message
            if (questChart) questChart.destroy();
            const ctx = chartCtx.getContext('2d');
            ctx.clearRect(0,0, chartCtx.width, chartCtx.height);
            ctx.fillStyle = '#b9bbbe';
            ctx.textAlign = 'center';
            ctx.font = '12px Inter';
            ctx.fillText('No data available yet', chartCtx.width/2, chartCtx.height/2);
        }

        // Timestamp
        const syncEl = document.getElementById('last-sync');
        if (syncEl) {
            syncEl.textContent = formatTime(new Date());
        }
    };

    async function poll() {
        const currentBase = window.API_BASE;
        if (!currentBase) {
            console.warn('[AutoQuest] window.API_BASE not configured, skipping poll');
            return;
        }
        
        try {
            const url = currentBase.endsWith('/') ? `${currentBase}v1/stats/public` : `${currentBase}/v1/stats/public`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
            const data = await response.json();
            updateUI(data);
        } catch (error) {
            console.error('[AutoQuest] Polling failed:', error.message);
            // Show stale data or error state if needed
            const syncEl = document.getElementById('last-sync');
            if (syncEl) syncEl.textContent = 'Offline';
        }
    }

    // Initialize
    window.addEventListener('DOMContentLoaded', () => {
        poll();
        setInterval(poll, POLLING_INTERVAL);
    });

})();
