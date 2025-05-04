if (jsapi.useragent.opera && jsapi.useragent.opera < 7) alert("Your version of Opera is too old. Please upgrade to Opera 7 or newer.");
else if (jsapi.useragent.msie < 5) alert("Your version of Internet Explorer is too old. Please upgrade to MSIE 5 or newer.");
else {
var data_ref, data_in,
	fields_extract_indexes_i = [],
	fields_extract_indexes_r = [],
	fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
		
window.onload = function() {
	if ((jsapi.useragent.msie && !jsapi.useragent.mac) || (jsapi.useragent.opera && jsapi.useragent.opera < 7.52)) {
		labels = document.getElementsByTagName('label');
		for (var i = 0; i < labels.length; i ++) {
			var form_element = document.getElementById(jsapi.dom.attribute(labels[i], 'for'));
			form_element._onchange = form_element.onchange;
			form_element.onchange = null;
			if (jsapi.useragent.opera) labels[i].onclick = function () {
				var form_element = document.getElementById(jsapi.dom.attribute(this, 'for'));
				setTimeout(function () {
					form_element._onchange();
				}, 50);
			};
			else form_element.onclick = function () {
				var form_element = this;
				setTimeout(function () {
					form_element._onchange();
				}, 50);
			};
		};
	};
	if (WHITEPOINT_SIMULATION && !WHITEPOINT_SIMULATION_RELATIVE) document.forms['F_out'].elements['FF_absolute'].checked = true;
	analyze()
};
};
