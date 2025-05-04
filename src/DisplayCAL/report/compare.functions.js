var p;
var debug = window.location.href.indexOf("?debug") > -1,
	get_gammaRGB = window.location.hash.indexOf("get_gammaRGB") > -1;

// Array methods
p=Array.prototype;
p.indexof = function(v, ignore_case) {
	for (var i=0; i<this.length; i++) if (ignore_case?(this[i]+"").toUpperCase()==(v+"").toUpperCase():this[i]==v) return i;
	return -1
};
if (!p.indexOf) p.indexOf = p.indexof;

// Object methods
p=Object.prototype;
p.clone = function() {
	var o = new this.constructor();
	for (var i in this) {
		if (this[i] != null && (this[i].constructor == Array || this[i].constructor == Object)) o[i] = this[i].clone();
		else o[i] = this[i]
	};
	return o
};

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

// String methods
p=String.prototype;
p.accuracy = function() {
	return this
};
p.repeat = function(n) {
	var str="";
	for (var i=0; i<n; i++) str+=this;
	return str
};

// dataset Constructor
function dataset(src) {
	this.header = [];
	this.data_format = [];
	this.data = [];
	this.decimal = ".";
	this.id = "RGB";
	var e = document.forms['F_data'].elements;
	this.testchart = e['FF_testchart'].value;
	//this.id = window.CRITERIA_GRAYSCALE ? 'RGB_GRAY' : splitext(basename(this.testchart))[0].toUpperCase();
	this.id = splitext(basename(this.testchart))[0].toUpperCase();
	if (src) {
		this.src = src;
		src=cr2lf(src);
		var _data_format_regexp = /(^|\s)BEGIN_DATA_FORMAT\s+(.*)\s+END_DATA_FORMAT(\s|$)/i,
			_data_regexp1 = /(^|\s)BEGIN_DATA\s+/i,
			_data_regexp2 = /\sEND_DATA(\s|$)/i,
			_header_regexp1 = /(^|\s)BEGIN_(\w+)\s+([\s\S]*)\s+END_\2(\s|$)/gi,
			_header_regexp2 = /(^|\s)BEGIN_(\w+)\s+([\s\S]*)\s+END_\2(\s|$)/i,
			data_begin,
			data_end,
			data_format = src.match(_data_format_regexp),
			i,v;
		if (data_format && data_format[2]) {
			this.data_format = toarray(data_format[2], 1);
			while ((data_begin = src.search(_data_regexp1))>-1 && (data_end = src.search(_data_regexp2))>data_begin) {
				if (!this.data.length) { // 1st
					var header = lf2cr(src).substr(0, data_begin).replace(_data_format_regexp, "");
					if (v = header.match(_header_regexp1)) for (i=0; i<v.length; i++) {
						header = header.replace(_header_regexp2, "\r" + (v[i].replace(_header_regexp2, "$2 $3").replace(/\r/g, "\n")))
					};
					header=trim(header).split(/\r/);
					for (i=0; i<header.length; i++) {
						header[i] = trim(header[i]).replace(/\s+/, "\r").split("\r");
						this.header_set_field(header[i][0], header[i][1], "append")
					}
				};
				this.data = this.data.concat(toarray(src.substring(data_begin, data_end).replace(_data_regexp1, "").replace(_data_regexp2, "")));
				src = src.substr(data_end+9)
			}
		};
	};
	if (this.data_format.indexOf('CMYK_C') > -1 && this.data_format.indexOf('CMYK_M') > -1 && this.data_format.indexOf('CMYK_Y') > -1 && this.data_format.indexOf('CMYK_K') > -1)
		this.device = 'CMYK';
	else
		this.device = 'RGB';
	if (comparison_criteria[this.id]) this.id = comparison_criteria[this.id].id;
	else this.id = this.device;
	return src ? true : false
};

