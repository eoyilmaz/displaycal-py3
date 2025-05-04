/*!
	Slimbox v2.04 - The ultimate lightweight Lightbox clone for jQuery
	(c) 2007-2010 Christophe Beyls <http://www.digitalia.be>
	MIT-style license.
	Modified by Neil Storer <http://www.trips.elusien.co.uk> to add the
	following feature(s):
	1) the ability to resize the images in the slide show by using the
	   following two options on the "slimbox" function call:
	      slideHeight,
		  slideWidth.
	   both options can take either:
	      an integer the value of which denotes PIXELS
		  e.g. {slideWidth: 300, slideHeight: 200}
	      or a string specifying the PERCENTAGE size of the slide image
		  e.g. {slideWidth: "50%", slideHeight: "50%"}
	2) the ability to enable the user to specify a "slideInterval" option
	   that will show a PLAY/PAUSE button that the user can press to enable
	   the slides to be flipped automatically evry "slideInterval" seconds.
    Modified by Florian Hoech <http://hoech.net> to add the
	following feature(s):
	3) the ability to automatically reduce the size of the images in the slide 
	   show if they are larger than the given maxima by using the following 
	   two options on the "slimbox" function call:
		  maxHeight,
		  maxWidth.
	   both options can take either:
		  an integer the value of which denotes PIXELS
		  e.g. {maxWidth: 600, maxHeight: 400}
		  or a string specifying the PERCENTAGE size of the viewport
		  e.g. {maxWidth: "95%", maxHeight: "95%"}
       default is 95% of the viewport.
    4) Bugfix: If html has overflow:hidden and body has overflow:scroll,
       and the page is scrolled, the image position was not correct in IE < 9
    5) Automatically skip duplicates in galleries
*/

