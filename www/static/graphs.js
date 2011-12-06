
function humanizeTime(seconds) {
  var interval = Math.floor(seconds / 31536000);
  if (interval > 1) {
    return interval + " years";
  }
  interval = Math.floor(seconds / 2592000);
  if (interval > 1) {
    return interval + " months";
  }
  interval = Math.floor(seconds / 86400);
  if (interval > 1) {
    return interval + " days";
  }
  interval = Math.floor(seconds / 3600);
  if (interval > 1) {
    return interval + " hours";
  }
  interval = Math.floor(seconds / 60);
  if (interval > 1) {
    return interval + " minutes";
  }
  return Math.floor(seconds) + " seconds";
}

function bargraph(data, target, options){
  if(!options){ 
    options = {}
  }
  charttop = d3.select(target)
     .append("svg:svg")
       .attr("class", "chart")
       .attr("width", 700)
       .attr("height", 20 * data.length + 15)
  var chart = charttop.append("svg:g")
      .attr("transform", "translate(100,15)");
  var points = $.map(data, function(x,z){return x[1]})
  var x = d3.scale.linear()
    .domain([0, d3.max(points)])
       .range([0, 350]);



  //tick the X axis
   chart.selectAll("line").data(x.ticks(10))
     .enter().append("svg:line")
       .attr("x1", x)
       .attr("x2", x)
       .attr("y1", 0)
       .attr("y2", 20*data.length)
       .attr("stroke", "#888");

  var rows = chart.selectAll("rect.bar").data(data).enter().append("svg:rect")
    .attr("class","bar")
    .attr("y", function(d, i) { return i * 20; })
    .attr("width", function(d,i){return x(d[1]);})
    .attr("height", 20)
    .attr("x", 0)

  charttop.selectAll("innerlabel").data(data).enter().append("svg:text")
    .attr("class","innerlabel")
    .attr("y", function(d, i) { return i * 20 + 30; })
    .attr("height", 20)
    .attr("x", function(d,i){return x(d[1]) + 100;})
    .attr("dx", function(d,i){return -5;})
    .attr("text-anchor", "end") // text-align: right
    .text(
        'labelfunc' in options ? options.labelfunc : function(d,i){ return d[1] > 0 ? d[1] : ""}
    )

  var labels = charttop.selectAll("xlabel").data(data).enter().append("svg:text")
    .attr("class","xlabel")
    .attr("y", function(d, i) { return i * 20 + 30; })
    .attr("height", 20)
    .attr("x", function(d,i){return 100;})
    .attr("dx", function(d,i){return -5;})
    .attr("text-anchor", "end") // text-align: right
    .text(function(d,i){ return d[0];})

}