p=dataset.prototype;
p.header_get = function() {
	var header=[], i, j, v;
	for (i=0; i<this.header.length; i++) {
		if (this.header[i][1] && this.header[i][1].indexOf("\n")>-1) {
			header.push(["BEGIN_"+this.header[i][0]]);
			v=this.header[i][1].split("\n");
			for (j=0; j<v.length; j++) header.push([v[j]]);
			header.push(["END_"+this.header[i][0]])
		}
		else header.push(this.header[i])
	};
	return fromarray(header)
};
p.header_set = function(header, mode) {
	for (var i=0; i<header.length; i++) {
		this.header_set_field(header[i][0], header[i][1], mode)
	}
};
p.header_set_date = function(mode) {
	var now=new Date();
	this.header_set_field("CREATED", "\"" + (now.getMonth()+1) + "/" + now.getDate() + "/" + now.getFullYear() + "\" # Time: " + now.getHours().fill(2) + ":" + now.getMinutes().fill(2), mode)
};
p.header_set_defaults = function(mode) {
	this.header_set_date(mode);
};
p.header_set_field = function(name, value, mode) {
	if (!name) return false;
	if (value != null) value += "";
	if (name.toUpperCase() == "NUMBER_OF_FIELDS" || name.toUpperCase() == "NUMBER_OF_SETS") return false;
	if (!this.header[name.toUpperCase()] || mode=="append" || name.toUpperCase() == "KEYWORD") {
		var header=[name];
		if(value!=null && value!=="") header.push(value);
		this.header.push(header);
		if (!this.header[name.toUpperCase()]) this.header[name.toUpperCase()]=[];
		this.header[name.toUpperCase()].push(this.header[this.header.length-1])
	}
	else if (mode=="overwrite") {
		for (var i=0; i<this.header[name.toUpperCase()].length; i++) {
			if (value==null || value==="") this.header[name.toUpperCase()][i].splice(1, 1);
			else this.header[name.toUpperCase()][i][1] = value
		}
	}
};
p.toString = function() {
	return (this.header.length?this.header_get()+"\n":"") + "NUMBER_OF_FIELDS\t" + this.data_format.length + "\nBEGIN_DATA_FORMAT\n" + fromarray(this.data_format, 1) + "\nEND_DATA_FORMAT\nNUMBER_OF_SETS\t" + this.data.length + "\nBEGIN_DATA\n" + decimal(fromarray(this.data), this.decimal == "." ? "\\," : "\\." , this.decimal) + "\nEND_DATA"
};
p.generate_report = function(set_delta_calc_method) {
	var f = document.forms,
		e = f['F_data'].elements,
		criteria = comparison_criteria[f['F_out'].elements['FF_criteria'].value];
	if (set_delta_calc_method !== false) {
		f['F_out'].elements['FF_delta_calc_method'].selectedIndex = ['CIE76', 'CIE94', 'CIE00', 'ICtCp'].indexOf(criteria.delta_calc_method);
		f['F_out'].elements['FF_absolute'].checked = WHITEPOINT_SIMULATION && !WHITEPOINT_SIMULATION_RELATIVE && !!SIMULATION_PROFILE;
		f['F_out'].elements['FF_use_profile_wp_as_ref'].checked = e['FF_profile'].value == SIMULATION_PROFILE;
	}
	f['F_out'].elements['FF_delta_calc_method'].disabled = criteria.lock_delta_calc_method;
	var rules = criteria.rules,
		result = [],
		delta,
		matched,
		target,
		target_Lab,
		target_rgb,
		target_rgb_html,
		actual,
		actual_Lab,
		actual_rgb,
		actual_rgb_html,
		planckian = f['F_out'].elements['FF_planckian'].checked,
		profile_wp = e['FF_profile_whitepoint'].value.split(/\s+/),
		profile_wp_round = [],
		profile_wp_norm = e['FF_profile_whitepoint_normalized'].value.split(/\s+/),
		profile_wp_norm_1 = [],
		profile_wp_norm_round = [],
		profile_wp_xy = [],
		profile_wp_xy_round = [],
		profile_colortemp,
		bp = e['FF_blackpoint'].value.split(/\s+/),
		wp = e['FF_whitepoint'].value.split(/\s+/),
		wp_round = [],
		wp_norm = e['FF_whitepoint_normalized'].value.split(/\s+/),
		wp_norm_1 = [],
		wp_norm_round = [],
		wp_xy = [],
		wp_xy_round = [],
		colortemp,
		colortemp_assumed,
		wp_assumed,
		wp_assumed_round = [],
		wp_assumed_xy = [],
		wp_assumed_xy_round = [],
		mode = f['F_out'].elements['FF_mode'].value,
		absolute = f['F_out'].elements['FF_absolute'].checked,
		use_profile_wp_as_ref = f['F_out'].elements['FF_use_profile_wp_as_ref'].checked,
		cat = e['FF_adaption'].value,
		target_Lab2RGB_wp_1 = absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'),
		actual_Lab2RGB_wp_1 = absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'),
		target_Lab2RGB_src_wp_1 = absolute && profile_wp_norm_1,
		actual_Lab2RGB_src_wp_1 = absolute && wp_norm_1,
		n = 0,
		o = fields_match.length - 1, // offset for CIE values in fields_extract_indexes
		devstart = criteria.fields_match.length > 3 ? 3 : 0, // start offset for device values in fields_match (CMYK if length > 3, else RGB)
		devend = criteria.fields_match.length > 3 ? 6 : 2, // end offset for device values in fields_match (CMYK if length > 3, else RGB)
		missing_data,
		delta_calc_method = f['F_out'].elements['FF_delta_calc_method'].value,
		delta_symbol = {'ICtCp': '',
						'CIE00': "'"}[delta_calc_method] || '*',
		weight_symbol = (delta_calc_method != "CIE76" ? '/w' : ''),
		delta_E_desc = delta_calc_method == 'ICtCp' ? 'IC<sub>T</sub>C<sub>P</sub>' : delta_calc_method.replace(/CIE(.+)/, 'E<sub>$1</sub>'),
		delta_L_desc = delta_calc_method == 'ICtCp' ? 'I' : delta_calc_method.replace(/CIE(.+)/, 'L*<sub>$1' + weight_symbol + '</sub>'),
		delta_C_desc = delta_calc_method == 'ICtCp' ? 'C<sub>C<sub>T</sub>C<sub>P</sub></sub>' : delta_calc_method.replace(/CIE(.+)/, 'C' + delta_symbol + '<sub>$1' + weight_symbol + '</sub>'),
		delta_H_desc = delta_calc_method == 'ICtCp' ? 'H<sub>C<sub>T</sub>C<sub>P</sub></sub>' : delta_calc_method.replace(/CIE(.+)/, 'H' + delta_symbol + '<sub>$1' + weight_symbol + '</sub>'),
		patch_number_html,
		verbosestats = f['F_out'].elements['FF_verbosestats'].checked,
		warn_deviation = criteria.warn_deviation,
		no_Lab = (this.data_format.indexof("LAB_L", true) < 0
				|| this.data_format.indexof("LAB_A", true) < 0
				|| this.data_format.indexof("LAB_B", true) < 0),
		no_XYZ = (this.data_format.indexof("XYZ_X", true) < 0
				|| this.data_format.indexof("XYZ_Y", true) < 0
				|| this.data_format.indexof("XYZ_Z", true) < 0),
		gray_balance_cal_only = f['F_out'].elements['FF_gray_balance_cal_only'].checked;
	
	if (profile_wp.length == 3) {
		for (var i=0; i<profile_wp.length; i++) {
			profile_wp[i] = parseFloat(profile_wp[i]);
			profile_wp_round[i] = profile_wp[i].accuracy(2)
		};
		profile_wp_xy = jsapi.math.color.XYZ2xyY(profile_wp[0], profile_wp[1], profile_wp[2]);
		profile_wp_xy_round[0] = profile_wp_xy[0].accuracy(4);
		profile_wp_xy_round[1] = profile_wp_xy[1].accuracy(4);
		for (var i=0; i<profile_wp.length; i++) {
			profile_wp_norm_1[i] = profile_wp[i] / profile_wp[1];
			profile_wp_norm[i] = profile_wp_norm_1[i] * 100;
			profile_wp_norm_round[i] = profile_wp_norm[i].accuracy(2)
		};
		profile_colortemp = Math.round(jsapi.math.color.XYZ2CorColorTemp(profile_wp_norm[0], profile_wp_norm[1], profile_wp_norm[2]));
	}
	
	if (bp.length == 3) {
		for (var i=0; i<bp.length; i++) {
			bp[i] = parseFloat(bp[i]);
		};
	}
	
	if (wp.length == 3) {
		for (var i=0; i<wp.length; i++) {
			wp[i] = parseFloat(wp[i]);
			wp_round[i] = wp[i].accuracy(2)
		};
		wp_xy = jsapi.math.color.XYZ2xyY(wp[0], wp[1], wp[2]);
		wp_xy_round[0] = wp_xy[0].accuracy(4);
		wp_xy_round[1] = wp_xy[1].accuracy(4);
		for (var i=0; i<wp.length; i++) {
			wp_norm_1[i] = wp[i] / wp[1];
			wp_norm[i] = wp_norm_1[i] * 100;
			wp_norm_round[i] = wp_norm[i].accuracy(2)
		};
		colortemp = Math.round(jsapi.math.color.XYZ2CorColorTemp(wp_norm[0], wp_norm[1], wp_norm[2]));
		if (colortemp >= 1667 && colortemp < 2500) {
			f['F_out'].elements['FF_planckian'].checked = planckian = true;
			f['F_out'].elements['FF_planckian'].disabled = true;
		}
		colortemp_assumed = Math.round(colortemp / 100) * 100;
		if (planckian)
			wp_assumed = jsapi.math.color.planckianCT2XYZ(colortemp_assumed);
		else
			wp_assumed = jsapi.math.color.CIEDCorColorTemp2XYZ(colortemp_assumed);
		for (var i=0; i<wp_assumed.length; i++) {
			wp_assumed[i] = wp_assumed[i] * 100;
			wp_assumed_round[i] = wp_assumed[i].accuracy(2);
		}
		wp_assumed_xy = jsapi.math.color.XYZ2xyY(wp_assumed[0], wp_assumed[1], wp_assumed[2]);
		wp_assumed_xy_round[0] = wp_assumed_xy[0].accuracy(4);
		wp_assumed_xy_round[1] = wp_assumed_xy[1].accuracy(4);
	}

	var ICtCp_lumi_target_scale = (profile_wp || wp)[1] / 10000,
		ICtCp_lumi_scale = wp[1] / 10000;
	
	this.report_html = [
		'	<div class="info"><h3 class="toggle" onclick="toggle(this)">Basic Information</h3>',
		'	<table cellspacing="0" id="info">',
		'		<tr>',
		'			<th>Device:</th>',
		'			<td>' + e['FF_display'].value + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Instrument:</th>',
		'			<td>' + e['FF_instrument'].value + '</td>',
		'		</tr>',
		(e['FF_correction_matrix'].value ? '<tr><th>Correction:</th><td>' + e['FF_correction_matrix'].value + '</td></tr>' : ''),
		'		<tr>',
		'			<th>Display profile:</th>',
		'			<td>' + e['FF_profile'].value + '</td>',
		'		</tr>'
	];
	if (profile_wp[1] != 100) this.report_html = this.report_html.concat([
		'		<tr>',
		'			<th>Display profile luminance:</th>',
		'			<td>' + profile_wp[1].accuracy(1) + ' cd/m²</td>',
		'		</tr>'
	]);
	if (profile_wp.length == 3) this.report_html = this.report_html.concat([
		'		<tr>',
		'			<th>Display profile whitepoint:</th>',
		'			<td>' + 'xy ' + profile_wp_xy_round.join(' ') + ' (XYZ ' + profile_wp_norm_round.join(' ') + '), CCT ' + profile_colortemp + 'K</td>',
		'		</tr>'
	]);
	if (wp.length == 3) this.report_html = this.report_html.concat([
		'		<tr>',
		'			<th>Measured luminance:</th>',
		'			<td>' + wp[1].accuracy(1) + ' cd/m²</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Measured whitepoint:</th>',
		'			<td>' + 'xy ' + wp_xy_round.join(' ') + ' (XYZ ' + wp_norm_round.join(' ') + '), CCT ' + colortemp + 'K</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Assumed target whitepoint:</th>',
		'			<td>' + colortemp_assumed + 'K ' + (planckian ? 'blackbody' : 'daylight') + ', xy ' + wp_assumed_xy_round.join(' ') + ' (XYZ ' + wp_assumed_round.join(' ') + ')</td>'
	]);
	if (bp.length == 3 && bp[0] > -1 && bp[1] > -1 && bp[2] > -1) this.report_html = this.report_html.concat([
		'		<tr>',
		'			<th>Measured black luminance:</th>',
		'			<td>' + bp[1].accuracy(4) + ' cd/m²</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Contrast:</th>',
		'			<td>' + (wp[1] / bp[1]).accuracy(1) + ':1</td>',
		'		</tr>'
	]);
	this.report_html = this.report_html.concat([
		'		</tr>',
		'		<tr>',
		'			<th>Testchart:</th>',
		'			<td>' + this.testchart + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Simulation profile:</th>',
		'			<td>' + (SIMULATION_PROFILE || 'None') + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Gamma mapping:</th>',
		'			<td>' + (TRC_GAMMA ? (TRC ? TRC : TRC + ' ' + TRC_GAMMA.toFixed(2) + ' ' + {"b": "relative",
																								"B": "absolute"}[TRC_GAMMA_TYPE] + ', black output offset ' + (TRC_OUTPUT_OFFSET * 100).toFixed(0) + '%') : (SIMULATION_PROFILE ? 'No' : 'N/A')) + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Whitepoint simulation:</th>',
		'			<td>' + (WHITEPOINT_SIMULATION ? 'Yes' + (WHITEPOINT_SIMULATION_RELATIVE ? ', relative to display profile whitepoint' : '') : (!DEVICELINK_PROFILE && SIMULATION_PROFILE ? 'No' : 'N/A')) + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Chromatic adaptation:</th>',
		'			<td>' + e['FF_adaption'].value + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Devicelink profile:</th>',
		'			<td>' + (DEVICELINK_PROFILE || 'None') + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Evaluation criteria:</th>',
		'			<td>' + criteria.name + '</td>',
		'		</tr>',
		'		<tr>',
		'			<th>Date:</th>',
		'			<td>' + e['FF_datetime'].value + '</td>',
		'		</tr>',
		'	</table></div>'
	]);
	var result_start = this.report_html.length;
	this.report_html = this.report_html.concat([
		'	<div class="summary">',
		'	<h3 class="toggle" onclick="toggle(this)">Summary</h3>',
		'	<div id="summary">',
		'	<table cellspacing="0">',
		'		<tr>',
		'			<th class="first-column">Criteria</th><th>Nominal</th><th>Recommended</th><th>#</th><th colspan="2">&#160;</th><th>Actual</th><th>&#160;</th><th>Result</th>',
		'		</tr>'
	]);
	var seen = [];
	for (var j=0; j<rules.length; j++) {
		result[j] = {
			E: [],
			L: [],
			C: [],
			H: [],
			a: [],
			b: [],
			Ch: [],
			g: [],
			matches: [],
			sum: null
		};
		if (rules[j][1].length == 1) {
			switch (rules[j][1][0]) {
				case 'CAL_REDLEVELS':
					if (window.CAL_RGBLEVELS) {
						result[j].sum = (window.CAL_RGBLEVELS[0] / CAL_ENTRYCOUNT * 100).accuracy(1);
						result[j].htmlsum = result[j].sum + '%<br />(' + window.CAL_RGBLEVELS[0] + '/' + CAL_ENTRYCOUNT + ')';
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
				case 'CAL_GREENLEVELS':
					if (window.CAL_RGBLEVELS) {
						result[j].sum = (window.CAL_RGBLEVELS[1] / CAL_ENTRYCOUNT * 100).accuracy(1);
						result[j].htmlsum = result[j].sum + '%<br />(' + window.CAL_RGBLEVELS[1] + '/' + CAL_ENTRYCOUNT + ')';
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
				case 'CAL_BLUELEVELS':
					if (window.CAL_RGBLEVELS) {
						result[j].sum = (window.CAL_RGBLEVELS[2] / CAL_ENTRYCOUNT * 100).accuracy(1);
						result[j].htmlsum = result[j].sum + '%<br />(' + window.CAL_RGBLEVELS[2] + '/' + CAL_ENTRYCOUNT + ')';
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
				case 'CAL_GRAYLEVELS':
					if (window.CAL_RGBLEVELS) {
						var cal_graylevels = Math.min(CAL_RGBLEVELS[0], CAL_RGBLEVELS[1], CAL_RGBLEVELS[2]);
						result[j].sum = (cal_graylevels / CAL_ENTRYCOUNT * 100).accuracy(1);
						result[j].htmlsum = result[j].sum + '%<br />(' + cal_graylevels + '/' + CAL_ENTRYCOUNT + ')';
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
				case 'WHITEPOINT_MvsA': // Measured vs. assumed
					if (wp.length == 3) {
						target_Lab = [100, 0, 0];
						actual_Lab = jsapi.math.color.XYZ2Lab(wp_norm[0], wp_norm[1], wp_norm[2], [wp_assumed[0], wp_assumed[1], wp_assumed[2]]);
						// alert(rules[j] + '\ntarget_Lab: ' + target_Lab + '\nactual_Lab: ' + actual_Lab);
						delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], rules[j][5], null, null, null, [wp_assumed[0] / 100, wp_assumed[1] / 100, wp_assumed[2] / 100], (profile_wp || wp)[1], wp[1], cat);
						result[j].E.push(delta.E);
						result[j].L.push(delta.Lw);
						result[j].C.push(delta.Cw);
						result[j].H.push(delta.Hw);
						result[j].a.push(delta.a);
						result[j].b.push(delta.b);
						result[j].Ch.push(delta.Ch);
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
				case 'WHITEPOINT_MvsP': // Profile vs. measured
					if (wp.length == 3 && profile_wp.length == 3) {
						target_Lab = [100, 0, 0];
						actual_Lab = jsapi.math.color.XYZ2Lab(wp_norm[0], wp_norm[1], wp_norm[2], [profile_wp_norm[0], profile_wp_norm[1], profile_wp_norm[2]]);
						// alert(rules[j] + '\ntarget_Lab: ' + target_Lab + '\nactual_Lab: ' + actual_Lab);
						delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], rules[j][5], null, null, null, profile_wp_norm_1, (profile_wp || wp)[1], wp[1], cat);
						result[j].E.push(delta.E);
						result[j].L.push(delta.Lw);
						result[j].C.push(delta.Cw);
						result[j].H.push(delta.Hw);
						result[j].a.push(delta.a);
						result[j].b.push(delta.b);
						result[j].Ch.push(delta.Ch);
					}
					else {
						rules[j][3] = null;
						rules[j][4] = null;
						continue;
					}
					break;
			}
		};
		this.report_html.push('		<tr' + (!(rules[j][3] || rules[j][4]) || !rules[j][5] || (!rules[j][6] && rules[j][5].substr(3) != delta_calc_method.substr(3)) ? ' class="statonly' + (verbosestats ? '' : ' verbose') + '"' : '' ) + '>');
		this.report_html.push('			<td class="first-column">' + rules[j][0] + '</td><td>' + (rules[j][3] ? (rules[j][2] ? '&lt;= ' + rules[j][3] : '&gt;= ' + rules[j][3] + '%') : '&#160;') + '</td><td class="statonly">' + (rules[j][4] ? (rules[j][2] ? '&lt;= ' + rules[j][4] : '&gt;= ' + rules[j][4] + '%'): '&#160;') + '</td><td class="sample_id">');
		patch_number_html = [];
		actual_rgb_html = [];
		target_rgb_html = [];
		var haspatchid = false;
		if (rules[j][2].indexOf("_MAX") < 0 && rules[j][2].indexOf("_MIN") < 0) {
			for (var k=0; k<rules[j][1].length; k++) if (rules[j][1].length > 1 && seen.indexOf(rules[j][1].join(',')) < 0 && (rules[j][6] || rules[j][5].substr(3) == delta_calc_method.substr(3))) {
				patch_number_html.push('<div class="sample_id">&#160;</div>');
				haspatchid = true;
				if (rules[j][1][k].length == 4) // Assume CMYK
					target_rgb = jsapi.math.color.CMYK2RGB(rules[j][1][k][0] / 100, rules[j][1][k][1] / 100, rules[j][1][k][2] / 100, rules[j][1][k][3] / 100, 255);
				else 
					// XXX Note that round(50 * 2.55) = 127, but
					// round(50 / 100 * 255) = 128 (the latter is what we want)!
					target_rgb = [rules[j][1][k][0] / 100.0 * 255, rules[j][1][k][1] / 100.0 * 255, rules[j][1][k][2] / 100.0 * 255];
				target_rgb_html.push('<div class="patch" style="background-color: rgb(' + Math.round(target_rgb[0]) + ', ' + Math.round(target_rgb[1]) + ', ' + Math.round(target_rgb[2]) + ');">&#160;</div>');
				actual_rgb_html.push('<div class="patch" style="color: red; position: relative;"><span style="position: absolute;">\u2716</span>&#160;</div>');
			}
		};
		if (rules[j][1].length) {
			for (var k=0; k<rules[j][1].length; k++) {
				for (var l=0; l<rules[j][1][k].length; l++) if (!isNaN(rules[j][1][k][l])) rules[j][1][k][l] = rules[j][1][k][l].accuracy(2);
			}
		};
		var silent = false;
		for (var i=0, n=0; i<this.data.length; i++) {
				this.data[i].actual_DE = null;
				this.data[i].tolerance_DE = null;
				this.data[i].actual_DL = null;
				this.data[i].tolerance_DL = null;
				this.data[i].actual_Da = null;
				this.data[i].tolerance_Da = null;
				this.data[i].actual_Db = null;
				this.data[i].tolerance_Db = null;
				this.data[i].actual_DC = null;
				this.data[i].tolerance_DC = null;
				this.data[i].actual_DH = null;
				this.data[i].tolerance_DH = null;
				n++;
				target = data_ref.data[i];
				actual = this.data[i];
				matched = false;
				var colors = get_colors(target, actual, o, no_Lab, no_XYZ, gray_balance_cal_only, false, profile_wp_norm, wp_norm, absolute, cat, use_profile_wp_as_ref);
				target_Lab = colors.target_Lab;
				actual_Lab = colors.actual_Lab;
				current_rgb = colors.current_rgb;
				current_cmyk = colors.current_cmyk;
				if (rules[j][1].length) {
					for (var k=0; k<rules[j][1].length; k++) {
						if ((rules[j][1][k].length == 3 && current_rgb.join(',') == rules[j][1][k].join(',')) || (rules[j][1][k].length == 4 && current_cmyk.join(',') == rules[j][1][k].join(','))) {
							// if (silent || !confirm('rules[j]: ' + rules[j] + '\nrules[j][1][k]: ' + rules[j][1][k] + '\nthis.data[' + i + ']: ' + this.data[i] + '\ncurrent_rgb: ' + current_rgb + '\ncurrent_cmyk: ' + current_cmyk)) silent = true;
							if (rules[j][2].indexOf("_MAX") < 0 && rules[j][2].indexOf("_MIN") < 0 && seen.indexOf(rules[j][1].join(',')) < 0 && (rules[j][6] || rules[j][5].substr(3) == delta_calc_method.substr(3))) {
								if (rules[j][1].length) {
									patch_number_html[k] = ('<div class="sample_id">' + n.fill(String(number_of_sets).length) + '</div>');
									haspatchid = true;
								}
								target_rgb = jsapi.math.color.Lab2RGB(target_Lab[0], target_Lab[1], target_Lab[2], target_Lab2RGB_wp_1, target_Lab2RGB_src_wp_1, 255, true, cat);
								actual_rgb = jsapi.math.color.Lab2RGB(actual_Lab[0], actual_Lab[1], actual_Lab[2], actual_Lab2RGB_wp_1, actual_Lab2RGB_src_wp_1, 255, true, cat);
								target_rgb_html[k] = ('<div class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');">&#160;</div>');
								actual_rgb_html[k] = ('<div class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');">&#160;</div>');
							};
							matched = true
						}
					}
				}
				else matched = true;
				if (matched) {
					delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], rules[j][5], null, null, null, absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'), (profile_wp || wp)[1], wp[1], cat);
					result[j].E.push(delta.E);
					result[j].L.push(delta.Lw);
					result[j].C.push(delta.Cw);
					result[j].H.push(delta.Hw);
					result[j].a.push(delta.a);
					result[j].b.push(delta.b);
					result[j].Ch.push(delta.Ch);
					if (actual.gamma) result[j].g.push(actual.gamma);
					if ((rules[j][1].length || rules[j][2].indexOf('_MAX') > -1 || rules[j][2].indexOf('_MIN') > -1) && (rules[j][2].indexOf('GAMMA') < 0 || actual.gamma)) result[j].matches.push([i, i, n])
				}
		};
		this.report_html = this.report_html.concat(patch_number_html);
		var number_of_sets = n;
		if (!rules[j][1].length || ((rules[j][1][0] == 'WHITEPOINT_MvsA' || (rules[j][1][0] == 'WHITEPOINT_MvsP' && profile_wp.length == 3)) && wp.length == 3) || result[j].matches.length >= rules[j][1].length) switch (rules[j][2]) {
			case DELTA_A_MAX:
				result[j].sum = jsapi.math.absmax(result[j].a);
				break;
			case DELTA_A_AVG:
				result[j].sum = jsapi.math.avgabs(result[j].a);
				break;
			case DELTA_A_MED:
				result[j].sum = jsapi.math.median(result[j].a);
				break;
			case DELTA_A_MAD:
				result[j].sum = jsapi.math.mad(result[j].a);
				break;
			case DELTA_A_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].a, 0.95);
				break;
			case DELTA_A_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].a, 0.99);
				break;
			case DELTA_A_RANGE:
				result[j].sum = jsapi.math.max(result[j].a) - jsapi.math.min(result[j].a);
				break;
			case DELTA_A_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].a);
				break;
				
			case DELTA_A_B_RANGE:
				var ab = result[j].a.concat(result[j].b);
				result[j].sum = jsapi.math.max(ab) - jsapi.math.min(ab);
				break;
				
			case DELTA_CH_MAX:
				result[j].sum = jsapi.math.max(result[j].Ch);
				break;
			case DELTA_CH_AVG:
				result[j].sum = jsapi.math.avg(result[j].Ch);
				break;
				
			case DELTA_B_MAX:
				result[j].sum = jsapi.math.absmax(result[j].b);
				break;
			case DELTA_B_AVG:
				result[j].sum = jsapi.math.avgabs(result[j].b);
				break;
			case DELTA_B_MED:
				result[j].sum = jsapi.math.median(result[j].b);
				break;
			case DELTA_B_MAD:
				result[j].sum = jsapi.math.mad(result[j].b);
				break;
			case DELTA_B_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].B, 0.95);
				break;
			case DELTA_B_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].B, 0.99);
				break;
			case DELTA_B_RANGE:
				result[j].sum = jsapi.math.max(result[j].b) - jsapi.math.min(result[j].b);
				break;
			case DELTA_B_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].b);
				break;
				
			case DELTA_E_MAX:
				result[j].sum = jsapi.math.absmax(result[j].E);
				break;
			case DELTA_E_AVG:
				result[j].sum = jsapi.math.avg(result[j].E);
				break;
			case DELTA_E_MED:
				result[j].sum = jsapi.math.median(result[j].E);
				break;
			case DELTA_E_MAD:
				result[j].sum = jsapi.math.mad(result[j].E);
				break;
			case DELTA_E_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].E, 0.95);
				break;
			case DELTA_E_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].E, 0.99);
				break;
			case DELTA_E_RANGE:
				result[j].sum = jsapi.math.max(result[j].E) - jsapi.math.min(result[j].E);
				break;
			case DELTA_E_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].E);
				break;
				
			case DELTA_L_MAX:
				result[j].sum = jsapi.math.absmax(result[j].L);
				break;
			case DELTA_L_AVG:
				result[j].sum = jsapi.math.avgabs(result[j].L);
				break;
			case DELTA_L_MED:
				result[j].sum = jsapi.math.median(result[j].L);
				break;
			case DELTA_L_MAD:
				result[j].sum = jsapi.math.mad(result[j].L);
				break;
			case DELTA_L_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].L, 0.95);
				break;
			case DELTA_L_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].L, 0.99);
				break;
			case DELTA_L_RANGE:
				result[j].sum = jsapi.math.max(result[j].L) - jsapi.math.min(result[j].L);
				break;
			case DELTA_L_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].L);
				break;
				
			case DELTA_C_MAX:
				result[j].sum = jsapi.math.absmax(result[j].C);
				break;
			case DELTA_C_AVG:
				result[j].sum = jsapi.math.avgabs(result[j].C);
				break;
			case DELTA_C_MED:
				result[j].sum = jsapi.math.median(result[j].C);
				break;
			case DELTA_C_MAD:
				result[j].sum = jsapi.math.mad(result[j].C);
				break;
			case DELTA_C_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].C, 0.95);
				break;
			case DELTA_C_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].C, 0.99);
				break;
			case DELTA_C_RANGE:
				result[j].sum = jsapi.math.max(result[j].C) - jsapi.math.min(result[j].C);
				break;
			case DELTA_C_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].C);
				break;
				
			case DELTA_H_MAX:
				result[j].sum = jsapi.math.absmax(result[j].H);
				break;
			case DELTA_H_AVG:
				result[j].sum = jsapi.math.avgabs(result[j].H);
				break;
			case DELTA_H_MED:
				result[j].sum = jsapi.math.median(result[j].H);
				break;
			case DELTA_H_MAD:
				result[j].sum = jsapi.math.mad(result[j].H);
				break;
			case DELTA_H_PERCENTILE_95:
				result[j].sum = jsapi.math.percentile(result[j].H, 0.95);
				break;
			case DELTA_H_PERCENTILE_99:
				result[j].sum = jsapi.math.percentile(result[j].H, 0.99);
				break;
			case DELTA_H_RANGE:
				result[j].sum = jsapi.math.max(result[j].H) - jsapi.math.min(result[j].H);
				break;
			case DELTA_H_STDDEV:
				result[j].sum = jsapi.math.stddev(result[j].H);
				break;
				
			case GAMMA_MAX:
				if (result[j].g.length) result[j].sum = jsapi.math.max(result[j].g);
				break;
			case GAMMA_MIN:
				if (result[j].g.length) result[j].sum = jsapi.math.min(result[j].g);
				break;
			case GAMMA_AVG:
				if (result[j].g.length) result[j].sum = jsapi.math.avg(result[j].g);
				break;
			case GAMMA_MED:
				if (result[j].g.length) result[j].sum = jsapi.math.median(result[j].g);
				break;
			case GAMMA_MAD:
				if (result[j].g.length) result[j].sum = jsapi.math.mad(result[j].g);
				break;
			case GAMMA_PERCENTILE_95:
				if (result[j].g.length) result[j].sum = jsapi.math.percentile(result[j].g, 0.95);
				break;
			case GAMMA_PERCENTILE_99:
				if (result[j].g.length) result[j].sum = jsapi.math.percentile(result[j].g, 0.99);
				break;
			case GAMMA_RANGE:
				if (result[j].g.length) result[j].sum = jsapi.math.max(result[j].g) - jsapi.math.min(result[j].g);
				break;
			case GAMMA_STDDEV:
				if (result[j].g.length) result[j].sum = jsapi.math.stddev(result[j].g);
				break;
		}
		else if (!rules[j][1].length || (rules[j][1][0] + '').indexOf('LEVELS') < 0) missing_data = true;
		if (result[j].matches.length) {
			matched = false;
			for (var k=0; k<result[j].matches.length; k++) {
				target = data_ref.data[result[j].matches[k][0]];
				actual = this.data[result[j].matches[k][1]];
				switch (rules[j][2]) {
					case DELTA_E_MAX:
						if (result[j].E[k] == result[j].sum) matched = true;
						break;
					case DELTA_L_MAX:
						if (result[j].L[k] == result[j].sum) matched = true;
						break;
					case DELTA_A_MAX:
						if (result[j].a[k] == result[j].sum) matched = true;
						break;
					case DELTA_B_MAX:
						if (result[j].b[k] == result[j].sum) matched = true;
						break;
					case DELTA_CH_MAX:
						if (result[j].Ch[k] == result[j].sum) matched = true;
						break;
					case DELTA_C_MAX:
						if (result[j].C[k] == result[j].sum) matched = true;
						break;
					case DELTA_H_MAX:
						if (result[j].H[k] == result[j].sum) matched = true;
						break;
					case GAMMA_MAX:
						if (result[j].g[k] == result[j].sum) matched = true;
						break;
					case GAMMA_MIN:
						if (result[j].g[k] == result[j].sum) matched = true;
						break;
				};
				if (matched) {
					result[j].finalmatch = result[j].matches[k];
					break;
				};
			};
			if (matched) {
				this.report_html.push('<div class="sample_id">' + result[j].finalmatch[2].fill(String(number_of_sets).length) + '</div>');
				haspatchid = true;
				var colors = get_colors(target, actual, o, no_Lab, no_XYZ, gray_balance_cal_only, true, profile_wp_norm, wp_norm, absolute, cat, use_profile_wp_as_ref);
				target_Lab = colors.target_Lab;
				actual_Lab = colors.actual_Lab;
				target_rgb = jsapi.math.color.Lab2RGB(target_Lab[0], target_Lab[1], target_Lab[2], target_Lab2RGB_wp_1, target_Lab2RGB_src_wp_1, 255, true, cat);
				actual_rgb = jsapi.math.color.Lab2RGB(actual_Lab[0], actual_Lab[1], actual_Lab[2], actual_Lab2RGB_wp_1, actual_Lab2RGB_src_wp_1, 255, true, cat);
				target_rgb_html.push('<div class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');">&#160;</div>');
				actual_rgb_html.push('<div class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');">&#160;</div>');
			};
		}
		if (!target_rgb_html.length) {
			target_rgb_html.push('&#160;');
			actual_rgb_html.push('&#160;');
		};
		if (!haspatchid) this.report_html.push('<div class="sample_id">&#160;</div>');
		this.report_html.push('			</td>');
		this.report_html.push('			<td class="patch">' + target_rgb_html.join('') + '</td>');
		this.report_html.push('			<td class="patch">' + actual_rgb_html.join('') + '</td>');
		var bar_html = [];
		if (result[j].sum != null && rules[j][2] && rules[j][2].indexOf("GAMMA") < 0) {
			if (!rules[j][3] || (!rules[j][6] && rules[j][5] && rules[j][5].substr(3) != delta_calc_method.substr(3))) rgb = [204, 204, 204];
			else {
				var rgb = [0, 255, 0],
					step = 255 / (rules[j][3] + rules[j][3] / 2);
				if (Math.abs(result[j].sum) <= rules[j][3]) {
					rgb[0] += Math.min(step * Math.abs(result[j].sum), 255);
					rgb[1] -= Math.min(step * Math.abs(result[j].sum), 255);
					var maxrg = Math.max(rgb[0], rgb[1]);
					rgb[0] *= (255 / maxrg);
					rgb[1] *= (255 / maxrg);
					rgb[0] = Math.round(rgb[0]);
					rgb[1] = Math.round(rgb[1]);
				}
				else rgb = [255, 0, 0];
			};
			for (var l = 0; l < actual_rgb_html.length; l ++) {
				bar_html.push(Math.abs(result[j].sum).accuracy(2) > 0 ? '<span style="display: block; width: ' + Math.round(10 * Math.abs(result[j].sum).accuracy(2)) + 'px; background-color: rgb(' + rgb.join(', ') + '); border: 1px solid silver; border-top: none; border-bottom: none; padding: .125em 0 .125em 0; overflow: hidden;">&#160;</span>' : '&#160;');
			};
		};
		this.report_html.push('			<td><span class="' + (result[j].sum != null && rules[j][3] && (rules[j][6] || !rules[j][5] || rules[j][5].substr(3) == delta_calc_method.substr(3)) ? ((rules[j][2] ? Math.abs(result[j].sum).accuracy(2) < rules[j][3] : Math.abs(result[j].sum).accuracy(2) > rules[j][3]) ? 'ok' : (Math.abs(result[j].sum).accuracy(2) == rules[j][3] ? 'warn' : 'ko')) : 'statonly') + '">' + (result[j].sum != null ? result[j].htmlsum || result[j].sum.accuracy(2) : '&#160;') + '</span></td><td class="bar">' + (bar_html.join('') || '&#160;') + '</td><td class="' + (result[j].sum != null && (!rules[j][3] || (rules[j][2] ? Math.abs(result[j].sum) <= rules[j][3] : Math.abs(result[j].sum) >= rules[j][3])) ? (((rules[j][2] ? Math.abs(result[j].sum).accuracy(2) < rules[j][3] : Math.abs(result[j].sum).accuracy(2) > rules[j][3]) ? 'ok">OK <span class="checkmark">✔</span>' : (result[j].sum != null && rules[j][3] ? 'warn">OK \u26a0' : 'statonly">')) + '<span class="' + (rules[j][4] && (rules[j][2] ? Math.abs(result[j].sum) <= rules[j][4] : Math.abs(result[j].sum) >= rules[j][4]) ? 'checkmark' : 'hidden') + (rules[j][3] && rules[j][4] ? '">✔' : '">&#160;')) : 'ko">' + (result[j].sum != null ? 'NOT OK' : '') + ' <span class="checkmark">\u2716') + '</span></td>');
		this.report_html.push('		</tr>');
		if (rules[j][1] && rules[j][1].length > 1 && (rules[j][6] || rules[j][5].substr(3) == delta_calc_method.substr(3))) seen.push(rules[j][1].join(','));
	};
	this.report_html.push('	</table>');
	
	var pass, overachieve;
	for (var j=0; j<result.length; j++) {
		if (rules[j][6] || !rules[j][5] || rules[j][5].substr(3) == delta_calc_method.substr(3)) {
			if (!rules[j][3]) continue;
			if (missing_data || isNaN(result[j].sum) || (rules[j][2] ? Math.abs(result[j].sum) > rules[j][3] : Math.abs(result[j].sum) < rules[j][3])) pass = false;
			if (!rules[j][4]) continue;
			if (missing_data || isNaN(result[j].sum) || (rules[j][2] ? Math.abs(result[j].sum) > rules[j][4] : Math.abs(result[j].sum) < rules[j][4])) overachieve = false;
		}
		if (rules[j][5] && rules[j][5].substr(3) == delta_calc_method.substr(3)) for (var k=0; k<result[j].matches.length; k++) {
			if (rules[j][2].indexOf('_E_') > -1) {
				this.data[result[j].matches[k][1]].actual_DE = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].E[k]);
				this.data[result[j].matches[k][1]].tolerance_DE = rules[j][3];
			}
			else if (rules[j][2].indexOf('_L_') > -1) {
				this.data[result[j].matches[k][1]].actual_DL = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].L[k]);
				this.data[result[j].matches[k][1]].tolerance_DL = rules[j][3];
			}
			else if (rules[j][2].indexOf('_A_') > -1) {
				this.data[result[j].matches[k][1]].actual_Da = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].a[k]);
				this.data[result[j].matches[k][1]].tolerance_Da = rules[j][3];
			}
			else if (rules[j][2].indexOf('_B_') > -1) {
				this.data[result[j].matches[k][1]].actual_Db = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].b[k]);
				this.data[result[j].matches[k][1]].tolerance_Db = rules[j][3];
			}
			else if (rules[j][2].indexOf('_C_') > -1) {
				this.data[result[j].matches[k][1]].actual_DC = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].C[k]);
				this.data[result[j].matches[k][1]].tolerance_DC = rules[j][3];
			}
			else if (rules[j][2].indexOf('_H_') > -1) {
				this.data[result[j].matches[k][1]].actual_DH = Math.abs(rules[j][2].indexOf('_MAX') < 0 ? result[j].sum : result[j].H[k]);
				this.data[result[j].matches[k][1]].tolerance_DH = rules[j][3];
			}
		};
	};
	this.report_html.push('<div class="footer"><p><span class="' + (pass !== false ? 'ok"><span class="checkmark">✔</span> ' + criteria.passtext : 'ko"><span class="checkmark">\u2716</span> ' + (missing_data ? 'MISSING DATA' : criteria.failtext)) + '</span>' + ((overachieve !== false && criteria.passrecommendedtext) || (overachieve === false && criteria.failrecommendedtext) ? '<br /><span class="' + (overachieve !== false ? 'ok"><span class="checkmark">✔</span> ' + criteria.passrecommendedtext : 'info"><span class="checkmark">✘</span> ' + criteria.failrecommendedtext) + '</span>' : '') + '</p></div>');
	
	this.result_html = this.report_html.slice(result_start);
	this.report_html.push('	</div></div>');
	
	this.report_html.push('	<div class="overview">');
	this.report_html.push('	<h3 class="toggle" onclick="toggle(this)">Overview</h3>');
	this.report_html.push('	<table cellspacing="0" id="overview">');
	this.report_html.push('		<tr>');
	var device_labels = fields_match.slice(devstart, devend + 1),
		device_channels = device_labels.join('').replace(/(?:CMYK|RGB)_/g, '');
	this.report_html.push('			<th>#</th><th colspan="' + device_labels.length + '">Device Values</th><th colspan="' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '4' : '3') + '">Nominal Values</th><th colspan="2">&#160;</th><th colspan="' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '4' : '3') + '">Measured Values</th><th colspan="4">Color distance</th><th>&#160;</th>');
	this.report_html.push('		</tr>');
	this.report_html.push('		<tr>');
	if (mode == 'Lab')
		labels = 'L*,a*,b*';
	else if (mode == 'XYZ')
		labels = 'X,Y,Z';
	else if (mode == 'xyY')
		labels = 'x,y,Y';
	else if (mode == "Lu'v'")
		labels = "L*,u',v'";
	else if (mode == "ICtCp")
		labels = "I,Ct,Cp";
	this.report_html.push('			<th>&#160;</th><th>' + device_labels.join('</th><th>').replace(/\w+_/g, '') + '</th><th>' + labels.split(',').join('</th><th>') + '</th>' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '<th>γ</th>' : '') + '<th>&#160;</th><th>&#160;</th><th>' + labels.split(',').join('</th><th>') + '</th>' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '<th>γ</th>' : '') + '<th>Δ' + delta_L_desc + '</th>' + /* '<th>Δa</th><th>Δb</th>' + */ '<th>Δ' + delta_C_desc + '</th><th>Δ' + delta_H_desc + '</th><th>Δ' + delta_E_desc + '</th><th>&#160;</th>');
	this.report_html.push('		</tr>');
	var grayscale_values = [], gamut_values = [];
	for (var i=0, n=0; i<this.data.length; i++) {
		n++;
		target = data_ref.data[i];
		actual = this.data[i];
		var colors = get_colors(target, actual, o, no_Lab, no_XYZ, gray_balance_cal_only, true, profile_wp_norm, wp_norm, absolute, cat, use_profile_wp_as_ref);
		target_Lab = colors.target_Lab;
		actual_Lab = colors.actual_Lab;
		current_rgb = colors.current_rgb;
		current_cmyk = colors.current_cmyk;
		target_rgb = jsapi.math.color.Lab2RGB(target_Lab[0], target_Lab[1], target_Lab[2], target_Lab2RGB_wp_1, target_Lab2RGB_src_wp_1, 255, true, cat);
		actual_rgb = jsapi.math.color.Lab2RGB(actual_Lab[0], actual_Lab[1], actual_Lab[2], actual_Lab2RGB_wp_1, actual_Lab2RGB_src_wp_1, 255, true, cat);
		delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], delta_calc_method, null, null, null, absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'), (profile_wp || wp)[1], wp[1], cat);
		if (mode == 'Lab') {
			target_color = target_Lab;
			actual_color = actual_Lab;
			accuracy = 2;
		}
		else if (mode == 'XYZ' || mode == 'xyY' || mode == "Lu'v'" || mode == "ICtCp") {
			target_color = jsapi.math.color.Lab2XYZ(target_Lab[0], target_Lab[1], target_Lab[2], absolute && use_profile_wp_as_ref && profile_wp_norm_1);
			actual_color = jsapi.math.color.Lab2XYZ(actual_Lab[0], actual_Lab[1], actual_Lab[2], absolute && use_profile_wp_as_ref && profile_wp_norm_1);
			if (mode != "ICtCp") {
				target_color = [target_color[0] * 100, target_color[1] * 100, target_color[2] * 100];
				actual_color = [actual_color[0] * 100, actual_color[1] * 100, actual_color[2] * 100];
			}
			accuracy = 4;
			if (mode == 'xyY') {
				target_color = jsapi.math.color.XYZ2xyY(target_color[0], target_color[1], target_color[2], absolute && profile_wp_norm_1);
				actual_color = jsapi.math.color.XYZ2xyY(actual_color[0], actual_color[1], actual_color[2], absolute && wp_norm_1);
			}
			else if (mode == "Lu'v'") {
				target_color = jsapi.math.color.XYZ2Lu_v_(target_color[0], target_color[1], target_color[2], absolute && profile_wp_norm);
				actual_color = jsapi.math.color.XYZ2Lu_v_(actual_color[0], actual_color[1], actual_color[2], absolute && wp_norm);
			}
			if (mode == "ICtCp") {
				if (!absolute || use_profile_wp_as_ref) {
					target_color = jsapi.math.color.adapt(target_color[0], target_color[1], target_color[2], (absolute && use_profile_wp_as_ref) ? profile_wp_norm_1 : [0.9642, 1, 0.8249], "D65", cat);
					actual_color = jsapi.math.color.adapt(actual_color[0], actual_color[1], actual_color[2], (absolute && use_profile_wp_as_ref) ? profile_wp_norm_1 : [0.9642, 1, 0.8249], "D65", cat);
				}
				target_color = jsapi.math.color.XYZ2ICtCp(target_color[0] * ICtCp_lumi_target_scale, target_color[1] * ICtCp_lumi_target_scale, target_color[2] * ICtCp_lumi_target_scale);
				actual_color = jsapi.math.color.XYZ2ICtCp(actual_color[0] * ICtCp_lumi_scale, actual_color[1] * ICtCp_lumi_scale, actual_color[2] * ICtCp_lumi_scale);
			}
		}
		this.report_html.push('		<tr' + (i == this.data.length - 1 ? ' class="last-row"' : '') + '>');
		var bar_html = [], rgb;
		if (actual.tolerance_DE == null)
			actual.tolerance_DE = warn_deviation;
		if (actual.actual_DE == null)
			actual.actual_DE = delta.E;
		if (actual.delta == null)
			actual.delta = delta;
		if (warn_deviation != null) {
			rgb = [0, 255, 0];
			var step = 255 / (actual.tolerance_DE + actual.tolerance_DE / 2);
			if (actual.actual_DE <= actual.tolerance_DE) {
				rgb[0] += Math.min(step * actual.actual_DE, 255);
				rgb[1] -= Math.min(step * actual.actual_DE, 255);
				var maxrg = Math.max(rgb[0], rgb[1]);
				rgb[0] *= (255 / maxrg);
				rgb[1] *= (255 / maxrg);
				rgb[0] = Math.round(rgb[0]);
				rgb[1] = Math.round(rgb[1]);
			}
			else rgb = [255, 0, 0];
		}
		else rgb = [204, 204, 204];
		bar_html.push(actual.actual_DE.accuracy(2) > 0 ? '<span style="display: block; width: ' + Math.round(10 * actual.actual_DE.accuracy(2)) + 'px; background-color: rgb(' + rgb.join(', ') + '); border: 1px solid silver; border-top: none; border-bottom: none; padding: .125em 0 .125em 0; overflow: hidden;">&#160;</span>' : '&#160;');
		if (criteria.fields_match.join(',').indexOf('CMYK') > -1) 
			var device = current_cmyk;
		else {
			var device = current_rgb;
			// XXX Note that round(50 * 2.55) = 127, but
			// round(50 / 100 * 255) = 128 (the latter is what we want)!
			for (var j=0; j<device.length; j++) device[j] = Math.round(device[j] / 100.0 * 255);
		}
		if ((target.gamma && actual.gamma) ||
			(current_rgb[0] == 0 && current_rgb[1] == 0 && current_rgb[2] == 0) ||
			(current_rgb[0] == 255 && current_rgb[1] == 255 && current_rgb[2] == 255)) {
			grayscale_values.push([current_rgb, target, actual, target_Lab, actual_Lab, target_rgb, actual_rgb]);
		}
		gamut_values.push([n, device_channels, device, target_color, actual_Lab, actual_color, target_rgb, actual_rgb, delta_calc_method, delta.E]);
		this.report_html.push('			<td>' + n.fill(String(number_of_sets).length) + '</td><td>' + device.join('</td><td>') + '</td><td>' + target_color[0].accuracy(accuracy) + '</td><td>' + target_color[1].accuracy(accuracy) + '</td><td>' + target_color[2].accuracy(accuracy) + '</td>' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '<td>' + (target.gamma ? target.gamma.accuracy(2) : '&#160;') + '</td>' : '') + '<td class="patch" style="background-color: rgb(' + target_rgb[0] + ', ' + target_rgb[1] + ', ' + target_rgb[2] + ');"><div class="patch">&#160;</div></td><td class="patch" style="background-color: rgb(' + actual_rgb[0] + ', ' + actual_rgb[1] + ', ' + actual_rgb[2] + ');"><div class="patch">&#160;</div></td><td>' + actual_color[0].accuracy(accuracy) + '</td><td>' + actual_color[1].accuracy(accuracy) + '</td><td>' + actual_color[2].accuracy(accuracy) + '</td>' + (criteria.fields_match.join(',').indexOf('CMYK') < 0 ? '<td>' + (actual.gamma ? actual.gamma.accuracy(2) : '&#160;') + '</td>' : '') + '<td class="' + (actual.actual_DL != null ? (actual.actual_DL.accuracy(2) < actual.tolerance_DL ? 'ok' : (actual.actual_DL.accuracy(2) == actual.tolerance_DL ? 'warn' : 'ko')) : 'info') + '">' + delta.Lw.accuracy(2) + '</td>' + /* '<td class="' + (actual.actual_Da != null ? (actual.actual_Da.accuracy(2) < actual.tolerance_Da ? 'ok' : (actual.actual_Da.accuracy(2) == actual.tolerance_Da ? 'warn' : 'ko')) : 'info') + '">' + delta.a.accuracy(2) + '</td><td class="' + (actual.actual_Db != null ? (actual.actual_Db.accuracy(2) < actual.tolerance_Db ? 'ok' : (actual.actual_Db.accuracy(2) == actual.tolerance_Db ? 'warn' : 'ko')) : 'info') + '">' + delta.b.accuracy(2) + '</td>' + */ '<td class="' + (actual.actual_DC != null ? (actual.actual_DC.accuracy(2) < actual.tolerance_DC ? 'ok' : (actual.actual_DC.accuracy(2) == actual.tolerance_DC ? 'warn' : 'ko')) : 'info') + '">' + delta.Cw.accuracy(2) + '</td><td class="' + (actual.actual_DH != null ? (actual.actual_DH.accuracy(2) < actual.tolerance_DH ? 'ok' : (actual.actual_DH.accuracy(2) == actual.tolerance_DH ? 'warn' : 'ko')) : 'info') + '">' + delta.Hw.accuracy(2) + '</td><td class="' + (actual.actual_DE != null && actual.tolerance_DE != null ? (actual.actual_DE.accuracy(2) < actual.tolerance_DE ? 'ok' : (actual.actual_DE.accuracy(2) == actual.tolerance_DE ? 'warn' : 'ko')) : (!warn_deviation || delta.E < warn_deviation ? 'info' : 'warn')) + '">' + delta.E.accuracy(2) + '</td><td class="bar">' + bar_html.join('') + '</td>');
		this.report_html.push('		</tr>');
	};
	this.report_html.push('	</table>');
	this.report_html.push('	</div>');
	
	if (grayscale_values.length) {
		grayscale_values.sort(function(a, b) {
			// Compare signal level
			if (a[0][0] < b[0][0]) return -1;
			if (a[0][0] > b[0][0]) return 1;
			// If same signal level, compare target L*
			if (a[3][0] < b[3][0]) return -1;
			if (a[3][0] > b[3][0]) return 1;
			return 0;
		});
		
		// CCT
		var CCT = [], hwidth = 100 / 18, width = (100 - hwidth) / grayscale_values.length, rows = 17, start = 10500, end = 2500, rstep = (start - end) / (rows - 1), rowh = 30;
		CCT.push('	<div class="CCT graph">');
		CCT.push('	<h3 class="toggle" onclick="toggle(this)">Correlated Color Temperature</h3>');
		CCT.push('	<table cellspacing="0" id="CCT" style="' + bggridlines(rowh) + 'height: ' + rowh * (rows + 1) + 'px;">');
		CCT.push('<tr><th style="width: ' + hwidth + '%; height: ' + rowh + 'px">' + start + 'K</th>');
		debug && window.console && console.log('CCT');
		for (var i = 0; i < grayscale_values.length; i ++) {
			var target_XYZ = jsapi.math.color.Lab2XYZ(grayscale_values[i][3][0], grayscale_values[i][3][1], grayscale_values[i][3][2], absolute && use_profile_wp_as_ref && profile_wp_norm, 100.0),
				actual_XYZ = jsapi.math.color.Lab2XYZ(grayscale_values[i][4][0], grayscale_values[i][4][1], grayscale_values[i][4][2], absolute && use_profile_wp_as_ref && profile_wp_norm, 100.0);
			if (!absolute) {
				// Make absolute
				target_XYZ = jsapi.math.color.adapt(target_XYZ[0], target_XYZ[1], target_XYZ[2], [96.42, 100, 82.49], profile_wp_norm, cat);
				actual_XYZ = jsapi.math.color.adapt(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2], [96.42, 100, 82.49], wp_norm, cat);
			}
			debug && window.console && console.log('Target XYZ', target_XYZ.join(', '), 'Actual XYZ', actual_XYZ.join(', '));
			var target_CCT = jsapi.math.color.XYZ2CorColorTemp(target_XYZ[0], target_XYZ[1], target_XYZ[2]),
				actual_CCT = jsapi.math.color.XYZ2CorColorTemp(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2]),
				target_Lab = jsapi.math.color.XYZ2Lab(target_XYZ[0], target_XYZ[1], target_XYZ[2], absolute && use_profile_wp_as_ref && profile_wp_norm),
				actual_Lab = jsapi.math.color.XYZ2Lab(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2], absolute && use_profile_wp_as_ref && profile_wp_norm),
				delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], delta_calc_method, null, null, null, (absolute && use_profile_wp_as_ref && profile_wp_norm_1) || 'D50', (profile_wp || wp)[1], wp[1], cat),
				delta_CH = Math.sqrt(Math.pow(delta.Cw, 2) + Math.pow(delta.Hw, 2));
			var rgb = jsapi.math.color.XYZ2RGB(actual_XYZ[0] / actual_XYZ[1] * 0.75, actual_XYZ[1] / actual_XYZ[1] * 0.75, actual_XYZ[2] / actual_XYZ[1] * 0.75, null, 255), brgb = [];
			for (var j = 0; j < 3; j ++)
				brgb[j] = Math.round(rgb[j] * .8);
			CCT.push('<td rowspan="' + rows + '" style="width: ' + width + '%;" data-title="Level: ' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '%\nNominal: ' + (target_CCT > -1 ? target_CCT.accuracy(0) + 'K' : 'Cannot compute CCT (XYZ out of range)') + '\nMeasured: ' + (actual_CCT > -1 ? actual_CCT.accuracy(0) + 'K' : 'Cannot compute CCT (XYZ out of range)') + '\nΔ' + strip_tags(delta_C_desc) + ': ' + delta.Cw.accuracy(2) + '\nΔ' + strip_tags(delta_H_desc) + ': ' + delta.Hw.accuracy(2) + '"><div class="col" style="height: ' + rowh * rows + 'px;"><div class="ref" style="bottom: ' + Math.min((target_CCT - end) / rstep * rowh + rowh / 2, rowh * rows) + 'px;"></div><div class="act" style="background-color: rgb(' + rgb.join(', ') + '); border-color: rgb(' + brgb.join(', ') + '); bottom: ' + Math.min((actual_CCT - end) / rstep * rowh + rowh / 2, rowh * rows) + 'px;"></div></div></td>');
		}
		CCT.push('</tr>');
		for (var i = start - rstep; i >= end; i -= rstep) {
			CCT.push('<tr><th style="height: ' + rowh + 'px">' + i + 'K</th></tr>');
		}
		CCT.push('<tr class="x"><th style="height: ' + rowh + 'px">%</th>');
		for (var i = 0; i < grayscale_values.length; i ++) {
			CCT.push('<td>' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '</td>');
		}
		CCT.push('</tr></table></div>');
		//var idx = this.report_html.indexOf('	<div class="overview">');
		//this.report_html.splice(idx, 0, CCT.join('\n'));
		this.report_html = this.report_html.concat(CCT);
		
		// Gamma tracking
		var numgamma = 0, gamma_max = 3, gamma_min = 1.4;
		for (var i = 0; i < grayscale_values.length; i ++) {
			if (grayscale_values[i][1].gamma && grayscale_values[i][2].gamma) {
				numgamma ++;
				gamma_max = Math.max(gamma_max, grayscale_values[i][1].gammaR, grayscale_values[i][2].gammaR, grayscale_values[i][1].gammaG, grayscale_values[i][2].gammaG, grayscale_values[i][1].gammaB, grayscale_values[i][2].gammaB);
				gamma_min = Math.min(gamma_min, grayscale_values[i][1].gammaR, grayscale_values[i][2].gammaR, grayscale_values[i][1].gammaG, grayscale_values[i][2].gammaG, grayscale_values[i][1].gammaB, grayscale_values[i][2].gammaB);
			}
		}
		if (numgamma > 0) {
		var gamma_tracking = [], hwidth = 100 / 31, width = (100 - hwidth) / numgamma, start = Math.ceil(gamma_max * 10), end = Math.floor(gamma_min * 10), rows = start - end + 1, rstep = (start - end) / (rows - 1), rowh = 30;
		gamma_tracking.push('	<div class="gamma_tracking graph">');
		gamma_tracking.push('	<h3 class="toggle" onclick="toggle(this)">Gamma</h3>');
		gamma_tracking.push('	<table cellspacing="0" id="gamma_tracking" style="' + bggridlines(rowh) + 'height: ' + rowh * (rows + 1) + 'px;">');
		gamma_tracking.push('<tr><th style="width: ' + hwidth + '%; height: ' + rowh + 'px">' + (start / 10).toFixed(1) + '</th>');
		for (var i = 0; i < grayscale_values.length; i ++) {
			if (!grayscale_values[i][1].gamma || !grayscale_values[i][2].gamma) continue;
			var target_Lab = grayscale_values[i][3],
				actual_Lab = grayscale_values[i][4],
				target_gamma = grayscale_values[i][1].gamma,
				actual_gamma = grayscale_values[i][2].gamma,
				gamma = 2.2 + target_gamma - actual_gamma,
				Eprime = Math.pow(Math.pow(0.75, 2.2), (1 / gamma)),
				rgb = [],
				brgb = [],
				delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], delta_calc_method, null, null, null, absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'), (profile_wp || wp)[1], wp[1], cat);
			for (var j = 0; j < 3; j ++) {
				rgb.push(Math.round(Eprime * 255));
				brgb.push(Math.round(Eprime * 204));
			}
			gamma_tracking.push('<td rowspan="' + rows + '" style="width: ' + width + '%;" data-title="Level: ' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '%\nNominal: Gamma ' + grayscale_values[i][1].gamma.accuracy(2) + '\nMeasured: Gamma ' + grayscale_values[i][2].gamma.accuracy(2) + (get_gammaRGB ? '\nR: ' + grayscale_values[i][2].gammaR.accuracy(2) + '\nG: ' + grayscale_values[i][2].gammaG.accuracy(2) + '\nB: ' + grayscale_values[i][2].gammaB.accuracy(2) : '') + '\nΔ' + strip_tags(delta_L_desc) + ': ' + delta.Lw.accuracy(2) + '"><div class="col" style="height: ' + rowh * rows + 'px;"><div class="ref" style="bottom: ' + ((grayscale_values[i][1].gamma * 10 - end) / rstep * rowh + rowh / 2) + 'px;"></div><div class="act" style="bottom: ' + ((grayscale_values[i][2].gamma * 10 - end) / rstep * rowh + rowh / 2) + 'px; background-color: rgb(' + rgb.join(', ') + '); border-color: rgb(' + brgb.join(', ') + ');"></div>' + (get_gammaRGB ? '<div class="act" style="bottom: ' + ((grayscale_values[i][2].gammaR * 10 - end) / rstep * rowh + rowh / 2) + 'px; background-color: #f00; border-color: #c00;"></div><div class="act" style="bottom: ' + ((grayscale_values[i][2].gammaG * 10 - end) / rstep * rowh + rowh / 2) + 'px; background-color: #0f0; border-color: #0c0;"></div><div class="act" style="bottom: ' + ((grayscale_values[i][2].gammaB * 10 - end) / rstep * rowh + rowh / 2) + 'px; background-color: #00a0ff; border-color: #0080ff;"></div>' : '') + '</div></td>');
		}
		gamma_tracking.push('</tr>');
		for (var i = start - rstep; i >= end; i -= rstep) {
			gamma_tracking.push('<tr><th style="height: ' + rowh + 'px">' + (i / 10).toFixed(1) + '</th></tr>');
		}
		gamma_tracking.push('<tr class="x"><th>%</th>');
		for (var i = 0; i < grayscale_values.length; i ++) {
			if (!grayscale_values[i][1].gamma || !grayscale_values[i][2].gamma) continue;
			gamma_tracking.push('<td>' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '</td>');
		}
		gamma_tracking.push('</tr></table></div>');
		//var idx = this.report_html.indexOf('	<div class="overview">');
		//this.report_html.splice(idx, 0, gamma_tracking.join('\n'));
		this.report_html = this.report_html.concat(gamma_tracking);
		} // numgamma > 0
		
		// RGB Balance
		var rgb_balance = [], hwidth = 100 / 21, width = (100 - hwidth) / grayscale_values.length, rows = 17, start = 40, end = -40, rstep = (start - end) / (rows - 1), rowh = 30, actual_white_Y = jsapi.math.color.Lab2XYZ(grayscale_values[grayscale_values.length - 1][4][0], 0, 0)[1];
		rgb_balance.push('	<div class="rgb_balance graph">');
		rgb_balance.push('	<h3 class="toggle" onclick="toggle(this)">RGB Gray Balance</h3>');
		rgb_balance.push('	<table cellspacing="0" id="rgb_balance" style="' + bggridlines(rowh) + 'height: ' + rowh * (rows + 1) + 'px;">');
		rgb_balance.push('<tr><th style="width: ' + hwidth + '%; height: ' + rowh + 'px">+' + start + '%</th>');
		debug && window.console && console.log('RGB Gray Balance');
		for (var i = 0; i < grayscale_values.length; i ++) {
			var target_Lab = grayscale_values[i][3],
				actual_Lab = grayscale_values[i][4],
				target_XYZ = jsapi.math.color.Lab2XYZ(target_Lab[0], target_Lab[1], target_Lab[2], absolute && use_profile_wp_as_ref && profile_wp_norm, 100.0),
				actual_XYZ = jsapi.math.color.Lab2XYZ(actual_Lab[0], actual_Lab[1], actual_Lab[2], absolute && use_profile_wp_as_ref && profile_wp_norm, 100.0),
				target_rgb = [target_XYZ[0] / target_XYZ[1], target_XYZ[1] / target_XYZ[1], target_XYZ[2] / target_XYZ[1]],
				//target_rgb = jsapi.math.color.XYZ2RGB(target_rgb[0], target_rgb[1], target_rgb[2], absolute && wp_norm_1, 1, false, false),
				target_rgb = jsapi.math.color.xyz_to_rgb_matrix(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, (absolute && wp_norm_1) || "D65", 1.0).multiply(target_rgb),
				fact = 1,
				actual_xyY = jsapi.math.color.XYZ2xyY(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2]),
				actual_rgb = [actual_xyY[0] / actual_xyY[1] * fact, fact, (1 - (actual_xyY[0] + actual_xyY[1])) / actual_xyY[1] * fact],
				//actual_rgb = jsapi.math.color.XYZ2RGB(actual_rgb[0], actual_rgb[1], actual_rgb[2], absolute && wp_norm_1, 1, false, false),
				actual_rgb = jsapi.math.color.xyz_to_rgb_matrix(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, (absolute && wp_norm_1) || "D65", 1.0).multiply(actual_rgb),
				delta = jsapi.math.color.delta(target_Lab[0], target_Lab[1], target_Lab[2], actual_Lab[0], actual_Lab[1], actual_Lab[2], delta_calc_method, null, null, null, absolute && (use_profile_wp_as_ref ? profile_wp_norm_1 : 'D50'), (profile_wp || wp)[1], wp[1], cat);
			debug && window.console && console.log('Target XYZ', target_XYZ.join(', '), 'Actual XYZ', actual_XYZ.join(', '));
			debug && window.console && console.log('Target RGB', target_rgb.join(', '), 'Actual RGB', actual_rgb.join(', '));
			if (isNaN(jsapi.math.min(target_rgb)) || isNaN(jsapi.math.min(actual_rgb))) {
				rgb_balance.push('<td rowspan="' + rows + '" style="width: ' + width + '%;" data-title="Level: ' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '%\nΔ' + strip_tags(delta_C_desc) + ': ' + delta.Cw.accuracy(2) + '\nΔ' + strip_tags(delta_H_desc) + ': ' + delta.Hw.accuracy(2) + '"></td>');
				continue;
			}
			rgb_balance.push('<td rowspan="' + rows + '" style="width: ' + width + '%;" data-title="Level: ' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '%\nR: ' + (actual_rgb[0] - target_rgb[0] > 0 ? '+' : '') + ((actual_rgb[0] - target_rgb[0]) * 100).accuracy(2) + '%\nG: ' + (actual_rgb[1] - target_rgb[1] > 0 ? '+' : '') + ((actual_rgb[1] - target_rgb[1]) * 100).accuracy(2) + '%\nB: ' + (actual_rgb[2] - target_rgb[2] > 0 ? '+' : '') + ((actual_rgb[2] - target_rgb[2]) * 100).accuracy(2) + '%\nΔ' + strip_tags(delta_C_desc) + ': ' + delta.Cw.accuracy(2) + '\nΔ' + strip_tags(delta_H_desc) + ': ' + delta.Hw.accuracy(2) + '"><div class="col" style="height: ' + rowh * rows + 'px;"><div class="ref" style="bottom: ' + rowh * rows / 2 + 'px;"></div><div class="act" style="bottom: ' + (rowh * rows / 2 + (actual_rgb[0] - target_rgb[0]) * 100 * rowh / rstep) + 'px; background-color: #f00; border-color: #c00;"></div><div class="act" style="bottom: ' + (rowh * rows / 2 + (actual_rgb[1] - target_rgb[1]) * 100 * rowh / rstep) + 'px; background-color: #0f0; border-color: #0c0;"></div><div class="act" style="bottom: ' + (rowh * rows / 2 + (actual_rgb[2] - target_rgb[2]) * 100 * rowh / rstep) + 'px; background-color: #00a0ff; border-color: #0080ff;"></div></div></td>');
		}
		rgb_balance.push('</tr>');
		for (var i = start - rstep; i >= end; i -= rstep) {
			rgb_balance.push('<tr><th style="height: ' + rowh + 'px">' + (i > 0 ? '+' : '') + i + '%</th></tr>');
		}
		rgb_balance.push('<tr class="x"><th>%</th>');
		for (var i = 0; i < grayscale_values.length; i ++) {
			rgb_balance.push('<td>' + (grayscale_values[i][0][0] / 255 * 100).accuracy(0) + '</td>');
		}
		rgb_balance.push('</tr></table></div>');
		//var idx = this.report_html.indexOf('	<div class="overview">');
		//this.report_html.splice(idx, 0, rgb_balance.join('\n'));
		this.report_html = this.report_html.concat(rgb_balance);
	}
	
	if (gamut_values.length) {
		var accuracy, offset, multiplier;
		switch (mode) {
			case "Lu'v'":
				xy = "u'v'";
				accuracy = 4;
				offset = [10, 95];
				multiplier = 1200;
				break;
			case 'XYZ':
				xy = 'XZ';
				accuracy = 2;
				offset = [5, 95];
				multiplier = 8;
				break;
			case 'xyY':
				xy = 'xy';
				accuracy = 4;
				offset = [10, 95];
				multiplier = 1000;
				break;
			case "ICtCp":
				xy = 'CtCp';
				accuracy = 4;
				offset = [50, 50];
				multiplier = 1000;
				break;
			default:
				xy = 'a*b*';
				accuracy = 2;
				offset = [50, 50];
				multiplier = 3;
		}
		this.report_html.push('	<div class="gamut graph">');
		this.report_html.push('	<h3 class="toggle" onclick="toggle(this)">Gamut ' + xy + '</h3>');
		this.report_html.push('	<div class="canvas" id="gamut" style="height: 900px;"><div class="inner" style="left: ' + offset[0] + '%; top: ' + offset[1] + '%;"><div class="overlay" style="left: -' + offset[0] * 9 + 'em; top: -' + offset[1] * 9 + 'em;"></div>');
		// Sort by L*
		gamut_values.sort(function (a, b) {
			if (a[4][0] < b[4][0]) return -1;
			if (a[4][0] > b[4][0]) return 1;
			return 0;
		});
		for (var i = 0; i < gamut_values.length; i ++) {
			var n = gamut_values[i][0],
				device_channels = gamut_values[i][1],
				device = gamut_values[i][2],
				target_color = gamut_values[i][3],
				target_xy,
				actual_color = gamut_values[i][5],
				actual_xy,
				target_rgb = gamut_values[i][6],
				actual_rgb = gamut_values[i][7],
				delta_calc_method = gamut_values[i][8],
				deltaE = gamut_values[i][9];
			switch (mode) {
				case 'XYZ':
					target_xy = [target_color[2], target_color[0]];
					actual_xy = [actual_color[2], actual_color[0]];
					break;
				case 'xyY':
					target_xy = target_color;
					actual_xy = actual_color;
					break;
				default:
					target_xy = target_color.slice(1);
					actual_xy = actual_color.slice(1);
			}
			this.report_html.push('<div class="wrap" style="left: ' + (target_xy[0] * multiplier).accuracy(8) + 'em; bottom: ' + (target_xy[1] * multiplier).accuracy(8) + 'em;" data-title="#' + n.fill(String(number_of_sets).length) + ' ' + device_channels + ': ' + device.join(' ') + '\nNominal ' + labels.split(',').join('') + ': ' + [target_color[0].accuracy(accuracy), target_color[1].accuracy(accuracy), target_color[2].accuracy(accuracy)].join(' ') + '\n(Measured ' + labels.split(',').join('') + ': ' + [actual_color[0].accuracy(accuracy), actual_color[1].accuracy(accuracy), actual_color[2].accuracy(accuracy)].join(' ') + ')\nΔ' + strip_tags(delta_E_desc) + ': ' + deltaE.accuracy(2) + '"><div class="ref patch-' + i + '" data-index="' + i + '" data-bgcolor="rgb(' + target_rgb.join(', ') + ')" data-bordercolor="rgb(' + [Math.round(target_rgb[0] * .8), Math.round(target_rgb[1] * .8), Math.round(target_rgb[2] * .8)].join(', ') + ')"></div></div><div class="wrap wrap-act" style="left: ' + (actual_xy[0] * multiplier).accuracy(8) + 'em; bottom: ' + (actual_xy[1] * multiplier).accuracy(8) + 'em;" data-title="#' + n.fill(String(number_of_sets).length) + ' ' + device_channels + ': ' + device.join(' ') + '\nMeasured ' + labels.split(',').join('') + ': ' + [actual_color[0].accuracy(accuracy), actual_color[1].accuracy(accuracy), actual_color[2].accuracy(accuracy)].join(' ') + '\n(Nominal ' + labels.split(',').join('') + ': ' + [target_color[0].accuracy(accuracy), target_color[1].accuracy(accuracy), target_color[2].accuracy(accuracy)].join(' ') + ')\nΔ' + strip_tags(delta_E_desc) + ': ' + deltaE.accuracy(2) + '"><div class="act patch-' + i + '" data-index="' + i + '" style="background-color: rgb(' + actual_rgb.join(', ') + '); border-color: rgb(' + [Math.round(actual_rgb[0] * .8), Math.round(actual_rgb[1] * .8), Math.round(actual_rgb[2] * .8)].join(', ') + ');"></div></div>');
		}
		this.report_html.push('	</div></div>');
	}
	
	return this.report_html.join('\n')
};

