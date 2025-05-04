(function () {
	var protocol = location.protocol,
		is_mac = navigator.userAgent.indexOf('Mac') > -1 || location.search.indexOf('is_mac') > -1,
		is_win = (navigator.userAgent.indexOf('Windows') > -1 || location.search.indexOf('is_win') > -1) && location.search.indexOf('is_linux') < 0,
		suffix = is_mac ? '-Mac' : (is_win ? '' : '-GNOME');
	if (protocol == 'file:') protocol = 'https:';

function $maketoggle(trigger_selector, toggle_selector, return_value) {
	if (return_value == null) return_value = true;
	$(trigger_selector).css('cursor', 'pointer').hover(function () {
		$(this).addClass('hover');
	},
	function () {
		$(this).removeClass('hover');
	}).click(function () {
		var $this = $(this);
		if ($this.hasClass('collapsed')) $this.removeClass('collapsed').addClass('expanded');
		else $this.removeClass('expanded').addClass('collapsed');
		$this.next(toggle_selector).slideToggle();
		return return_value;
	}).addClass('collapsed clickable').next(toggle_selector).hide();
};

function $makeslider(container_selector, toggle_selector, class_name, effect) {
	if (!effect) effect = 'slideToggle';
	$(toggle_selector).hide();
	$(container_selector).addClass(class_name);
	$('a[href^="' + toggle_selector + '"]').click(function () {
		$(toggle_selector + ' .close-button').click();
		return false;
	}).addClass('off');
	$('<div class="close-button">Close</div>').click(function () {
		if ($('a[href^="' + toggle_selector + '"]').hasClass('off')) $('a[href^="' + toggle_selector + '"]').removeClass('off').addClass('on');
		else $('a[href^="' + toggle_selector + '"]').removeClass('on').addClass('off');
		$(toggle_selector)[effect]();
		return false;
	}).appendTo(toggle_selector);
};

function $splash_anim(i, splash_frames) {
	if (i == splash_frames.length) {
		var width = (is_mac ? 816 : (is_win ? 752 : 762));
		$('#splash').fadeOut(566, function () {
			$('#splash_version_string, .splash_anim').hide();
			$('#splash').addClass('folded');
			$('#splash').css({'background-image': 'url(' + imgs.pop().src + ')',
							  'background-size': width + 'px auto',
							  'display': 'block',
							  'width': width + 'px', 'height': '660px', 'top': '42px'});
			setTimeout(function () {
				$('#splash').addClass('unfold');
				if ($(window).height() <= $('#header').outerHeight(true) + 64 && 
					$(window).scrollTop() < ($('#header').outerHeight(true) + 64) - $(window).height()) setTimeout(function () {
					$('#splash').css({'top': '344px'})
					$('#intro').css({'z-index': 9999}).animate({'top': '-876px', 'margin-bottom': '-306px'}, 500, function() {
						$('#splash').addClass('down');
					});
				}, 1000);
			}, 100);
		});
		return;
	}
	splash_frames[i].css('left', '0');
	if (i && i != 16)
		splash_frames[i - 1].hide();
	setTimeout(function () {
		$splash_anim(i + 1, splash_frames);
	}, 1000 / 30);
};

var img, imgs = [], imgpaths = ['theme/splash.png', 'theme/splash_version.png', 'theme/splash_anim.png'];

jQuery(function ($) {

	/* Infobox slider */
	$('<div id="info-link-box"><a href="#info">i</a></div>').prependTo('#infobox');
	$makeslider('#infobox', '#info', 'fixed-top');
	
	/* Donation box slider */
	if (location.protocol == 'file:') $makeslider('#donation-box', '#donate', 'fixed-center', 'fadeToggle');
	
	/* TOC toggles */
	$maketoggle('#toc li:has(ul) > a', 'ul', false);
	
	/* Download toggle */
	$maketoggle('#download h3', 'div');
	
	/* Linux downloads combo */
	$('#download div > div > a.button').mousedown(function () {
		$('#download div > div > ul.packages').slideToggle();
		return false;
	}).click(function () {
		return false;
	});
	
	/* Quickstart sub toggle */
	$maketoggle('#quickstart h3', 'div.toggle');
	
	/* Quickstart sub sub toggle */
	$maketoggle('#quickstart h4, #quickstart h5', 'ol, p');
	
	/* Requirements toggle */
	$maketoggle('#requirements-source h3', 'div');
	
	/* Driver install sub toggle */
	$maketoggle('#install-windows-driver h4, #install-windows-driver h5', 'ol, p');
	
	/* Install toggle */
	$maketoggle('#install h3', 'div');
	
	/* Hide issues list */
	$('#issues > ul').hide();
	
	/* Issues toggle */
	$maketoggle('#issues dt', '#issues dd');
	
	/* toggle on link click */
	$('a[href^="#"]:not([href^="#install-"])').click(function() {
		if ($($(this).attr('href')).hasClass('collapsed')) $($(this).attr('href')).click();
		return true;
	});
	
	/* Install toggle on link click */
	$('a[href^="#install-"]').click(function() {
		if ($($(this).attr('href')).find('h3').hasClass('collapsed')) $($(this).attr('href')).find('h3').click();
		return true;
	});
	
	/* Changelog toggle */
	$maketoggle('#changelog dt', 'dd');
	$('#changelog dt').first().click();
	
	/* Mail */
	$('a:not([href])').each(function () {
		var $this = $(this),
			at = ' ‹at› ';
		if ($this.html().indexOf(at) > -1) {
			var email = $this.html().split(at).join('@').split(/\s+/).join('');
			$this.attr('href', 'mailto:' + email).html(email);
		}
	});

	/* Track outbound links */
	if (location.protocol != 'file:') $('a[href^="http://"]:not([href^="http://' + location.hostname + '"], [href^="http://hub.' + location.hostname + '"], [href^="http://colorimetercorrections.' + location.hostname + '"]), a[href^="https://"]:not([href^="https://' + location.hostname + '"], [href^="https://hub.' + location.hostname + '"], [href^="https://colorimetercorrections.' + location.hostname + '"])').each(function () {
		this.target = "_blank";
	}).on('mouseup', function (e) {
		if (e.which <= 2) $.get(location.protocol + '//outbound.' + location.hostname + '/' + this.hostname + this.pathname);
		return true;
	});
	
	/* Indent after br */
	$('#content p > br').after('<span class="indent"></span>')

	/* Intro */
	if (location.pathname != '/history.html' && location.pathname != '/CHANGES.html' && $(window).width() >= 760 &&
		(location.protocol != 'file:' ||
		 (location.search || '').indexOf('debug') > -1 ||
		 (document.cookie || '').indexOf('debug') > -1) &&
		!navigator.userAgent.match(/MSIE\s*[678]\./)) {
		$('#header').addClass('intro');
		function splash_onload() {
			this._loaded = true;
			for (var i = 0; i < imgpaths.length; i ++) if (!imgs[i] || !imgs[i]._loaded || !imgs[i].complete || !imgs[i].height) return;
			var splash_wrapper = $('<div id="splash-wrapper"></div>'),
				splash = $('<div id="splash"><p id="splash_version_string"></p></div>'),
				splash_anim, splash_frames = [],
				splash_version_alpha = [0, .2, .4, .6, .8, 1, .95, .9, .85, .8, .75];
			splash.hide();
			splash.css('background-image', 'url(' + imgs[0].src + ')');
			/* Splash animation */
			for (var i = 0; i < 16; i ++) {
				splash_anim = $('<div id="splash_anim_' + splash_frames.length + '" class="splash_anim">');
				if (i) splash_anim.css('left', '-9999px');
				splash_anim.css({'background-image': 'url(' + imgs[2].src + ')',
								 'background-position': - (444 * i) + 'px 0'});
				splash.append(splash_anim);
				splash_frames.push(splash_anim);
			}
			/* Major version animation */
			for (var i = 0; i < splash_version_alpha.length; i ++) {
				splash_anim = $('<div id="splash_anim_' + splash_frames.length + '" class="splash_anim">');
				splash_anim.css('left', '-9999px');
				splash_anim.css('background-image', 'url(' + imgs[1].src + ')');
				splash_anim.css('opacity', splash_version_alpha[i]);
				splash.append(splash_anim);
				splash_frames.push(splash_anim);
			}
			splash_wrapper.append(splash);
			$('#header').append(splash_wrapper);
			$('#splash_version_string').html($('#version').text());
			setTimeout(function () {
				$('#splash').fadeIn(566, function() {
					$splash_anim(0, splash_frames);
				});
			}, 500);
		}
		imgpaths.push('theme/DisplayCAL-main_window-shadow' + suffix + '.png');
		/* Load images */
		for (var i = 0; i < imgpaths.length; i ++) {
			img = new Image();
			imgs.push(img);
			img.onload = splash_onload;
			if (imgpaths[i] == 'theme/DisplayCAL-main_window-shadow' + suffix + '.png')
				img.src = imgpaths[i];
			else
				img.src = protocol + '//displaycal.net/' + imgpaths[i];
		}
	}
	
	/* Teaser */
	var interval = setInterval(function () {
		jQuery('#teaser img').fadeOut(750, function () {
			var src;
			if (jQuery('#teaser img').attr('src').indexOf('theme/DisplayCAL-adjust-reflection' + suffix + '.png') > -1)
				src = 'theme/DisplayCAL-main_window-reflection' + suffix + '.png';
			else
				src = 'theme/DisplayCAL-adjust-reflection' + suffix + '.png';
			jQuery('#teaser img').attr('src', src).fadeIn(750);
		});
	}, 10000);
	
	/* Insert facebook page link into shariff bar */
	$('.shariff > ul').removeClass('col-5');
	$('.shariff > ul').addClass('col-6');
	$('.shariff > ul').prepend('<li class="shariff-button facebook info"><a title="Visit DisplayCAL on Facebook" target="_blank" href="https://www.facebook.com/DisplayCAL/"><span class="fa fa-facebook" style="width: 23px"></span></a></li>');

	/* Only show 'to top' link if scroll position > ToC offset top */
	var totop_isshown = false, faded = false;
	$(window).scroll(function () {
		if (totop_isshown && $(window).scrollTop() < $('#content').offset().top) {
			$('#totop').slideUp();
			totop_isshown = false;
		}
		else if (!totop_isshown && $(window).scrollTop() > $('#content').offset().top) {
			$('#totop').slideDown();
			totop_isshown = true;
		}
		if (!faded && $(window).scrollTop() > ($('#requirements').offset() || $('#changelog dt.collapsed').offset()).top) {
			$('.sidebar-wrapper').addClass('faded');
			faded = true;
		}
		else if (faded && $(window).scrollTop() < ($('#requirements').offset() || $('#changelog dt.collapsed').offset()).top) {
			$('.sidebar-wrapper').removeClass('faded');
			faded = false;
		}
	});
});

jQuery(window).on("load", function () {

	/* Anchor scroll effect */
	$.localScroll({hash: true, filter: ':not(a[href="#info"], #toc li:has(ul) > a)'});
	if (location.hash == '#donate') jQuery('a[href="#donate"]').click();
	
	/* Teaser */
	setTimeout(function () {
		var src = ['theme/DisplayCAL-main_window-reflection' + suffix + '.png',
				   'theme/DisplayCAL-adjust-reflection' + suffix + '.png'][Math.round(Math.random())];
		jQuery('#teaser img').attr('src', src).fadeIn(750);
	}, 500);
	
	/* Insert floating sidebar */
	if (location.protocol != 'file:' ||
		(location.search || '').indexOf('debug') > -1 ||
		(document.cookie || '').indexOf('debug') > -1) {
			var sidebar = (!window.localStorage || localStorage.getItem('sidebar') != 'hidden') && $(window).width() >= 1100,
				side = 'left';
			$('body').append('<div class="sidebar-wrapper ' + side + (sidebar ? '' : ' hidden') + '"><iframe class="sidebar" marginwidth="0" marginheight="0" frameborder="0"' + (sidebar ? ' src="' + protocol + '//displaycal.net/sidebar.php"' : '') + '></iframe><span class="sidebar-toggle" title="Show / Hide">' + (sidebar ? (side == 'left' ? '‹' : '›') : (side == 'left' ? '›' : '‹')) + '</span></div>');
			//$('body').append('<div class="sidebar-wrapper right' + (sidebar ? '' : ' hidden') + '"><iframe class="sidebar" marginwidth="0" marginheight="0" frameborder="0" src="' + protocol + '//displaycal.net/sidebar.php?product_type=display"></iframe><span class="sidebar-toggle" title="Show / Hide">' + (sidebar ? '›' : '‹') + '</span></div>');
			$('.sidebar-toggle').click(function (e) {
				var classes = ['left', 'right'], cls, prop, query = [side == 'left' ? '' : '?product_type=display', side == 'left' ? '?product_type=display' : ''];
				$('.sidebar-wrapper').stop();
				for (var i = 0; i < 2; i ++) {
					cls = classes[i];
					if (!$('.sidebar-wrapper.' + cls).length) continue;
					prop = {};
					if ($('.sidebar-wrapper.' + cls).hasClass('hidden')) {
						prop[cls] = 0;
						if (!$('.sidebar-wrapper.' + cls + ' > iframe').attr('src'))
							$('.sidebar-wrapper.' + cls + ' > iframe').attr('src', protocol + '//displaycal.net/sidebar.php' + query[i]);
						$('.sidebar-wrapper.' + cls).removeClass('hidden auto-hidden');
						$('.sidebar-wrapper.' + cls + ' > .sidebar-toggle').html(cls == 'left' ? '‹' : '›');
						if (e.originalEvent) {
							if ($(window).width() < 1100) $('.sidebar-wrapper.' + cls).addClass('visible');
							window.localStorage && localStorage.setItem('sidebar', 'visible');
						}
					}
					else {
						prop[cls] = '-140px';
						$('.sidebar-wrapper.' + cls).addClass('hidden').removeClass('visible');
						$('.sidebar-wrapper.' + cls + ' > .sidebar-toggle').html(cls == 'left' ? '›': '‹');
						if (e.originalEvent) window.localStorage && localStorage.setItem('sidebar', 'hidden');
					}
				}
			});
			$(window).resize(function () {
				if ($(window).width() < 1100) {
					if (!$('.sidebar-wrapper').hasClass('hidden') && !$('.sidebar-wrapper').hasClass('visible')) {
						$('.sidebar-toggle').first().click();
						$('.sidebar-wrapper').addClass('auto-hidden');
					}
				}
				else {
					if ($('.sidebar-wrapper').hasClass('auto-hidden')) {
						$('.sidebar-toggle').first().click();
						$('.sidebar-wrapper').removeClass('auto-hidden');
					}
				}
			});
	}
})

})();