(function($) {

	// DOM elements
	var overlay, center, image, slide, sizer, prevLink, nextLink, playPauseLink, closeBtn, bottomContainer, bottom, caption, number;
	

	/*
		Initialization
	*/

	$(function() {
		// Append the Slimbox HTML code at the bottom of the document
		$("body").append(
			$([
				overlay = $('<div id="lbOverlay" />')[0],
				center = $('<div id="lbCenter" />')[0],
				bottomContainer = $('<div id="lbBottomContainer" />')[0]
			]).css("display", "none")
		);

		image = $('<div id="lbImage" />').appendTo(center).append(
			sizer = $('<div style="position: absolute;" />').append([
				slide    = $('<img id="lbSlide" alt="" />')[0]
			])[0]
		)[0];

		bottom = $('<div id="lbBottom" />').appendTo(bottomContainer).append([
			closeBtn = $('<a id="lbCloseLink" href="#">Close</a>')[0],
			caption = $('<div id="lbCaption" />')[0],
			number = $('<div id="lbNumber" />')[0],
			prevLink = $('<a id="lbPrevLink" href="#">Prev</a>')[0],
			nextLink = $('<a id="lbNextLink" href="#">Next</a>')[0],
			playPauseLink  = $('<div id="lbPlayPauseLink" class="lbPlay"  />').hide()[0],
			$('<div style="clear: both;" />')[0]
		])[0];
	});


	/*
		API
	*/

	// Open Slimbox with the specified parameters
	$.slimbox = function(_images, startImage, _options) {

		// Global variables, accessible to Slimbox only
		var win = $(window), options, images, activeImage = -1, activeURL, prevImage, nextImage, compatibleOverlay, middle, centerWidth, centerHeight,
			maxWidth, maxHeight, slideWidth, slideHeight, slideInterval,
			ie6 = !window.XMLHttpRequest, hiddenElements = [], documentElement = document.documentElement,

		// Preload images
		preload = {}, preloadPrev = new Image(), preloadNext = new Image();


		/*
			Internal functions
		*/

		function position() {
			var l = win.scrollLeft(), w = win.width();
			$([center, bottomContainer]).css("left", l + (w / 2));
			if (compatibleOverlay) $(overlay).css({left: l, top: win.scrollTop(), width: w, height: win.height()});
		};

		function setup(open) {
			if (open) {
				$("object").add(ie6 ? "select" : "embed").each(function(index, el) {
					hiddenElements[index] = [el, el.style.visibility];
					el.style.visibility = "hidden";
				});
			} else {
				$.each(hiddenElements, function(index, el) {
					el[0].style.visibility = el[1];
				});
				hiddenElements = [];
			}
			var fn = open ? "bind" : "unbind";
			win[fn]("scroll resize", position);
			$(document)[fn]("keydown", keyDown);
		};

		function keyDown(event) {
			var code = event.keyCode, fn = $.inArray;
			// Prevent default keyboard action (like navigating inside the page)
			return (fn(code, options.closeKeys) >= 0) ? close()
				: (fn(code, options.nextKeys) >= 0) ? next()
				: (fn(code, options.previousKeys) >= 0) ? previous()
				: false;
		};

		function previous() {
			return changeImage(prevImage);
		};

		function next() {
			if (nextImage < 0) return close();
			return changeImage(nextImage);
		};

		function changeImage(imageIndex) {
			if (imageIndex >= 0) {
				activeImage = imageIndex;
				activeURL = images[activeImage][0];
				prevImage = (activeImage || (options.loop ? images.length : 0)) - 1;
				nextImage = ((activeImage + 1) % images.length) || (options.loop ? 0 : -1);

				stop();
				center.className = "lbBeforeLoading";
				setTimeout(function () {
					// Only show the loading message if the image takes longer than one fourth of a second to load
					if (center.className == "lbBeforeLoading") center.className = "lbLoading";
				}, 250);

				preload = new Image();
				preload.onload = animateBox;
				preload.src = activeURL;
			}

			return false;
		};

		function animateBox() {
			center.className = "";
			
			slideWidth    = options.slideWidth || "100%";
			slideHeight   = options.slideHeight || "100%";

			var borderWidth = 10, captionHeight = 42;
			if (typeof maxWidth  == "string" && maxWidth.match(/%$/))
				maxWidth  = win.width()  * 0.01 * parseFloat(maxWidth) - borderWidth * 2;
			if (typeof maxHeight == "string" && maxHeight.match(/%$/))
				maxHeight = win.height() * 0.01 * parseFloat(maxHeight) - borderWidth * 2 - captionHeight;
			if (typeof slideWidth  == "string" && slideWidth.match(/%$/))
				slideWidth  = preload.width  * 0.01 * parseFloat(slideWidth);
			if (typeof slideHeight == "string" && slideHeight.match(/%$/))
				slideHeight = preload.height * 0.01 * parseFloat(slideHeight);
			if (slideWidth > maxWidth || slideHeight > maxHeight) {
				var factor = Math.min(maxWidth / slideWidth, maxHeight / slideHeight);
				slideWidth  *= factor;
				slideHeight *= factor;
			}

			$(slide).attr({src: activeURL});
			$(image).css({visibility: "hidden", display: ""});
			$([image, sizer, slide]).width(slideWidth);
			$([image, sizer, slide]).height(slideHeight);

			$(caption).html(images[activeImage][1] || "");
			$(number).html((images.length > 1 ? options.counterText : "").replace(/{x}/, activeImage + 1).replace(/{y}/, images.length));

			if (prevImage >= 0) preloadPrev.src = images[prevImage][0];
			if (nextImage >= 0) preloadNext.src = images[nextImage][0];

			centerWidth = image.offsetWidth;
			centerHeight = image.offsetHeight;
			var top = Math.max(0, middle - ((centerHeight + captionHeight) / 2));
			if (center.offsetHeight != centerHeight) {
				$(center).animate({height: centerHeight, top: top}, options.resizeDuration, options.resizeEasing);
			}
			if (center.offsetWidth != centerWidth) {
				$(center).animate({width: centerWidth, marginLeft: -centerWidth/2}, options.resizeDuration, options.resizeEasing);
			}
			$(center).queue(function() {
				$(bottomContainer).css({width: centerWidth, top: top + centerHeight, marginLeft: -centerWidth/2, display: ""});
				$(image).css({display: "none", visibility: "", opacity: ""}).fadeIn(options.imageFadeDuration, animateCaption);
			});
		};

		function animateCaption() {
			if (prevImage >= 0) $(prevLink).fadeIn(200);
			if (nextImage >= 0) $(nextLink).fadeIn(200);
			bottomContainer.style.visibility = "";
		};

		function stop() {
			preload.onload = null;
			preload.src = preloadPrev.src = preloadNext.src = activeURL;
			$([center, image, bottom]).stop(true);
			$(image).hide();
			if (prevImage < 0) $(prevLink).fadeOut(200);
			if (nextImage < 0) $(nextLink).fadeOut(200);
		};

		function close() {
			if (activeImage >= 0) {
				stop();
				activeImage = prevImage = nextImage = -1;
				$(center).hide();
				$(bottomContainer).fadeOut(200);
				$(overlay).stop().fadeOut(options.overlayFadeDuration, setup);
			}
			
			var $playPauseLink = $(playPauseLink);
			if ($playPauseLink.data('ppHandler') != -1) {
				clearInterval($playPauseLink.data('ppHandler'));
				$playPauseLink.data('ppHandler', -1);
				$playPauseLink.removeClass('lbPause').addClass('lbPlay');
			}

			return false;
		};

		$(overlay).unbind('click').click(close);
		$(image).unbind('click').click(next);
		$(closeBtn).unbind('click').click(close);
		$(prevLink).unbind('click').click(previous);
		$(nextLink).unbind('click').click(next);

		options = $.extend({
			filterDuplicates: false,	// Filter duplicates
			loop: false,				// Allows to navigate between first and last images
			overlayOpacity: 0.9,			// 1 is opaque, 0 is completely transparent (change the color in the CSS file)
			overlayFadeDuration: 400,		// Duration of the overlay fade-in and fade-out animations (in milliseconds)
			resizeDuration: 400,			// Duration of each of the box resize animations (in milliseconds)
			resizeEasing: "swing",			// "swing" is jQuery's default easing
			initialWidth: 250,			// Initial width of the box (in pixels)
			initialHeight: 250,			// Initial height of the box (in pixels)
			maxWidth: "95%",			// Max width  of the slide (in pixels or in percent of viewport width  as a string e.g. "95%")
			maxHeight: "95%",			// Max height of the slide (in pixels or in percent of viewport height as a string e.g. "95%")
			slideWidth: "100%",				// Initial width  of the slide (in pixels or in percent as a string e.g. "50%")
			slideHeight: "100%",				// Initial height of the slide (in pixels or in percent as a string e.g. "50%")
			slideInterval: 0,			// Interval between flipping slides (in seconds), 0 means no automation.
			imageFadeDuration: 400,		// Duration of the image fade-in animation (in milliseconds)
			captionAnimationDuration: 400,		// Duration of the caption animation (in milliseconds)
			counterText: "{x} / {y}",	// Translate or change as you wish, or set it to false to disable counter text for image groups
			closeKeys: [27, 88, 67],		// Array of keycodes to close Slimbox, default: Esc (27), 'x' (88), 'c' (67)
			previousKeys: [37, 80],			// Array of keycodes to navigate to the previous image, default: Left arrow (37), 'p' (80)
			nextKeys: [39, 78]			// Array of keycodes to navigate to the next image, default: Right arrow (39), 'n' (78)
		}, _options);

		// The function is called for a single image, with URL and Title as first two arguments
		if (typeof _images == "string") {
			_images = [[_images, startImage]];
			startImage = 0;
		}

		middle = (win.height() / 2);
		centerWidth = options.initialWidth;
		centerHeight = options.initialHeight;
		
		maxWidth    = options.maxWidth;
		maxHeight   = options.maxHeight;
		slideInterval = options.slideInterval;

		$(center).css({top: Math.max(0, middle - (centerHeight / 2)), width: centerWidth, height: centerHeight, marginLeft: -centerWidth/2}).show();
		compatibleOverlay = ie6 || (overlay.currentStyle && (overlay.currentStyle.position != "fixed"));
		if (compatibleOverlay) overlay.style.position = "absolute";
		$(overlay).css("opacity", options.overlayOpacity).fadeIn(options.overlayFadeDuration);
		position();
		setup(1);

		images = _images;
		options.loop = options.loop && (images.length > 1);
		
		if (slideInterval > 0) {
			if (typeof($(playPauseLink).data('ppHandler')) == 'undefined'){
				$(playPauseLink).click(function(){
					var $this = $(this);
					if ($this.hasClass('lbPlay')) {
						if ($this.data('ppHandler') != -1) clearInterval($this.data('ppHandler'));
						$this.data('ppHandler', setInterval(function(){next();}, slideInterval*1000));
						$this.removeClass('lbPlay').addClass('lbPause');
					} else {
						if ($this.data('ppHandler') != -1) clearInterval($this.data('ppHandler'));
						$this.data({ppHandler: -1});
						$this.removeClass('lbPause').addClass('lbPlay');
					}
				});
			}
			$(playPauseLink).addClass('lbPlay').data({ppHandler: -1}).show();
		}
		
		return changeImage(startImage);
	};

	/*
		options:	Optional options object, see jQuery.slimbox()
		linkMapper:	Optional function taking a link DOM element and an index as arguments and returning an array containing 2 elements:
				the image URL and the image caption (may contain HTML)
		linksFilter:	Optional function taking a link DOM element and an index as arguments and returning true if the element is part of
				the image collection that will be shown on click, false if not. "this" refers to the element that was clicked.
				This function must always return true when the DOM element argument is "this".
	*/
	$.fn.slimbox = function(_options, linkMapper, linksFilter) {
		linkMapper = linkMapper || function(el) {
			return [el.href, el.title];
		};

		linksFilter = linksFilter || function() {
			return true;
		};

		var links = this;
		options = $.extend({
			filterDuplicates: false,
			slideInterval: 0			// Interval between flipping slides (in seconds), 0 means no automation.
		}, _options);
		
		slideInterval = options.slideInterval;
		
		return links.unbind("click").click(function() {
			// Filter out duplicates
			var uris = {}, duplicatesFilter = function () {
				if (!uris[this.href]) uris[this.href] = 0;
				uris[this.href] ++;
				return uris[this.href] == 1;
			}, filteredLinks = options.filterDuplicates ? links.filter(duplicatesFilter) : links;
			
			// Build the list of images that will be displayed
			var link = this, startIndex = 0, i = 0, length;
			filteredLinks = $.grep(filteredLinks, function(el, i) {
				return linksFilter.call(link, el, i);
			});

			// We cannot use jQuery.map() because it flattens the returned array
			for (length = filteredLinks.length; i < length; ++i) {
				if (filteredLinks[i] == link) startIndex = i;
				filteredLinks[i] = linkMapper(filteredLinks[i], i);
			}

			return $.slimbox(filteredLinks, startIndex, _options);
		});
	};

})(jQuery);

function slimbox_init($, container) {
  $(container || 'body').find("a[data-lightbox^='lightbox'], a[href$='.gif'], a[href$='.jpg'], a[href$='.jpeg'], a[href$='.png']").filter(function () {
	return $(this).attr('slimbox') != 'slimbox';
  }).each(function () {
	  $(this).attr('slimbox', 'slimbox');
	  if (!this.title) {
		  var img = $(this).find('img');
		  if (img.length) {
			  this.title = img.attr('title') || img.attr('alt') || img.attr('src').split('/').pop();
			  img.attr('title', null);
		  }
		  else this.title = $(this).text();
	  }
  }).slimbox({filterDuplicates: true}, null, function(el) {
    return this == el || ($(this).data('lightbox').length > 8 && $(this).data('lightbox') == $(el).data('lightbox'));
  });
};

// AUTOLOAD CODE BLOCK (MAY BE CHANGED OR REMOVED)
if (!/ipod|series60|symbian|windows ce/i.test(navigator.userAgent)) {
  jQuery(function ($) {
	  slimbox_init($);
  });
};