function bggridlines(rowh) {
	return window.btoa ? 'background-image: url(data:image/svg+xml;base64,' + btoa('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" width="10px" height="' + rowh + 'px" viewBox="0 0 10 ' + rowh + '"><line opacity="0.5" stroke="#999999" x1="0" y1="' + rowh / 2 + '" x2="10" y2="' + rowh / 2 + '"/></svg>') + ');' : '';
};

function trim(txt) {
	return txt.replace(/^\s+|\s+$/g, "")
};

function lf2cr(txt) {
	return txt.replace(/\r\n/g, "\r").replace(/\n/g, "\r")
};

function cr2lf(txt) {
	// CR LF = Windows
	// CR = Mac OS 9
	// LF = Unix/Linux/Mac OS X
	return txt.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
};

function compact(txt, collapse_whitespace) {
	txt = trim(txt).replace(/\n\s+|\s+\n/g, "\n");
	return collapse_whitespace?txt.replace(/\s+/g, " "):txt
};

function comma2point(txt) {
	return decimal(txt)
};

function decimal(txt, sr, re) {
	if (!sr) sr = "\\,";
	if (!re) re = ".";
	return txt.replace(new RegExp("((^|\\s)\\-?\\d+)"+sr+"(\\d+(\\s|$))", "g"), "$1"+re+"$3")
};

