let chartsState = {};

export function createChart(containerId, data, colors, labels) {
    const svgWidth = document.getElementById(containerId).clientWidth;
    const svgHeight = document.getElementById(containerId).clientHeight;
    const margin = { top: 30, right: 30, bottom: 40, left: 50 };
    const width = svgWidth - margin.left - margin.right;
    const height = svgHeight - margin.top - margin.bottom;

    if (!chartsState[containerId]) {
        chartsState[containerId] = {
            zoom: null,
            currentZoomState: null,
            data: data,
        };
    }

    const svg = d3.select(`#${containerId}`)
        .append("svg")
        .attr("width", svgWidth)
        .attr("height", svgHeight)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    svg.append("defs")
        .append("clipPath")
        .attr("id", "clip")
        .append("rect")
        .attr("width", width)
        .attr("height", height);

// src/napview/core/static/d3_chart.js

svg.append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", 0 - margin.left)
    .attr("x", 0 - height / 2)
    .attr("dy", "1em")
    .style("text-anchor", "middle")
    .style("fill", "#ffffff") // White text
    .text(labels[0]);

svg.append("text")
    .attr("x", width / 2)
    .attr("y", height + (margin.bottom * 0.9))
    .style("text-anchor", "middle")
    .style("fill", "#ffffff") // White text
    .text("Time");


    // svg.append("text")
    //     .attr("transform", "rotate(-90)")
    //     .attr("y", 0 - margin.left)
    //     .attr("x", 0 - height / 2)
    //     .attr("dy", "1em")
    //     .style("text-anchor", "middle")
    //     .text(labels[0]);

    // svg.append("text")
    //     .attr("x", width / 2)
    //     .attr("y", height + (margin.bottom * 0.9))
    //     .style("text-anchor", "middle")
    //     .text("Time");

    const numberOfXTicks = Math.max(3, Math.min(6, Math.floor(width / 100)));
    const numberOfYTicks = Math.max(3, Math.min(6, Math.floor(height / 30)));

    const dataMax = d3.max(data.flat(), d => d.x);
    const dataMin = d3.min(data.flat(), d => d.x);

    const xScale = d3.scaleTime()
        .domain([new Date(dataMin), new Date(dataMax)])
        .range([0, width]);

    const yScale = d3.scaleLinear()
        .domain([0, d3.max(data.flat(), d => d.y)])
        .range([height, 0]);

    const xAxis = d3.axisBottom(xScale)
        .ticks(numberOfXTicks)
        .tickFormat(d3.timeFormat("%H:%M:%S"))
        .tickSize(-height);

    const yAxis = d3.axisLeft(yScale)
        .ticks(numberOfYTicks)
        .tickSize(-width);

    const gX = svg.append("g")
        .attr("class", "x-axis grid")
        .attr("transform", `translate(0,${height})`)
        .call(xAxis);

    const gY = svg.append("g")
        .attr("class", "y-axis grid")
        .call(yAxis);

    const line = d3.line()
        .x(d => xScale(new Date(d.x)))
        .y(d => yScale(d.y))
        .curve(d3.curveLinear);

    data.forEach((lineData, i) => {
        svg.append("path")
            .datum(lineData)
            .attr("fill", "none")
            .attr("stroke", colors[i])
            .attr("stroke-width", 1.5)
            .attr("class", "line")
            .attr("clip-path", "url(#clip)")
            .attr("d", line);
    });

    const zoom = d3.zoom()
        .scaleExtent([0, Infinity])
        .translateExtent([[0, 0], [width, height]])
        .on("zoom", zoomed);

    svg.append("rect")
        .attr("width", width)
        .attr("height", height)
        .style("fill", "none")
        .style("pointer-events", "all")
        .call(zoom);

    addLegend(svg, width, height, labels, colors);

    function updateChart(data) {
        chartsState[containerId].data = data;

        let newXScale;
        if (chartsState[containerId].currentZoomState) {
            newXScale = chartsState[containerId].currentZoomState.rescaleX(xScale);
        } else {
            newXScale = xScale;
        }
        
        const oldDomainStart = newXScale.domain()[0].getTime();
        const oldDomainEnd = newXScale.domain()[1].getTime();
        const latestDataPoint = d3.max(data.flat(), d => d.x);
        const domainShift = latestDataPoint - oldDomainEnd;
        newXScale.domain([oldDomainStart + domainShift, latestDataPoint]);
    
        gX.call(xAxis.scale(newXScale));
    
        const line = d3.line()
            .x(d => newXScale(d.x))
            .y(d => yScale(d.y))
            .curve(d3.curveLinear);

        svg.selectAll(".line")
            .attr("d", (d, i) => line(data[i]));
    
        yScale.domain([0, d3.max(data.flat(), d => d.y)]);
        gY.call(yAxis.scale(yScale));
    }

    function zoomed(event) {
        const transform = event.transform;
        chartsState[containerId].currentZoomState = transform;

        const data = chartsState[containerId].data;
        let newXScale = transform.rescaleX(xScale);
        const newDomainStart = newXScale.domain()[0].getTime();
        const newDomainEnd = newXScale.domain()[1].getTime();
        const latestDataPoint = d3.max(data.flat(), d => d.x);
        const domainShift = latestDataPoint - newDomainEnd;
        newXScale.domain([newDomainStart + domainShift, latestDataPoint]);

        gX.call(xAxis.scale(newXScale));
        const line = d3.line()
            .x(d => newXScale(d.x))
            .y(d => yScale(d.y))
            .curve(d3.curveLinear);
        svg.selectAll(".line")
            .attr("d", (d, i) => line(data[i]));

        // call the zoomed function for all charts
        Object.keys(chartsState).forEach(id => {
            if (id !== containerId) {
                const chart = chartsState[id];
                chart.currentZoomState = transform;
                chart.zoomed({ transform });
            }
        });
    }

    return { svg, data, xScale, yScale, xAxis, yAxis, gX, gY, containerId, update: updateChart, zoomed };
}


