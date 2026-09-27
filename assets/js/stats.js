/**
 * AutoQuest Live Stats Engine
 * Handles real-time data polling and smooth UI updates
 */
(function () {
    const POLLING_INTERVAL = 30000;
    const API_BASE = window.API_BASE || '';
    let questChart = null;
    let chartKeys = [];            // task types currently rendered (stable order)
    let lastChartSignature = null; // last rendered breakdown, to detect changes

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

    // --- CHART ---
    const CHART_COLORS = [
        '#5865F2', // Discord Blue
        '#3BA55D', // Discord Green
        '#FAA61A', // Discord Yellow
        '#EB459E', // Activity Pink
        '#ED4245', // Discord Red
        '#00A8FC', // Link Blue
        '#9B59B6'  // Purple
    ];
    const chartColorMap = new Map(); // task type -> stable color
    const chartColor = (key) => {
        if (!chartColorMap.has(key)) {
            chartColorMap.set(key, CHART_COLORS[chartColorMap.size % CHART_COLORS.length]);
        }
        return chartColorMap.get(key);
    };

    const formatChartLabel = (key) => key.replace(/_/g, ' ').toUpperCase();

    const breakdownSignature = (breakdown) =>
        JSON.stringify(Object.keys(breakdown).sort().map(k => [k, breakdown[k]]));

    // Merge incoming task types into the rendered key list, preserving order so
    // arcs never get shuffled between refreshes (colors stay bound to a type).
    const chartSeries = (breakdown) => {
        Object.keys(breakdown).forEach(k => {
            if (!chartKeys.includes(k)) chartKeys.push(k);
        });
        return {
            labels: chartKeys.map(formatChartLabel),
            values: chartKeys.map(k => breakdown[k] || 0),
            colors: chartKeys.map(chartColor)
        };
    };

    // Animate the existing chart into the new values instead of rebuilding it,
    // so refreshes morph smoothly and the entrance animation never replays.
    const applyChartData = (breakdown) => {
        const { labels, values, colors } = chartSeries(breakdown);
        questChart.data.labels = labels;
        questChart.data.datasets[0].data = values;
        questChart.data.datasets[0].backgroundColor = colors;
        questChart.options.animation = { duration: 900, easing: 'easeOutQuart' };
        questChart.update();
    };

    const initChart = (ctx, breakdown) => {
        if (questChart) questChart.destroy();

        const { labels, values, colors } = chartSeries(breakdown);

        questChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false, // first paint is static; later refreshes morph
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
                        displayColors: false,
                        callbacks: {
                            label: (ctx) => ` ${ctx.formattedValue} quests`
                        }
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
        // "Users" = real users with at least one healthy active token
        // (fall back to the historical unique-user count for older API responses)
        const realUsers = data.active_users !== undefined ? data.active_users : data.total_users;
        animateValue('stat-users', realUsers || 0);
        animateValue('stat-quests', data.total_quests_completed || 0);
        animateValue('stat-servers', data.guild_count || 0);
        animateValue('stat-active', data.active_sessions || 0);
        
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
        const breakdown = data.quest_type_breakdown || {};
        if (chartCtx && Object.keys(breakdown).length > 0) {
            const signature = breakdownSignature(breakdown);
            if (!questChart) {
                // First paint on page load: render statically (no animation)
                initChart(chartCtx, breakdown);
                lastChartSignature = signature;
            } else if (signature !== lastChartSignature) {
                // Data changed on a refresh: morph smoothly into the new values
                applyChartData(breakdown);
                lastChartSignature = signature;
            }
        } else if (chartCtx) {
            // Handle empty state - maybe clear chart or show message
            if (questChart) {
                questChart.destroy();
                questChart = null;
            }
            chartKeys = [];
            lastChartSignature = null;
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