function toarray(txt, level) {
	txt=comma2point(compact(cr2lf(txt)));
	if (!txt) return [];
	if (level) {
		txt=txt.split(/\s/)
	}
	else {
		txt=txt.split("\n");
		for (var i=0; i<txt.length; i++) {
			txt[i]=txt[i].split(/\s+/);
			for (var j=0; j<txt[i].length; j++) {
				parsed=parseFloat(txt[i][j]);
				if (!isNaN(parsed)) txt[i][j]=parsed;
			}
		}
	};
	return txt
};

function fromarray(array, level) {
	array = array.clone();
	if (level) return array.join("\t");
	for (var i=0; i<array.length; i++) array[i]=array[i].join("\t");
	return array.join("\n")
};

function analyze(which) {
	var f=document.forms,
		e=f['F_out'].elements,fv,i,j,v,s;
	
	if (!trim(f["F_data"].elements["FF_data_in"].value) || !trim(f["F_data"].elements["FF_data_ref"].value)) return;
	
	if (!get_data(which)) {
		if (which == "r" || !which) {
			if (trim(f['F_data'].elements['FF_data_ref'].value)) {
				if (!data_ref.data_format.length) set_status("Reference data: No or invalid data format.");
				else if (!data_ref.data.length) set_status("Reference data: No or invalid values.")
			};
		};
		if (which == "i" || !which) {
			if (trim(f['F_data'].elements['FF_data_in'].value)) {
				if (!data_in.data_format.length) set_status("Measurement data: No or invalid data format.");
				else if (!data_in.data.length) set_status("Measurement data: No or invalid values.")
			};
		}
	};
	
	var _criteria = [];
	for (var id in comparison_criteria) {
		if (comparison_criteria[id] && comparison_criteria[id].name && _criteria.indexOf(comparison_criteria[id]) < 0) {
			for (var i=0; i<comparison_criteria[id].fields_match.length; i++) {
				if (data_ref.data_format.indexOf(comparison_criteria[id].fields_match[i]) < 0) 
					break;
				else if (fields_match.indexOf(comparison_criteria[id].fields_match[i]) < 0)
					fields_match.push(comparison_criteria[id].fields_match[i]);
			};
			if (i == comparison_criteria[id].fields_match.length) {
				_criteria.push(comparison_criteria[id])
			}
		}
	};
	for (var i=0; i<_criteria.length; i++) {
		e['FF_criteria'].options[i] = new Option(_criteria[i].name, _criteria[i].id); //, data_ref.id == _criteria[i].id, data_ref.id == _criteria[i].id);
		if (data_ref.id == _criteria[i].id) e['FF_criteria'].selectedIndex = i;
	};
	
	var criteria = comparison_criteria[e['FF_criteria'].value],
		fields_extract_r = fields_match.slice().concat(criteria.fields_compare),
		fields_extract_i = fields_match.slice().concat(criteria.fields_compare);
	
	for (i=0; i<fields_extract_i.length; i++) {
		for (j=0; j<data_in.data_format.length; j++) {
			if (data_in.data_format[j]==fields_extract_i[i]) {
				fields_extract_indexes_i.push(j);
				break
			}
		}
	};
	for (i=0; i<fields_extract_r.length; i++) {
		for (j=0; j<data_ref.data_format.length; j++) {
			if (data_ref.data_format[j]==fields_extract_r[i]) {
				fields_extract_indexes_r.push(j);
				break
			}
		}
	};
	
	if (data_in.data.length && data_ref.data.length && data_in.data.length != data_ref.data.length) {
		alert("Different amount of sets in measurements and reference data.");
		return false
	};
	var data_in_format_missing_fields = [], data_ref_format_missing_fields = [], errortxt = "";
	for (i = 0; i < fields_extract_i.length; i ++) {
		if (data_in.data_format.indexOf(fields_extract_i[i]) < 0) data_in_format_missing_fields.push(fields_extract_i[i]);
		if (data_ref.data_format.indexOf(fields_extract_i[i]) < 0) data_ref_format_missing_fields.push(fields_extract_i[i]);
	};
	if (data_in_format_missing_fields.length) {
		errortxt += "Measurement data is missing the following fields: " + data_in_format_missing_fields.join(", ") + ".\n"
	}
	if (data_ref_format_missing_fields.length) {
		errortxt += "Reference data is missing the following fields: " + data_ref_format_missing_fields.join(", ") + ".\n"
	};
	if (errortxt) {
		alert(errortxt + "Measurements and reference data must contain atleast: " + fields_extract_i.join(", "));
		return
	};
	
	if (data_ref.data_format.length && data_ref.data.length && data_in.data_format.length && data_in.data.length) {
		compare();
	};
};

