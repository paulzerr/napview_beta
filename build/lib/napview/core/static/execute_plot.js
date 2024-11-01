import { createChart } from './d3_chart.js';

class DataPlotter {
    constructor(chartId, config) {
        this.chartId = chartId;
        this.config = config;
        this.chart = null;
        this.dataSets = null;
    }

    async plotChart() {

            const response = await fetch(this.config.endpoint);
            const data = await response.json();

            this.dataSets = [];
            for (const fieldName of this.config.fields) {
                const fieldData = data[fieldName].map(entry => ({
                    x: entry.x * 1000,
                    y: entry.y
                }));
                this.dataSets.push(fieldData);
            }

            //if (this.hasEnoughData()) {
                
                if (!this.chart) {
                    this.chart = createChart(this.chartId, this.dataSets, this.config.colors, this.config.labels);
                } else {
                    this.chart.update(this.dataSets);
                }
            //}
    }

    hasEnoughData() {
        return this.dataSets && this.dataSets.every(dataSet => dataSet.length >= 2);
    }

    startPlotting(interval = 500) {

        setInterval(() => {
            this.plotChart();
        }, interval);


    }
}

// Configure the charts
const chart1Config = {
    endpoint: '/data1',
    fields: ['n1', 'n2', 'n3', 'rem', 'w'],
    labels: ["probability", "time", "N1", "N2", "N3", "REM", "W"],
    colors: ["#2222ff", "#2ca02c", "#800080", "#d62728", "#ee7f0e"]
};

const chart2Config = {
    endpoint: '/data2',
    fields: ['alpha_power', 'beta_power', 'theta_power', 'delta_power'],
    labels: ["power", "time", 'alpha', 'beta', 'theta', 'delta'],
    colors: ["#2222ff", "#2ca02c", "#800080", "#d62728"]

};

const chart3Config = {
    endpoint: '/data2',
    fields: ['alpha_power', 'beta_power', 'theta_power', 'delta_power'],
    labels: ["power", "time", 'alpha', 'beta', 'theta', 'delta'],
    colors: ["#2222ff", "#2ca02c", "#800080", "#d62728"]

};

const chart4Config = {
    endpoint: '/data1',
    fields: ['n1', 'n2', 'n3', 'rem', 'w'],
    labels: ["probability", "time", "N1", "N2", "N3", "REM", "W"],
    colors: ["#2222ff", "#2ca02c", "#800080", "#d62728", "#ee7f0e"]
};

// Create instances of the DataPlotter class for each chart
const chart1Plotter = new DataPlotter("d3Plot1", chart1Config);
const chart2Plotter = new DataPlotter("d3Plot2", chart2Config);
// const chart3Plotter = new DataPlotter("d3Plot3", chart3Config);
// const chart4Plotter = new DataPlotter("d3Plot4", chart4Config);

// Start plotting for each chart
chart1Plotter.startPlotting();
chart2Plotter.startPlotting();
// chart3Plotter.startPlotting();
// chart4Plotter.startPlotting();
