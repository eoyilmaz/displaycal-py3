// Number methods
p=Number.prototype;
p.accuracy = function(ln) {
	var n = Math.pow(10, ln || 0);
	return Math.round(this * n) / n
};
p.fill=function(ipart, fpart) {
	var i, v=(fpart!=null?this.toFixed(fpart):this+"");
	if ((i = v.indexOf(".")) > -1) ipart+=v.substr(i).length;
	while (v.length<ipart) v=0+v;
	return v
};
p.lead=function(ln) {
	var v=this+"";
	while (v.length<ln+1) v=0+v;
	return v
};

var selected_index = 0;

// Main
function generate_report() {
	var cells = [],
		reference_index = parseInt(Math.floor(rows * cols / 2.0)),
		reference = results[reference_index],
		Ymax = 0,
		delta_cycle = {'E': 'C',
					   /*'C': 'ab',
					   'ab': 'L',*/
					   'C': 'E',
					   'L': 'E'},
		deltas = [],
		curdeltas = [],
		result_delta_E = [],
		delta_E = [],
		T = [],
		tolerance_nominal,
		tolerance_recommended,
		tolerance_nominal_max,
		tolerance_recommended_max,
		delta_E_tolerance_nominal = 4,
		delta_E_tolerance_recommended = 2,
		cls;
	if (delta == 'E' || delta == 'L') {
		// ISO 14861: dE*00 shall be equal or less than four and should be equal or less than two
		tolerance_nominal = tolerance_nominal_max = delta_E_tolerance_nominal;
		tolerance_recommended = tolerance_recommended_max = delta_E_tolerance_recommended;
	}
	else if (delta == 'C') {
		tolerance_nominal_max = 4.5;
		tolerance_recommended_max = 2;
		tolerance_nominal = 3;
		tolerance_recommended = 1;
	}
	else if (delta == 'ab') {
		tolerance_nominal = tolerance_nominal_max = 2;
		tolerance_recommended = tolerance_recommended_max = 1.5;
	}
	// Find brightest point
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			if (results[i][j]['XYZ'][1] > Ymax) Ymax = results[i][j]['XYZ'][1];
		}
	}
	var scale = 100 / Ymax;
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			var XYZ = results[i][j]['XYZ'];
			results[i][j]['XYZ_scaled'] = [scale * XYZ[0], scale * XYZ[1], scale * XYZ[2]];
			results[i][j]['CCT'] = jsapi.math.color.XYZ2CorColorTemp(XYZ[0], XYZ[1], XYZ[2]);
			if (i == reference_index) {
				// Reference white
				results[i][j]['XYZ_100'] = [XYZ[0] / reference[0]['XYZ'][1] * 100,
											XYZ[1] / reference[0]['XYZ'][1] * 100,
											XYZ[2] / reference[0]['XYZ'][1] * 100];
				if (location.search.indexOf('debug') > -1)
					console.log(i, j, 'XYZ', XYZ, '-> XYZ_100', results[i][j]['XYZ_100']);
			}
		}
		// ISO 14861: Calculate 50% gray to white ratio R based on abs. luminance (cd/m2)
		results[i]['R'] = results[i][results[i].length / 2]['XYZ'][1] / results[i][0]['XYZ'][1];
	}
	for (var i = 0; i < rows * cols; i ++) {
		for (var j = 0; j < results[i].length; j ++) {
			var XYZ = results[i][j]['XYZ'],
				XYZ_scaled = results[i][j]['XYZ_scaled'];
			if (i == reference_index) {
				// Reference white
				XYZ_100 = results[i][j]['XYZ_100'];
			}
			else {
				// Scale luminance relative to reference luminance
				results[i][j]['XYZ_100'] = XYZ_100 = [XYZ[0] / reference[0]['XYZ'][1] * 100,
													  XYZ[1] / reference[0]['XYZ'][1] * 100,
													  XYZ[2] / reference[0]['XYZ'][1] * 100];
				if (location.search.indexOf('debug') > -1)
					console.log(i, j, 'XYZ', XYZ, '-> XYZ_100', results[i][j]['XYZ_100']);
			}
			results[i][j]['Lab'] = jsapi.math.color.XYZ2Lab(XYZ_100[0], XYZ_100[1], XYZ_100[2], reference[0]['XYZ_100']);
			if (location.search.indexOf('debug') > -1)
				console.log(i, j, 'XYZ_100', XYZ, '-> L*a*b*', results[i][j]['Lab'], 'ref white', reference[0]['XYZ_100']);
			results[i][j]['Lab_scaled'] = jsapi.math.color.XYZ2Lab(XYZ_scaled[0], XYZ_scaled[1], XYZ_scaled[2], reference[0]['XYZ_100']);
			if (location.search.indexOf('debug') > -1)
				console.log(i, j, 'XYZ_100', XYZ, '-> L*a*b* (scaled)', results[i][j]['Lab_scaled'], 'ref white', reference[0]['XYZ_100']);
		}
		// ISO 14861: Calculate new ratio T by dividing gray/white ratio by reference gray/white ratio, subtracting one and calculating the absolute value
		T.push(Math.abs(results[i]['R'] / reference['R'] - 1));
	}
	for (var i = 0; i < rows * cols; i ++) {
		deltas.push([]);
		curdeltas.push([]);
		result_delta_E.push([]);
		for (var j = 0; j < results[i].length; j ++) {
			var rLab = reference[j]['Lab'],
				Lab = results[i][j]['Lab'],
				curdelta = jsapi.math.color.delta(rLab[0], rLab[1], rLab[2], Lab[0], Lab[1], Lab[2], "2k"),
				delta_ab = [curdelta['a'], curdelta['b']];
			curdelta['ab'] = jsapi.math.max(delta_ab) - jsapi.math.min(delta_ab);
			deltas[i].push(curdelta);
			curdeltas[i].push(curdelta[delta]);
			result_delta_E[i].push(curdelta['E']);
			delta_E.push(curdelta['E']);
		}
	}
	// ISO 14861:2015 tone uniformity
	var delta_E_max = jsapi.math.max(delta_E), delta_E_max_color = '', delta_E_max_mark = ' \u25cf';
	if (delta_E_max <= delta_E_tolerance_recommended)
		delta_E_max_color = 'green';
	else if (delta_E_max <= delta_E_tolerance_nominal)
		delta_E_max_color = 'yellow';
	else
		delta_E_max_color = 'red';
	// ISO 14861:2015 deviation from uniform tonality (contrast deviation)
	// Technically, ISO 12646:2015 has caught up with ISO 14861
	var T_max = jsapi.math.max(T), T_max_color = '', T_max_mark = ' \u25cf',
		T_tolerance_nominal = 0.1;
	if (delta != 'E') 
		T_max_mark = '';
	else if (T_max < T_tolerance_nominal)
		T_max_color = 'green';
	else
		T_max_color = 'red';
	// Generate HTML report
	for (var i = 0; i < rows * cols; i ++) {
		var cellcontent = [],
			Y_diff = [],
			Y_diff_percent = [],
			rgb,
			CCT = [],
			CCT_diff = [],
			CCT_diff_percent = [],
			CT = [],
			CT_diff = [],
			CT_diff_percent = [];
		for (var j = 0; j < results[i].length; j ++) {
			var Lab = results[i][j]['Lab'],
				Lab_scaled = results[i][j]['Lab_scaled'],
				line = '<strong class="rgb_toggle" onclick="window.selected_index = ' + j + '; generate_report()" title="L*a*b* ' + Lab[0].accuracy(2) + ' ' + Lab[1].accuracy(2) + ' ' + Lab[2].accuracy(2) + '">' + (100 - j * 25) + '%:</strong> ' + results[i][j]['XYZ'][1].accuracy(2) + ' cd/m²';
			CCT.push(results[i][j]['CCT']);
			CT.push(results[i][j]['C' + locus.substr(0, 1) + 'T']);
			if (results[i] == reference) {
				line = '</td><td>' + line;
				line += ' (' + (reference[j]['XYZ'][1] / reference[0]['XYZ'][1] * 100).accuracy(2) + '%)' + '</td><td>' + (j == 0 ? '<span id="info_toggle" onclick="document.body.className = document.body.className == &quot;info&quot; ? &quot;toggle&quot; : &quot;info&quot;;" title="Toggle Information Display"><svg width="12" height="12" viewBox="-0.6 -0.6 176 176"><path d="M0,87.7C0,39.2,39.2,0,87.7,0l0,0v15v15c-16,0-30.3,6.4-40.8,16.9l0,0C36.4,57.4,30,71.7,30,87.7l0,0 c0,16,6.4,30.3,16.9,40.8l0,0c10.5,10.5,24.8,16.9,40.8,16.9l0,0c16,0,30.3-6.4,40.8-16.9l0,0c10.5-10.5,16.9-24.8,16.9-40.8l0,0 c0-16-6.4-30.3-16.9-40.8l0,0C118,36.4,103.6,30,87.7,30l0,0V15V0c48.4,0,87.7,39.2,87.7,87.7l0,0c0,48.4-39.2,87.7-87.7,87.7l0,0 C39.2,175.3,0,136.1,0,87.7L0,87.7z" /><path d="M72.7,115.4v-55c0-8.3,6.7-15,15-15l0,0c8.3,0,15,6.7,15,15l0,0v55c0,8.3-6.7,15-15,15l0,0 C79.4,130.4,72.7,123.6,72.7,115.4L72.7,115.4z" /></svg></span>' : '');
				//line += '</td></tr>\n<tr><td></td><td><abbr title="Correlated Color Temperature">CCT</abbr>&#160;' + Math.round(CCT[j]) + 'K, <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr>&#160;' + Math.round(CT[j]) + 'K></td><td>';
			}
			else {
				var color = '', mark = ' \u25cf', Y_color = color, Y_mark = mark;
				CCT_diff.push(-(reference[j]['CCT'] - results[i][j]['CCT']));
				CCT_diff_percent.push(100.0 / reference[j]['CCT'] * CCT_diff[j]);
				CT_diff.push(-(reference[j]['C' + locus.substr(0, 1) + 'T'] - CT[j]));
				CT_diff_percent.push(100.0 / reference[j]['C' + locus.substr(0, 1) + 'T'] * CT_diff[j]);
				Y_diff.push(-(reference[j]['XYZ'][1] - results[i][j]['XYZ'][1]));
				Y_diff_percent.push(100.0 / reference[0]['XYZ'][1] * Y_diff[j]);
				if (delta == 'E' || delta == 'C')
					Y_mark = '';
				else if (Math.abs(Y_diff_percent[j]) <= 5)
					Y_color = 'green';
				else if (Math.abs(Y_diff_percent[j]) <= 10)
					Y_color = 'yellow';
				else
					Y_color = 'red';
				if (Math.abs(deltas[i][j][delta]) <= tolerance_recommended_max)
					color = 'green';
				else if (Math.abs(deltas[i][j][delta]) <= tolerance_nominal_max)
					color = 'yellow';
				else
					color = 'red';
				line = (Y_mark ? '<span class="mark ' + Y_color + '">' + Y_mark + '</span>' : '') + (mark ? '<span class="mark ' + color + '">' + mark + '</span>' : '') + '</td><td>' + line;
				line += ' <span' + (Y_mark ? ' title="Nominal &lt;= 10%, recommended &lt;= 5%"' : '') + '>(' + (Y_diff_percent[j] > 0 ? '+' : '') + Y_diff_percent[j].accuracy(2) + '%)</span>, <span class="delta_toggle" onclick="window.delta = &quot;' + delta_cycle[delta] + '&quot;; generate_report()" title="Nominal &lt;= ' + tolerance_nominal_max.accuracy(2) + ', recommended &lt;= ' + tolerance_recommended_max.accuracy(2) + '">' + deltas[i][j][delta].accuracy(2) + ' Δ' + delta + '*00</span>';
				//line += '</td></tr>\n<tr><td></td><td><abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(CCT[j]) + 'K (' + (CCT_diff_percent[j] > 0 ? '+' : '') + CCT_diff_percent[j].accuracy(2) + '%), <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(CT[j]) + 'K (' + (CT_diff_percent[j] > 0 ? '+' : '') + CT_diff_percent[j].accuracy(2) + '%)>';
			}
			if (j == selected_index) {
				//rgb = jsapi.math.color.Lab2RGB(Lab_scaled[0], Lab_scaled[1], Lab_scaled[2], reference[0]['XYZ_100'], null, 255, true);
				rgb = [Math.round(255 * (1 - j / results[i].length)),
					   Math.round(255 * (1 - j / results[i].length)),
					   Math.round(255 * (1 - j / results[i].length))];
				if (results[i] == reference) {
					if (j == 3)
						cls = 'dark';
					else if (j == 2)
						cls = 'dim';
					else if (j)
						cls = 'avg';
					else
						cls = '';
				}
			}
			cellcontent.push(line);
		}
		if (results[i] == reference) {
			//line = '</td><td>strong>Average:</strong</td><td></td></tr>\n<tr><td></td><td><abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K, <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K</td><td';
			// ISO 14861:2015 tone uniformity
			/*line = '</td></tr>\n<tr><td></td><td>&#160;</td><td></td></tr>\n<tr><td><span class="mark ' + delta_E_max_color + '">' + delta_E_max_mark + '</span></td><td><strong>Maximum ΔE*00:</strong> ' + delta_E_max.accuracy(2) + '</td><td>';
			// ISO 14861:2015 deviation from uniform tonality (contrast deviation)
			// Technically, ISO 12646:2015 has caught up with ISO 14861
			line += '</td></tr>\n<tr><td><span class="mark ' + T_max_color + '">' + T_max_mark + '</span></td><td><strong>Maximum contrast deviation:</strong> ' + (T_max * 100).accuracy(2) + '%</td><td>';
			if (T_max < T_tolerance_nominal && delta_E_max <= delta_E_tolerance_nominal) {
				var msg_mark = '\u2713';
				if (delta_E_max <= delta_E_tolerance_recommended)
					var msg_color = 'green', msg = 'Recommended tolerance passed';
				else
					var msg_color = 'yellow', msg = 'Nominal tolerance passed';
			}
			else
				var msg_color = 'red', msg_mark = '\u2716', msg = 'Nominal tolerance exceeded';
			line += '</td></tr>\n<tr><td><strong class="msg ' + msg_color + '">' + msg_mark + '</strong></td><td><strong class="msg ' + msg_color + '">' + msg + '</strong></td><td>';*/
			line = '</td></tr>\n<tr><td colspan="3">&#160;</td></tr>\n<tr><td></td><td colspan="2">Evaluation criteria:<br /><select onchange="window.delta = this.options[this.selectedIndex].value; generate_report()"><option value="E"' + (delta == 'E' ? ' selected="selected"' : '') + '>ISO 14861:2015</option><option value="C"' + (delta == 'C' ? ' selected="selected"' : '') + '>Average luminance &amp; ΔC*00</option></select>' + (delta == 'E' && (rows < 5 || cols < 5) ? '</td></tr>\n<tr><td><span class="msg orange">\u26A0</span></td><td colspan="2"><span class="msg orange">ISO 14861:2015 mandates at least a 5 × 5 grid</span>' : '');
		}
		else {
			var delta_avg = jsapi.math.avg(curdeltas[i]),
				delta_max = jsapi.math.absmax(curdeltas[i]),
				Y_diff_percent_avg = jsapi.math.avg(Y_diff_percent),
				Y_diff_percent_max = jsapi.math.absmax(Y_diff_percent),
				color = '', mark = ' \u25cf', Y_color = color, Y_mark = mark;
			if (delta == 'E')
				Y_mark = '';
			else if (Math.abs(Y_diff_percent_avg) <= 5)
				Y_color = 'green';
			else if (Math.abs(Y_diff_percent_avg) <= 10)
				Y_color = 'yellow';
			else
				Y_color = 'red';
			if (Math.abs(delta_avg) <= tolerance_recommended)
				color = 'green';
			else if (Math.abs(delta_avg) <= tolerance_nominal)
				color = 'yellow';
			else
				color = 'red';
			line = '</td><td>&#160;</td></tr>\n<tr><td>' + (Y_mark ? '<span class="mark ' + Y_color + '">' + Y_mark + '</span>' : '') + (mark ? '<span class="mark ' + color + '">' + mark + '</span>' : '') + '</td><td><strong>Average:</strong> ' + (Y_diff_percent_avg > 0 ? '+' : '') + jsapi.math.avg(Y_diff).accuracy(2) + ' cd/m² <span' + (Y_mark ? ' title="Nominal &lt;= 10%, recommended &lt;= 5%"' : '') + '>(' + (Y_diff_percent_avg > 0 ? '+' : '') + Y_diff_percent_avg.accuracy(2) + '%)</span>, <span class="delta_toggle" onclick="window.delta = &quot;' + delta_cycle[delta] + '&quot;; generate_report()"' + (delta == 'C' ? ' title="Nominal &lt;= ' + tolerance_nominal.accuracy(2) + ', recommended &lt;= ' + tolerance_recommended.accuracy(2) + '"' : '') + '>' + delta_avg.accuracy(2) + ' Δ' + delta + '*00</span></td>';
			//line += '</tr>\n<tr><td></td><td><abbr title="Correlated Color Temperature">CCT</abbr> ' + Math.round(jsapi.math.avg(CCT)) + 'K (' + (jsapi.math.avg(CCT_diff_percent) > 0 ? '+' : '') + jsapi.math.avg(CCT_diff_percent).accuracy(2) + '%), <abbr class="locus_toggle" title="Closest ' + locus + ' Temperature" onclick="window.locus = &quot;' + (locus == 'Daylight' ? 'Planckian' : 'Daylight') + '&quot;; generate_report()">C' + locus.substr(0, 1) + 'T</abbr> ' + Math.round(jsapi.math.avg(CT)) + 'K (' + (jsapi.math.avg(CT_diff_percent) > 0 ? '+' : '') + jsapi.math.avg(CT_diff_percent).accuracy(2) + '%)>';
			Y_mark = mark;
			if (delta == 'E' || delta == 'C')
				Y_mark = '';
			else if (Math.abs(Y_diff_percent_avg) <= 5)
				Y_color = 'green';
			else if (Math.abs(Y_diff_percent_avg) <= 10)
				Y_color = 'yellow';
			else
				Y_color = 'red';
			// ISO 14861:2015 tone uniformity
			var result_delta_max_color = '', result_delta_max_mark = ' \u25cf';
			if (delta_max <= tolerance_recommended_max)
				result_delta_max_color = 'green';
			else if (delta_max <= tolerance_nominal_max)
				result_delta_max_color = 'yellow';
			else
				result_delta_max_color = 'red';
			line += '</tr>\n<tr><td>' + (Y_mark ? '<span class="mark ' + Y_color + '">' + Y_mark + '</span>' : '') + '<span class="mark ' + result_delta_max_color + '">' + result_delta_max_mark + '</span></td><td><strong>Maximum:</strong> ' + (Y_diff_percent_max > 0 ? '+' : '') + jsapi.math.absmax(Y_diff).accuracy(2) + ' cd/m² <span' + (Y_mark ? ' title="Nominal &lt;= 10%, recommended &lt;= 5%"' : '') + '>(' + (Y_diff_percent_max > 0 ? '+' : '') + Y_diff_percent_max.accuracy(2) + '%)</span>, <span class="delta_toggle" onclick="window.delta = &quot;' + delta_cycle[delta] + '&quot;; generate_report()" title="Nominal &lt;= ' + tolerance_nominal_max.accuracy(2) + ', recommended &lt;= ' + tolerance_recommended_max.accuracy(2) + '">' + delta_max.accuracy(2) + ' Δ' + delta + '*00</span>';
			// ISO 14861:2015 deviation from uniform tonality (contrast deviation)
			// Technically, ISO 12646:2015 has caught up with ISO 14861:2015
			var T_color = '', T_mark = ' \u25cf';
			if (delta != 'E')
				T_mark = '';
			else if (T[i] < T_tolerance_nominal)
				T_color = 'green';
			else
				T_color = 'red';
			line += '</td></tr>\n<tr><td>' + (T_mark ? '<span class="mark ' + T_color + '">' + T_mark + '</span>' : '') + '</td><td><strong>Contrast deviation:</strong> <span' + (delta == 'E' ? ' title="Nominal &lt; 10%"' : '') + '>' + (T[i] * 100).accuracy(2) + '%</span>';
			if ((delta == 'E' ? T[i] < T_tolerance_nominal : Y_diff_percent_avg < 10) && delta_max <= tolerance_nominal_max && delta_avg <= tolerance_nominal) {
				var msg_mark = '\u2713';
				if (delta_max <= tolerance_recommended_max && delta_avg <= tolerance_recommended)
					var msg_color = 'green', msg = 'Recommended tolerance passed';
				else
					var msg_color = 'yellow', msg = 'Nominal tolerance passed';
			}
			else
				var msg_color = 'red', msg_mark = '\u2716', msg = 'Nominal tolerance exceeded';
			line += '</td></tr>\n<tr><td><strong class="msg ' + msg_color + '">' + msg_mark + '</strong></td><td><strong class="msg ' + msg_color + '">' + msg + '</strong>';
		}
		cellcontent.push(line);
		cells.push('<td id="cell-' + i + '" style="background-color: rgb(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + '); height: ' + (100 / rows) + '%; width: ' + (100 / cols) + '%;" class="' + (i == reference_index ? 'reference ' : msg_color) + '"><table><tr><td>' + cellcontent.join('</td></tr>\n<tr><td>') + '</td></tr></table></td>');
		if ((i + 1) % self.cols == 0 && i + 1 < self.rows * self.cols) {
			cells[cells.length - 1] += '</tr>\n<tr>';
		}
	}
	document.getElementsByTagName('body')[0].innerHTML = '<table id="report"' + (cls ? ' class="' + cls + '"' : '') + '><tbody><tr>' + cells.join('') + '</tr></tbody></table>';
};
window.onload = generate_report;