function get_colors(target, actual, o, no_Lab, no_XYZ, gray_balance_cal_only, skip_gamma, profile_wp_norm, wp_norm, absolute, cat, use_profile_wp_as_ref) {
	var target_Lab, actual_Lab, target_XYZ, actual_XYZ, current_rgb, current_cmyk = [];
	target_Lab = [target[fields_extract_indexes_r[o + 1]], target[fields_extract_indexes_r[o + 2]], target[fields_extract_indexes_r[o + 3]]];
	actual_Lab = [actual[fields_extract_indexes_i[o + 1]], actual[fields_extract_indexes_i[o + 2]], actual[fields_extract_indexes_i[o + 3]]];
	if (no_Lab && !no_XYZ) {
		target_XYZ = jsapi.math.color.adapt(target_Lab[0], target_Lab[1], target_Lab[2], profile_wp_norm, [96.42, 100, 82.49], cat);
		actual_XYZ = jsapi.math.color.adapt(actual_Lab[0], actual_Lab[1], actual_Lab[2], wp_norm, [96.42, 100, 82.49], cat);
		target_Lab = jsapi.math.color.XYZ2Lab(target_XYZ[0], target_XYZ[1], target_XYZ[2]);
		actual_Lab = jsapi.math.color.XYZ2Lab(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2]);
	}
	if (fields_match.join(',').indexOf('RGB') == 0) {
		current_rgb = [actual[fields_extract_indexes_i[0]], actual[fields_extract_indexes_i[1]], actual[fields_extract_indexes_i[2]]];
		if (fields_match.join(',').indexOf('CMYK') > -1) 
			current_cmyk = [actual[fields_extract_indexes_i[3]], actual[fields_extract_indexes_i[4]], actual[fields_extract_indexes_i[5]], actual[fields_extract_indexes_i[6]]];
	}
	else {
		current_rgb = [actual[fields_extract_indexes_i[4]], actual[fields_extract_indexes_i[5]], actual[fields_extract_indexes_i[6]]];
		if (fields_match.join(',').indexOf('CMYK') > -1) 
			current_cmyk = [actual[fields_extract_indexes_i[0]], actual[fields_extract_indexes_i[1]], actual[fields_extract_indexes_i[2]], actual[fields_extract_indexes_i[3]]];
	}
	for (var l=0; l<current_rgb.length; l++) current_rgb[l] = current_rgb[l].accuracy(2);
	for (var l=0; l<current_cmyk.length; l++) current_cmyk[l] = current_cmyk[l].accuracy(2);
	if (current_rgb[0] == current_rgb[1] && current_rgb[1] == current_rgb[2]) {
		if (gray_balance_cal_only) {
			target_Lab[0] = actual_Lab[0]; // set L to measured value
			target_Lab[1] = target_Lab[2] = 0; // set a=b=0
		}
	}
	if (absolute) {
		target_XYZ = jsapi.math.color.Lab2XYZ(target_Lab[0], target_Lab[1], target_Lab[2], null, 100.0);
		target_XYZ = jsapi.math.color.adapt(target_XYZ[0], target_XYZ[1], target_XYZ[2], [96.42, 100, 82.49], profile_wp_norm, cat);
		target_Lab = jsapi.math.color.XYZ2Lab(target_XYZ[0], target_XYZ[1], target_XYZ[2], use_profile_wp_as_ref && profile_wp_norm);
		actual_XYZ = jsapi.math.color.Lab2XYZ(actual_Lab[0], actual_Lab[1], actual_Lab[2], null, 100.0);
		actual_XYZ = jsapi.math.color.adapt(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2], [96.42, 100, 82.49], wp_norm, cat);
		actual_Lab = jsapi.math.color.XYZ2Lab(actual_XYZ[0], actual_XYZ[1], actual_XYZ[2], use_profile_wp_as_ref && profile_wp_norm);
	}
	if (current_rgb[0] == current_rgb[1] && current_rgb[1] == current_rgb[2]) {
		if (!skip_gamma && !current_cmyk.length && current_rgb[0] > 0 && current_rgb[0] < 100 && target_Lab[0] > 0 && actual_Lab[0] > 0) {
			if (!absolute) {
				target_XYZ = jsapi.math.color.Lab2XYZ(target_Lab[0], target_Lab[1], target_Lab[2], null, 100.0);
				actual_XYZ = jsapi.math.color.Lab2XYZ(actual_Lab[0], actual_Lab[1], actual_Lab[2], null, 100.0);
			}
			target.gamma = Math.log(target_XYZ[1] / 100) / Math.log(current_rgb[0] / 100);
			actual.gamma = Math.log(actual_XYZ[1] / 100) / Math.log(current_rgb[0] / 100);
			if (get_gammaRGB) {
				var profile_wp_norm_1 = [profile_wp_norm[0] / 100.0, profile_wp_norm[1] / 100.0, profile_wp_norm[2] / 100.0],
					wp_norm_1 = [wp_norm[0] / 100.0, wp_norm[1] / 100.0, wp_norm[2] / 100.0],
					target_RGB = jsapi.math.color.xyz_to_rgb_matrix(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, (absolute && profile_wp_norm_1) || "D50", 1.0).multiply(target_XYZ),
					actual_RGB = jsapi.math.color.xyz_to_rgb_matrix(0.6400, 0.3300, 0.3000, 0.6000, 0.1500, 0.0600, (absolute && wp_norm_1) || "D50", 1.0).multiply(actual_XYZ);
				target.gammaR = Math.log(target_RGB[0] / 100) / Math.log(current_rgb[0] / 100);
				target.gammaG = Math.log(target_RGB[1] / 100) / Math.log(current_rgb[0] / 100);
				target.gammaB = Math.log(target_RGB[2] / 100) / Math.log(current_rgb[0] / 100);
				actual.gammaR = Math.log(actual_RGB[0] / 100) / Math.log(current_rgb[0] / 100);
				actual.gammaG = Math.log(actual_RGB[1] / 100) / Math.log(current_rgb[0] / 100);
				actual.gammaB = Math.log(actual_RGB[2] / 100) / Math.log(current_rgb[0] / 100);
			}
			else {
				target.gammaR = target.gamma;
				target.gammaG = target.gamma;
				target.gammaB = target.gamma;
				actual.gammaR = actual.gamma;
				actual.gammaG = actual.gamma;
				actual.gammaB = actual.gamma;
			}
		}
	}
	return {target_Lab: target_Lab,
			actual_Lab: actual_Lab,
			current_rgb: current_rgb,
			current_cmyk: current_cmyk,
			target_XYZ: target_XYZ,
			actual_XYZ: actual_XYZ};
};

