document.addEventListener("DOMContentLoaded", function () {
    const ctx = document.getElementById('priceChart');
    if (!ctx) return;

    fetch('/api/price-history')
        .then(response => response.json())
        .then(data => {
            const labels = data.map(item => item.time);
            const prices = data.map(item => item.price);

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'KTX Price ($USD)',
                        data: prices,
                        borderColor: '#22D3EE',
                        backgroundColor: 'rgba(34, 211, 238, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { labels: { color: '#9CA3AF' } }
                    },
                    scales: {
                        x: { ticks: { color: '#9CA3AF' }, grid: { color: '#262626' } },
                        y: { ticks: { color: '#9CA3AF' }, grid: { color: '#262626' } }
                    }
                }
            });
        });
});