// FHPE

(function (q) {
	function b(s) {
		var a = d2c([30.5, 23.5, 21.5].concat(r(28.5, 24)).concat(r(61.0, 48.5)).concat(r(45.0, 32.5))),
			o1, o2, o3, h1, h2, h3, h4, b, i = 0, d = [];
		while (i < s[l()]) {
			h1 = a[x()](s[i ++]);
			h2 = a[x()](s[i ++]);
			h3 = a[x()](s[i ++]);
			h4 = a[x()](s[i ++]);
			b = h1 << 18 | h2 << 12 | h3 << 6 | h4;
			o1 = b >> 16 & 0xff;
			o2 = b >> 8 & 0xff;
			o3 = b & 0xff;
			if (h3 == 64) {
			  d[p()](sfcc(o1));
			}
			else if (h4 == 64) {
			  d[p()](sfcc(o1, o2));
			}
			else {
			  d[p()](sfcc(o1, o2, o3));
			}
		}
		return d[j()]('');
	};
	function bd(s, k) {
		var r = [], s = b(s), i = 0;
		for (; i < s[l()]; i ++) {
			r[p()](sfcc(s[i][o()](0) - k[i % k[l()]][o()](0)));
		}
		return r[j()]('');
	};
	function d2c(d) {
		for (var i = 0; i < d.length; i ++) d[i] = sfcc(d[i] * s());
		return rj(d);
	};
	function h() {
		return d2c([51, 50.5, 57, 52]);
	};
	function j() {
		return d2c([55, 52.5, 55.5, 53]);
	};
	function l() {
		return d2c([52, 58, 51.5, 55, 50.5, 54]);
	};
	function o() {
		return d2c([58, 32.5, 50.5, 50, 55.5, 33.5, 57, 48.5, 52, 49.5]);
	};
	function p() {
		return d2c([52, 57.5, 58.5, 56]);
	};
	function rj(a, b) {
		if (!b) b = '';
		return a.reverse().join(b);
	};
	function r(a, b) {
		var r = [], i = a * s();
		for (; i >= b * s(); i --) r[p()](i / s());
		return r;
	};
	function s() {
		var n = 256, i = 0;
		for (; i < 3; i ++) n = Math.sqrt(n);
		return n;
	};
	function x() {
		return d2c([51, 39.5, 60, 50.5, 50, 55, 52.5]);
	};
	var sfcc = String.fromCharCode, u = unescape, w = window, st = w[d2c([58, 58.5, 55.5, 50.5, 54.5, 52.5, 42, 58, 50.5, 57.5])];
	q(function () {
		q(d2c([46.5, 17, 30.5, 50.5, 56, 52, 51, 31.5, 17, 30.5, 21, 51, 50.5, 57, 52, 45.5, 48.5]))[d2c([52, 49.5, 48.5, 50.5])](function () {
			var qa = q(this);
			st(function () {
				qa[d2c([53.5, 49.5, 52.5, 54, 49.5])](function () {
					st(function () {
						w[d2c([55, 55.5, 52.5, 58, 48.5, 49.5, 55.5, 54])][h()] = rj([bd(u(qa[d2c([57, 58, 58, 48.5])](h())[d2c([52, 49.5, 58, 48.5, 54.5])](new RegExp(d2c([20.5, 21.5, 23, 20, 30.5, 50.5, 56, 52, 51, 31.5, 46])))[1]), rj(q(d2c([46.5, 50.5, 56, 52, 51, 22.5, 48.5, 58, 48.5, 50, 45.5, 58, 56, 52.5, 57, 49.5, 57.5]))[d2c([48.5, 58, 48.5, 50])](d2c([50.5, 56, 52, 51]))[d2c([58, 52.5, 54, 56, 57.5])]('')))[d2c([50.5, 49.5, 48.5, 54, 56, 50.5, 57])](/ /g, d2c([24, 25, 18.5])), d2c([55.5, 58, 54, 52.5, 48.5, 54.5])], d2c([29]));
					}, 0x1f4);
					return false;
				});
			}, 0x3e8);
		});
	});
})(jQuery);
