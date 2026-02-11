var chartInstances = {};

function parseJsonScript(scriptId) {
  var element = document.getElementById(scriptId);
  if (!element) {
    return null;
  }
  try {
    return JSON.parse(element.textContent);
  } catch (error) {
    console.error("Failed to parse chart data:", scriptId, error);
    return null;
  }
}

function destroyChart(chartKey) {
  if (chartInstances[chartKey]) {
    chartInstances[chartKey].destroy();
    delete chartInstances[chartKey];
  }
}

function renderStockOverlayChart() {
  var canvas = document.getElementById("stock-overlay-chart");
  if (!canvas || typeof Chart === "undefined") {
    destroyChart("stockOverlay");
    return;
  }

  var priceData = parseJsonScript("price-chart-data") || [];
  var interestData = parseJsonScript("interest-chart-data") || [];
  if (!priceData.length && !interestData.length) {
    destroyChart("stockOverlay");
    return;
  }

  var interestMap = {};
  for (var i = 0; i < interestData.length; i += 1) {
    interestMap[interestData[i].date] = interestData[i].mentions;
  }

  var labels = [];
  var priceSeries = [];
  var interestSeries = [];

  for (var j = 0; j < priceData.length; j += 1) {
    var point = priceData[j];
    labels.push(point.date);
    priceSeries.push(point.close);
    interestSeries.push(interestMap[point.date] || 0);
  }

  destroyChart("stockOverlay");
  chartInstances.stockOverlay = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Close Price",
          data: priceSeries,
          borderColor: "#1d4ed8",
          backgroundColor: "rgba(29, 78, 216, 0.12)",
          yAxisID: "y",
          tension: 0.2
        },
        {
          label: "Interest",
          data: interestSeries,
          borderColor: "#b45309",
          backgroundColor: "rgba(180, 83, 9, 0.14)",
          yAxisID: "y1",
          tension: 0.2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          position: "left",
          title: { display: true, text: "Price" }
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Interest" }
        }
      }
    }
  });
}

function renderDashboardInterestTimeline() {
  var canvas = document.getElementById("dashboard-interest-timeline-chart");
  if (!canvas || typeof Chart === "undefined") {
    destroyChart("dashboardInterestTimeline");
    return;
  }

  var points = parseJsonScript("dashboard-interest-timeline-data") || [];
  if (!points.length) {
    destroyChart("dashboardInterestTimeline");
    return;
  }

  var labels = [];
  var mentions = [];
  for (var i = 0; i < points.length; i += 1) {
    labels.push(points[i].label);
    mentions.push(points[i].mentions || 0);
  }

  destroyChart("dashboardInterestTimeline");
  chartInstances.dashboardInterestTimeline = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Total Interest",
          data: mentions,
          borderColor: "#0f766e",
          backgroundColor: "rgba(15, 118, 110, 0.14)",
          fill: true,
          tension: 0.25,
          pointRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "Mentions" }
        }
      }
    }
  });
}

function renderCharts() {
  renderStockOverlayChart();
  renderDashboardInterestTimeline();
}

document.addEventListener("DOMContentLoaded", function () {
  renderCharts();
});

if (document.body) {
  document.body.addEventListener("htmx:afterSwap", function () {
    renderCharts();
  });
}
