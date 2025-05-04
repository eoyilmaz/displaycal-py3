var x3d_viewer = {
	rendermode: null,
	runtime: null,
	setOpacity: function(opacity) {
		var nodes = document.getElementById('x3d').getElementsByTagName('material');
		for (var i = 0; i < nodes.length; i ++) {
			_opacity = nodes[i].getAttribute('_opacity');
			if (_opacity == null) {
				transparency = nodes[i].getAttribute('transparency');
				if (transparency == null) transparency = 0;
				_opacity = 1 - transparency;
				nodes[i].setAttribute('_opacity', _opacity.toString());
			}
			nodes[i].setAttribute('transparency', (1 - parseFloat(_opacity) * opacity).toString());
		}
	},
	setRenderMode: function(mode, element) {
		if (mode != this.rendermode) {
			switch (this.rendermode) {
				case 'lines':
					this.runtime.togglePoints(true);
					break;
				case 'points':
					this.runtime.togglePoints();
					break;
			}
			this.rendermode = mode;
			switch (mode) {
				case 'lines':
					if (this.runtime.togglePoints(true) == 1)
						this.runtime.togglePoints(true);
					this.setOpacity(1);
					break;
				case 'points':
					this.runtime.togglePoints();
					this.setOpacity(1);
					break;
				default:
					this.setOpacity(mode);
			}
			element && this.setSelected(element);
		}
	},
	setSelected: function(element) {
		var siblings = element.parentNode.getElementsByTagName('div');
		element.parentNode.parentNode.getElementsByClassName('selected')[0].innerHTML = element.innerHTML;
		for (var i = 0; i < siblings.length; i ++) siblings[i].setAttribute('class', 'unchecked');
		element.setAttribute('class', 'checked');
	},
	setViewMode: function(mode, element) {
		this.runtime.getActiveBindable('NavigationInfo').setAttribute('explorationMode', mode);
		element && this.setSelected(element);
	},
	setViewpoint: function(viewpoint) {
		this.runtime.showAll(viewpoint);
	},
	setup: function() {
		if (window.x3dom) {
			var buttons = document.getElementsByClassName('button');
			for (var i = 0; i < buttons.length; i ++) {
				buttons[i].addEventListener('mousedown', function () {
					var cls = this.getAttribute('class');
					this.setAttribute('class', cls + ' mousedown');
				});
			}
			document.addEventListener('mouseup', function () {
				var elements = document.getElementsByClassName('mousedown'), cls;
				for (var i = 0; i < elements.length; i ++) {
					cls = elements[i].getAttribute('class').replace(/ mousedown$/, '');
					elements[i].setAttribute('class', cls);
				}
			});
			function fixMethod(cls, methodName, args, fix) {
				var method = cls[methodName].toString();
				method = method.replace(/^\(?\s*function\s*\([^)]*\)\s*{/, '');
				method = method.replace(/}\s*\)?$/, '');
				args.push(fix(method));
				cls[methodName] = Function.apply(Function, args);
			}
			// Fix lighting clamping
			fixMethod(x3dom.shader.DynamicShader.prototype, 'generateFragmentShader', ['gl', 'properties'], function (method) {
				for (var i = 0; i < 3; i ++) {
					method = method.replace(/(ambient|diffuse|specular)\s*=\s*clamp\(\1,\s*0.0,\s*1.0\)/, '$1 = max($1, 0.0)');
					method = method.replace(/clamp\((ambient\s*\+\sdiffuse),\s*0.0,\s*1.0\)/, 'max($1, 0.0)');
				}
				return method;
			});
			//
			var background = document.getElementsByTagName('background')[0];
			if (!background) {
				// Having a background element fixes transparency tone mapping
				background = document.createElement('background');
				document.getElementsByTagName('scene')[0].appendChild(background);
			}
			background.setAttribute('groundAngle', '1.5707963268');
			background.setAttribute('groundColor', '.08 .08 .08 .04 .04 .04');
			background.setAttribute('skyAngle', '1.5707963268');
			background.setAttribute('skyColor', '0 0 0 .04 .04 .04');
			// Fix fontsize clamping and text positioning
			fixMethod(x3dom.Texture.prototype, 'updateText', [], function (method) {
				// Fix fontsize clamping
				method = method.replace(/\s*if\s*\(font_size\s*>\s*\d+\.\d+\)\s*font_size\s*=\s*\d+\.\d+\s*;\n?/, '');
				// Fix text positioning
				method = method.replace(/this\.node\._mesh\._positions\[0\]\s*=\s*\[[^\]]+\]/,
										'this.node._mesh._positions[0] = [-w + w / 2, -h + h / 2, 0, w + w / 2, -h + h / 2, 0, w + w / 2, h + h / 2, 0, -w + w / 2, h + h / 2, 0]');
				return method;
			});
			//
			var environment = document.getElementsByTagName('environment')[0];
			if (!environment || !environment.hasAttribute('gammaCorrectionDefault')) {
				// Set gamma correction to none
				if (!environment) {
					environment = document.createElement('environment');
					document.getElementsByTagName('scene')[0].appendChild(environment);
				}
				environment.setAttribute('gammaCorrectionDefault', 'none');
			}
			//
			var navigationInfo = document.getElementsByTagName('navigationInfo')[0],
				indexedFaceSets = document.getElementsByTagName('indexedFaceSet');
			// Fix transparency problems with sort order
			for (var i = 0; i < indexedFaceSets.length; i ++) {
				if (indexedFaceSets[i].getAttribute('solid') == 'false')
					indexedFaceSets[i].setAttribute('solid', 'true');
				if (indexedFaceSets[i].getAttribute('ccw') != 'false')
					indexedFaceSets[i].setAttribute('ccw', 'false');
			}
			//
			x3dom.runtime.ready = function () {
				var lights = ['directional', 'point', 'spot'],
					x3d_viewer_toolbar = document.createElement('div'),
					toolbar_html = [
'			<div class="button">',
'				<div class="selected">Rotate</div>',
'				<div class="options">',
'					<div class="checked" onclick="x3d_viewer.setViewMode(\'all\', this)">Rotate</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewMode(\'pan\', this)">Pan</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewMode(\'zoom\', this)">Zoom</div>',
'				</div>',
'			</div><!--',
'			--><div class="button">',
'				<div class="selected">Default</div>',
'				<div class="options">',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(\'lines\', this)">Lines</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(\'points\', this)">Points</div>',
'					<div class="checked" onclick="x3d_viewer.setRenderMode(1, this)">Default</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.9, this)">Fade 10%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.8, this)">Fade 20%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.7, this)">Fade 30%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.6, this)">Fade 40%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.5, this)">Fade 50%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.4, this)">Fade 60%</div>',
'					<div class="unchecked" onclick="x3d_viewer.setRenderMode(.3, this)">Fade 70%</div>',
'				</div>',
'			</div><!--',
'			--><div class="button">',
'				<div class="selected">Lights</div>',
'				<div class="options">',
'					<div class="' + (navigationInfo && navigationInfo.getAttribute('headlight') == 'false' ? 'un' : '') + 'checked" onclick="x3d_viewer.toggleLights(\'headlight\', this)">Headlight</div>'
				];
				// Add light toggles for existing lights
				for (var i = 0; i < lights.length; i ++) {
					if (document.getElementById('x3d').getElementsByTagName(lights[i] + 'Light').length) {
						toolbar_html.push('					<div class="checked" onclick="x3d_viewer.toggleLights(\'' + lights[i] + 'Light\', this)">' + lights[i][0].toUpperCase() + lights[i].substr(1) + '</div>');
					}
				}
				//
				toolbar_html = toolbar_html.concat([
'				</div>',
'			</div><!--',
'			--><div class="button">',
'				<div class="selected">Viewpoint</div>',
'				<div class="options">',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'negZ\')">Top</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'posZ\')">Bottom</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'negY\')">Front</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'posY\')">Back</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'posX\')">Left</div>',
'					<div class="unchecked" onclick="x3d_viewer.setViewpoint(\'negX\')">Right</div>',
'				</div>',
'			</div><!--',
'			--><div class="button" onclick="x3d_viewer.runtime.fitAll()">Center &amp; fit</div><!--',
'			--><div class="button" onclick="x3d_viewer.runtime.resetView()">Reset</div><!--',
'			--><div class="button" onclick="window.open(x3d_viewer.runtime.getScreenshot())">Screenshot</div><!--',
'			--><div class="button" onclick="x3d_viewer.toggleLog()">Toggle log</div>'
				]);
				x3d_viewer_toolbar.setAttribute('id', 'x3d_viewer_toolbar');
				x3d_viewer_toolbar.innerHTML = toolbar_html.join('\n');
				document.body.appendChild(x3d_viewer_toolbar);
				x3d_viewer_toolbar.style.bottom = 0;
				window.x3d_viewer.runtime = document.getElementById('x3d').runtime;
				if (window.x3d_viewer.runtime.canvas.backend == 'flash' && !window.x3d_viewer.runtime.canvas.isFlashReady) window.x3d_viewer.toggleLog();
			}
		}
		else {
			var x3d_viewer_error = document.createElement('p');
			x3d_viewer_error.setAttribute('id', 'x3d_viewer_error');
			x3d_viewer_error.innerHTML = 'ERROR: X3DOM has failed loading. Please check the console for details.';
			document.body.appendChild(x3d_viewer_error);
			x3d_viewer_error.style.top = 0;
		}
	},
	toggleLights: function(which, control) {
		var lights, backup;
		if (which == 'headlight') {
			backup = this.runtime.getActiveBindable('NavigationInfo').getAttribute('headlight') == 'false';
			x3dom.debug.logInfo('Toggling ' + which + ' = ' + (backup ? 'true' : 'false'));
			this.runtime.getActiveBindable('NavigationInfo').setAttribute('headlight', backup ? 'true' : 'false');
		}
		else {
			lights = document.getElementById('x3d').getElementsByTagName(which);
			if (!lights.length) x3dom.debug.logError('Cannot toggle ' + which + ': There are no ' + which + ' nodes');
			for (var i = 0; i < lights.length; i ++) {
				backup = lights[i].getAttribute('_intensity');
				x3dom.debug.logInfo('Toggling ' + which + ' ' + i + ' intensity = ' + (backup ? backup : '0'));
				if (backup) {
					lights[i].setAttribute('intensity', lights[i].getAttribute('_intensity'));
					lights[i].removeAttribute('_intensity');
				}
				else {
					lights[i].setAttribute('_intensity', lights[i].getAttribute('intensity'));
					lights[i].setAttribute('intensity', '0');
				}
			}
		}
		control && control.setAttribute('class', backup ? 'checked' : 'unchecked');
	},
	toggleLog: function(show) {
		if (show == window.undefined) show = x3dom.debug.logContainer.style.bottom[0] != '0';
		x3dom.debug.logContainer.style.bottom = show !== false ? 0 : '-100%';
		if (this.runtime.canvas.backend == 'flash') this.runtime.canvas.canvas.setAttribute('wmode', show !== false ? 'opaque' : 'direct');
	}
};
