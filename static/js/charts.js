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

function renderStockOverlayChart() {
  var canvas = document.getElementById("stock-overlay-chart");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  var priceData = parseJsonScript("price-chart-data") || [];
  var interestData = parseJsonScript("interest-chart-data") || [];
  if (!priceData.length && !interestData.length) {
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

  new Chart(canvas.getContext("2d"), {
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
          tension: 0.2,
        },
        {
          label: "관심도",
          data: interestSeries,
          borderColor: "#b45309",
          backgroundColor: "rgba(180, 83, 9, 0.14)",
          yAxisID: "y1",
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          position: "left",
          title: {display: true, text: "Price"},
        },
        y1: {
          position: "right",
          grid: {drawOnChartArea: false},
          title: {display: true, text: "Interest"},
        },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", function () {
  renderStockOverlayChart();
});

document.body.addEventListener("htmx:afterSwap", function () {
  renderStockOverlayChart();
});