// export function addLegend(svg, width, height, labels, colors) {
//     const legendWidth = width * 0.15;
//     const itemSpacing = width * 0.02;
//     const itemWidth = width * 0.02;
//     const itemHeight = width * 0.02;
//     const labelOffset = width * 0.03;
//     const labelFontSize = width * 0.025;
//     const legendPadding = width * 0.01;

//     const legendHeight = (labels.length - 2) * (itemHeight + itemSpacing) + legendPadding * 2;
//     const legendX = width * 0.01;
//     const legendY = height * 0.05;

//     const legend = svg.append("g")
//         .attr("class", "legend")
//         .attr("transform", `translate(${legendX}, ${legendY})`);

//     legend.append("rect")
//         .attr("width", legendWidth)
//         .attr("height", legendHeight)
//         .attr("fill", "white")
//         .attr("fill-opacity", 0.8);

//     const legendItems = legend.selectAll(".legend-item")
//         .data(labels.slice(2))
//         .enter()
//         .append("g")
//         .attr("class", "legend-item")
//         .attr("transform", (d, i) => `translate(${legendWidth / 8}, ${i * (itemSpacing + itemHeight) + legendPadding})`);

//     legendItems.append("rect")
//         .attr("x", 0)
//         .attr("y", 0)
//         .attr("width", itemWidth)
//         .attr("height", itemHeight)
//         .attr("fill", (d, i) => colors[i]);

//     legendItems.append("text")
//         .attr("x", labelOffset)
//         .attr("y", itemHeight)
//         .attr("font-size", `${labelFontSize}px`)
//         .attr("alignment-baseline", "middle")
//         .text(d => d);
// }


export function addLegend(svg, width, height, labels, colors) {
    const legendWidth = width * 0.15;
    const itemSpacing = width * 0.02;
    const itemWidth = width * 0.02;
    const itemHeight = width * 0.02;
    const labelOffset = width * 0.03;
    const labelFontSize = width * 0.025;
    const legendPadding = width * 0.01;

    const legendHeight = (labels.length - 2) * (itemHeight + itemSpacing) + legendPadding * 2;
    const legendX = width * 0.01;
    const legendY = height * 0.05;

    const legend = svg.append("g")
        .attr("class", "legend")
        .attr("transform", `translate(${legendX}, ${legendY})`);

    legend.append("rect")
        .attr("width", legendWidth)
        .attr("height", legendHeight)
        .attr("fill", "#1e1e1e") // Ensure the background is dark
        .attr("fill-opacity", 0.8);

    const legendItems = legend.selectAll(".legend-item")
        .data(labels.slice(2))
        .enter()
        .append("g")
        .attr("class", "legend-item")
        .attr("transform", (d, i) => `translate(${legendWidth / 8}, ${i * (itemSpacing + itemHeight) + legendPadding})`);

    legendItems.append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", itemWidth)
        .attr("height", itemHeight)
        .attr("fill", (d, i) => colors[i]) // Ensure this uses the correct color
        .attr("stroke", "#ffffff") // Optional: Add a white stroke for better visibility
        .attr("stroke-width", 0.5); // Optional: Stroke width

    legendItems.append("text")
        .attr("x", labelOffset)
        .attr("y", itemHeight / 2)
        .attr("font-size", `${labelFontSize}px`)
        .attr("alignment-baseline", "middle")
        .attr("fill", "#ffffff") // Ensure text is visible
        .text(d => d);
}