function get_data(which) {
	var f=document.forms;
	
	if (which == "r" || !which) {
		data_ref=new dataset(f["F_data"].elements["FF_data_ref"].value)
	};
	if (which == "i" || !which) {
		data_in=new dataset(f["F_data"].elements["FF_data_in"].value)
	};
	
	if (which == "r" || !which) {
		if (!data_ref.data_format.length) return false;
		if (!data_ref.data.length) return false
	};
	if (which == "i" || !which) {
		if (!data_in.data_format.length) return false;
		if (!data_in.data.length) return false
	};
	
	return true
};

function compare(set_delta_calc_method) {
	form_elements_set_disabled(null, true);
	var fe = document.forms["F_out"].elements, fe2 = document.forms["F_data"].elements;
	if (fe2["FF_variables"]) try {
		eval(fe2["FF_variables"].value);
		window.comparison_criteria = comparison_criteria;
		if (debug) alert("Comparsion criteria: " + (comparison_criteria.toSource ? comparison_criteria.toSource() : comparison_criteria))
	}
	catch (e) {
		alert("Error parsing variable:\n" + e + "\nUsing default values.")
	};
	var report = data_in.generate_report(set_delta_calc_method),
		criteria = comparison_criteria[fe['FF_criteria'].value];
	document.getElementById('result').innerHTML = report;
	layout();
	document.getElementById('reporttitle').style.visibility = "visible";
	document.getElementById('report').style.visibility = "visible";
	form_elements_set_disabled(null, false);
	form_element_set_disabled(fe['FF_absolute'], !!criteria.lock_use_absolute_values);
	form_element_set_disabled(fe['FF_use_profile_wp_as_ref'], !fe['FF_absolute'].checked);
	if (document.getElementsByClassName) {
		var canvas = document.getElementsByClassName('canvas'),
			inner_coords, mouse_is_down, mouse_down_coords;
		document.addEventListener('mouseup', function (e) {
			for (var i = 0; i < canvas.length; i ++) {
				jsapi.dom.attributeRemoveWord(canvas[i], 'class', 'dragging');
			}
			mouse_is_down = false;
		});
		for (var i = 0; i < canvas.length; i ++) {
			var act = Array.prototype.slice.apply(canvas[i].getElementsByClassName('act')),
				ref = Array.prototype.slice.apply(canvas[i].getElementsByClassName('ref')),
				pts = act.concat(ref);
			for (var j = 0; j < pts.length; j ++) {
				pts[j].addEventListener('mouseenter', function (e) {
					var linked = this.parentNode.parentNode.getElementsByClassName('patch-' + jsapi.dom.attr(this, 'data-index'));
					jsapi.dom.attributeAddWord(this.parentNode.parentNode, 'class', 'hover');
					for (var k = 0; k < linked.length; k ++) {
						jsapi.dom.attributeAddWord(linked[k].parentNode, 'class', 'hover');
						if (jsapi.dom.attributeHasWord(linked[k], 'class', 'ref')) {
							linked[k].style.backgroundColor = jsapi.dom.attr(linked[k], 'data-bgcolor');
							linked[k].style.borderColor = jsapi.dom.attr(linked[k], 'data-bordercolor');
						}
					}
				});
				pts[j].addEventListener('mouseleave', function (e) {
					var linked = this.parentNode.parentNode.getElementsByClassName('patch-' + jsapi.dom.attr(this, 'data-index'));
					jsapi.dom.attributeRemoveWord(this.parentNode.parentNode, 'class', 'hover');
					for (var k = 0; k < linked.length; k ++) {
						jsapi.dom.attributeRemoveWord(linked[k].parentNode, 'class', 'hover');
						if (jsapi.dom.attributeHasWord(linked[k], 'class', 'ref')) {
							linked[k].style.backgroundColor = '';
							linked[k].style.borderColor = '';
						}
					}
				});
			}
			// Reset viewport
			canvas[i].addEventListener('dblclick', function () {
				var inner = this.getElementsByClassName('inner')[0];
				this.style.fontSize = '1px';
				inner.style.marginLeft = '';
				inner.style.marginTop = '';
			});
			// Click drag viewport
			canvas[i].addEventListener('mousedown', function (e) {
				var inner = this.getElementsByClassName('inner')[0];
				inner_coords = [parseFloat(inner.style.marginLeft) || 0, parseFloat(inner.style.marginTop) || 0];
				jsapi.dom.attributeAddWord(this, 'class', 'dragging');
				mouse_is_down = true;
				mouse_down_coords = [e.pageX, e.pageY];
				e.preventDefault();
			});
			canvas[i].addEventListener('mousemove', function (e) {
				if (mouse_is_down) {
					var fontSize = parseFloat(this.style.fontSize) || 1,
						inner = this.getElementsByClassName('inner')[0];
					inner.style.marginLeft = inner_coords[0] + (e.pageX - mouse_down_coords[0]) / fontSize + 'em';
					inner.style.marginTop = inner_coords[1] + (e.pageY - mouse_down_coords[1]) / fontSize + 'em';
				}
			});
			// Mousewheel zoom
			canvas[i].addEventListener('wheel', function (e) {
				var fontSize = parseFloat(this.style.fontSize) || 1;
				if ((e.deltaY < 0 && fontSize < 1000) || (e.deltaY > 0 && fontSize > 1)) {
					if (e.deltaY < 0) fontSize += fontSize / 4;
					else fontSize = Math.max(fontSize - fontSize / 4, 1);
					this.style.fontSize = fontSize + 'px';
					e.preventDefault();
				}
			});
		}
	}
	return true
};

function layout() {
	var padding = 0, borderwidth = 0, margin = 20,
		maxwidth = (document.getElementById("report").offsetWidth || 900) - padding * 2 - borderwidth * 2,
		tables = document.getElementsByTagName("table");
	for (var i = 0; i < tables.length; i ++) {
		if (tables[i].offsetWidth > maxwidth) {
			maxwidth = tables[i].offsetWidth;
			document.body.style.width = (maxwidth + padding * 2 + borderwidth * 2) + 'px';
		}
	}
	for (var i = 0; i < tables.length; i ++) tables[i].style.width = maxwidth + 'px';
}

function form_element_set_disabled(form_element, disabled) {
	if (!form_element || form_element.readOnly || form_element.type == "hidden" || form_element.type == "file" || jsapi.dom.attributeHasWord(form_element, "class", "fakefile") || jsapi.dom.attributeHasWord(form_element, "class", "save") || jsapi.dom.attributeHasWord(form_element, "class", "delete")) return;
	if (form_element.name == "FF_delta_calc_method") disabled = form_element.disabled;
	disabled = disabled ? "disabled" : "";
	form_element.disabled = disabled;
	if (disabled && !jsapi.dom.attributeHasWord(form_element, "class", "disabled")) jsapi.dom.attributeAddWord(form_element, "class", "disabled");
	else if (!disabled && jsapi.dom.attributeHasWord(form_element, "class", "disabled")) jsapi.dom.attributeRemoveWord(form_element, "class", "disabled");
	var labels = document.getElementsByTagName("label");
	for (var i=0; i<labels.length; i++) if (jsapi.dom.attribute(labels[i], "for") == form_element.id) {
		if (jsapi.dom.attribute(labels[i], "for") == "FF_gray_balance_cal_only") labels[i].style.display = document.getElementById(jsapi.dom.attribute(labels[i], "for")).style.display = window.CRITERIA_GRAYSCALE ? "inline" : "none";
		labels[i].className = disabled;
		labels[i].disabled = disabled;
	}
};

function form_elements_set_disabled(form, disabled) {
	disabled = disabled ? "disabled" : "";
	if (form) for (var j=0; j<form.elements.length; j++) form_element_set_disabled(form.elements[j], disabled);
	else {
		for (var i=0; i<document.forms.length; i++) {
			for (var j=0; j<document.forms[i].elements.length; j++) {
				if (document.forms[i].elements[j].name == "FF_gray_balance_cal_only") form_element_set_disabled(document.forms[i].elements[j], disabled || !window.CRITERIA_GRAYSCALE);
				else form_element_set_disabled(document.forms[i].elements[j], disabled);
			}
		}
	}
};

function toggle(e) {
	var target = document.getElementById(jsapi.dom.attr(e.parentNode, 'class').split(/\s+/)[0]);
	if (jsapi.dom.attributeHasWord(e.parentNode, 'class', 'collapsed')) {
		jsapi.dom.attributeRemoveWord(e.parentNode, 'class', 'collapsed');
		jsapi.dom.attributeRemoveWord(target, 'class', 'collapsed');
	}
	else {
		jsapi.dom.attributeAddWord(e.parentNode, 'class', 'collapsed');
		jsapi.dom.attributeAddWord(target, 'class', 'collapsed');
	}
};

function togglestats() {
	var verbosestats = document.forms['F_out'].elements['FF_verbosestats'].checked,
		summary = document.getElementById("summary"),
		trs = summary.getElementsByTagName("tr");
	for (var i = 0; i < trs.length; i ++) {
		if (jsapi.dom.attributeHasWord(trs[i], "class", "statonly")) (jsapi.dom.attributeHasWord(trs[i], "class", "verbose") ? jsapi.dom.attributeRemoveWord : jsapi.dom.attributeAddWord)(trs[i], "class", "verbose");
	}
	layout();
};

function set_status(str, append) {
	if (append) window.status += str;
	else window.status = str
};

function set_progress(str, cur_num, max_num) {
	var p = Math.ceil(100 / max_num * cur_num);
	set_status(str + p + "% " + "|".repeat(p / 2))
};

function basename(path) {
	return path.split(/[\/\\]/).pop()
};

function splitext(path) {
	var test = path.match(/(^.+)(\.\w+)$/);
	return test ? test.slice(1) : [path, null]
};

function strip_tags(str) {
	return str.replace(/<[^<]+>/g, '').replace(/CTCP/g, ' CtCp');
};

function plaintext(which) {
	var e = document.forms['F_data'].elements;
	if (which == 'ref') 
		var f = 'FF_data_ref';
	else
		var f = 'FF_data_in';
	var win = window.open();
	win.document.write('<pre>' + e[f].value);
	win.document.close();
};
