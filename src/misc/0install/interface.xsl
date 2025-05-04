<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns="http://www.w3.org/1999/xhtml"
				xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
				xmlns:zi="http://zero-install.sourceforge.net/2004/injector/interface"
				version="1.0">
	<xsl:output method="xml" encoding="utf-8"
				doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
				doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"/>
	<xsl:template match="/zi:interface">
		<html>
			<head>
				<title>
					<xsl:value-of select="zi:name"/><xsl:if test="zi:summary and zi:summary != zi:name">—<xsl:value-of select="zi:summary"/></xsl:if>
				</title>
				<link rel="stylesheet" href="//fonts.googleapis.com/css?family=Lato%3A400%2C700%2C900%2C400italic%2C700italic&#038;subset=latin%2Clatin-ext" type="text/css" media="all" />
				<link rel="stylesheet" href="../theme/readme.css" />
				<link rel="stylesheet" href="interface1.css" />
			</head>
			<body>
				<h1>
					<xsl:variable name="icon-href" select="(zi:icon[@type='image/png'][1])/@href"/>
					<xsl:if test="$icon-href != ''">
						<span class="reflect"><img id="icon"
												   src="{$icon-href}"
												   alt="" /></span>
						<xsl:text> </xsl:text>
					</xsl:if>
					<xsl:choose>
						<xsl:when test="zi:homepage">
							<a href="{zi:homepage}">
								<xsl:value-of select="zi:name"/>
							</a>
						</xsl:when>
						<xsl:otherwise>
							<a href="http://{zi:name}.org/">
								<xsl:value-of select="zi:name"/>
							</a>
						</xsl:otherwise>
					</xsl:choose>
					<xsl:if test="zi:summary and zi:summary != zi:name">
						<span><span class="dash">—</span><xsl:value-of select="zi:summary"/></span>
					</xsl:if>
				</h1>
				<div id="info">
					<h2>
						This is a <strong><img src="0install-icon.png"
											   alt="" />
						Zero Install</strong> feed.
					</h2>
					<xsl:choose>
						<xsl:when test="zi:replaced-by">
							<p>
								This interface is obsolete! Please use this one
								instead:
							</p>
							<div id="box">
								<xsl:for-each select="zi:replaced-by">
									<p>
										<a class="button">
											<xsl:attribute name="href">
												<xsl:value-of select="@interface"/>
											</xsl:attribute>
											<xsl:value-of select="@interface"/>
										</a>
									</p>
								</xsl:for-each>
							</div>
						</xsl:when>
						<xsl:when test="//zi:implementation[@main] | //zi:group[@main] | //zi:command | //zi:package-implementation[@main] | //zi:entry-point">
							<xsl:choose>
								<xsl:when test="//zi:entry-point">
									<p>
										To add this program to your Applications menu,
										choose <strong>Zero Install (0install)</strong>
										from your <strong>Applications</strong> menu
										(“Start” menu under Windows), and <strong>drag
										this feed's URL into the window that
										opens.</strong>
									</p>
									<p>
										If you don't see this menu item, install the
										<code>zeroinstall-injector</code> package from
										your distribution's repository, or from
										<a href="http://0install.net/injector.html">0install.net</a>.
									</p>
									<div id="box">
										<p>
											<img src="0install.png" alt="" />
										</p>
										<p>
											<a class="button" href="{/zi:interface/@uri}">
												<xsl:value-of select="/zi:interface/@uri"/>
											</a>
										</p>
										<xsl:if test="zi:feed-for">
											<p>
												In most cases, you should use the
												interface URI instead of this feed's
												URI.
											</p>
											<xsl:for-each select="zi:feed-for">
												<p>
													<a class="button">
														<xsl:attribute name="href">
															<xsl:value-of select="@interface"/>
														</xsl:attribute>
														<xsl:value-of select="@interface"/>
													</a>
												</p>
											</xsl:for-each>
										</xsl:if>
									</div>
									<p>
										Alternatively, to run it from the command-line:
									</p>
								</xsl:when>
								<xsl:otherwise>
									<p>
										To run this program from the command-line:
									</p>
								</xsl:otherwise>
							</xsl:choose>

							<p>
								<code>
									0launch
									<xsl:choose>
										<xsl:when test="//zi:implementation[@main] | //zi:group[@main] | //zi:command[@name='run'] | //zi:package-implementation[@main]">
										</xsl:when>
										<xsl:otherwise>
											--command=COMMAND
										</xsl:otherwise>
									</xsl:choose>
									<xsl:value-of select="/zi:interface/@uri"/>
								</code>
							</p>
							<p>
								The <code>0alias</code> command can be used to
								create a short-cut to run it again later. If you
								don't have the <code>0launch</code> command,
								download it from
								<a href="http://0install.net/injector.html">0install.net</a>,
								which also contains documentation about how the
								Zero Install system works.
							</p>
						</xsl:when>
						<xsl:otherwise>
							<p>
								This software cannot be run as an application
								directly. It is a library for other programs to
								use.
							</p>
							<p>
								For more information about Zero Install, see
								<a href="http://0install.net">0install.net</a>.
							</p>
						</xsl:otherwise>
					</xsl:choose>
				</div>
				<div class="main" id="content">
					<xsl:apply-templates mode="dl" select="*|@*"/>
					<xsl:choose>
						<xsl:when test="zi:entry-point">
							<h2>Provides</h2>
							<xsl:for-each select="zi:entry-point">
								<div class="entry-point">
									<xsl:variable name="icon-href" select="(zi:icon[@type='image/png'][1])/@href"/>
									<xsl:if test="$icon-href != ''">
										<img src="{$icon-href}"
											 alt="" />
									</xsl:if>
									<div>
										<h3><xsl:value-of select="zi:name"/></h3>
										<p><xsl:value-of select="zi:description"/></p>
									</div>
								</div>
							</xsl:for-each>
						</xsl:when>
						<xsl:otherwise>
							<xsl:if test="//zi:command[@name!='run']">
								<h2>Provides</h2>
								<ul>
									<xsl:for-each select="//zi:command">
										<li>
											<xsl:value-of select="@name"/>
										</li>
									</xsl:for-each>
								</ul>
							</xsl:if>
						</xsl:otherwise>
					</xsl:choose>
					<h2>Required libraries</h2>
					<xsl:choose>
						<xsl:when test="//zi:requires|//zi:runner">
							<p>
								The list below is just for information; Zero
								Install will automatically download any required
								libraries for you.
							</p>
							<ul>
								<xsl:for-each select="//zi:requires|//zi:runner">
									<xsl:variable name="interface"
												  select="@interface"/>
									<xsl:if test="not(preceding::zi:requires[@interface = $interface]) and not(preceding::zi:runner[@interface = $interface])">
										<li>
											<a>
												<xsl:attribute name="href">
													<xsl:value-of select="$interface"/>
												</xsl:attribute>
												<xsl:value-of select="$interface"/>
											</a>
										</li>
									</xsl:if>
								</xsl:for-each>
							</ul>
						</xsl:when>
						<xsl:otherwise>
							<p>
								This feed does not list any additional
								requirements.
							</p>
						</xsl:otherwise>
					</xsl:choose>
					<xsl:if test="zi:feed">
						<h2>Other feeds for this interface</h2>
						<p>
							Zero Install will also check these feeds when
							deciding which version to use.
						</p>
						<ul>
							<xsl:for-each select="zi:feed">
								<li>
									<a>
										<xsl:attribute name="href">
											<xsl:value-of select="@src"/>
										</xsl:attribute>
										<xsl:value-of select="@src"/>
									</a>
								</li>
							</xsl:for-each>
						</ul>
					</xsl:if>
					<h2>Available versions</h2>
					<xsl:choose>
						<xsl:when test="//zi:implementation|//zi:package-implementation">
							<p>
								The list below is just for information; Zero
								Install will automatically download one of these
								versions for you.
							</p>
							<xsl:if test="//zi:implementation">
								<div id="friendlybox">
									<table id="get">
										<tr>
											<th>Version</th>
											<th>Released</th>
											<th>Stability</th>
											<th>Platform</th>
											<th>Archive</th>
										</tr>
										<xsl:for-each select="//zi:implementation">
											<xsl:variable name="stability"
														  select="(ancestor-or-self::*[@stability])[last()]/@stability"/>
											<tr>
												<xsl:if test="$stability = 'buggy' or $stability = 'insecure'">
													<xsl:attribute name="style">
														opacity: .5
													</xsl:attribute>
												</xsl:if>
												<td>
													<h2>
														<xsl:if test="$stability = 'buggy' or $stability = 'insecure'">
															<xsl:attribute name="style">
																text-decoration: line-through
															</xsl:attribute>
														</xsl:if>
														<xsl:value-of select="(ancestor-or-self::*[@version])[last()]/@version"/>
														<xsl:if test="(ancestor-or-self::*[@version])[last()]/@version-modifier">
															<xsl:value-of select="(ancestor-or-self::*[@version])[last()]/@version-modifier"/>
														</xsl:if>
														<xsl:if test="$stability = 'testing' or $stability = 'developer' or contains(.//zi:archive/@href, 'snapshot')">
															Beta
														</xsl:if>
													</h2>
													<xsl:if test="@langs">
														(<xsl:value-of select="@langs"/>)
													</xsl:if>
												</td>
												<td>
													<xsl:value-of select="(ancestor-or-self::*[@released])[last()]/@released"/>
												</td>
												<td>
													<xsl:value-of select="(ancestor-or-self::*[@stability])[last()]/@stability"/>
												</td>
												<td>
													<xsl:variable name="arch"
																  select="(ancestor-or-self::*[@arch])[last()]/@arch"/>
													<xsl:choose>
														<xsl:when test="$arch = '*-src'">
															Source code
														</xsl:when>
														<xsl:when test="not($arch) or $arch = '*-*'">
															Any
														</xsl:when>
														<xsl:otherwise>
															<xsl:value-of select="$arch"/>
														</xsl:otherwise>
													</xsl:choose>
												</td>
												<td class="download">
													<xsl:apply-templates select=".//zi:archive | .//zi:file" />
												</td>
											</tr>
										</xsl:for-each>
									</table>
								</div>
							</xsl:if>
							<xsl:if test="//zi:package-implementation">
								<p>
									Non-Zero Install packages
									provided by distributions can
									provide this interface:
								</p>
								<table id="packages">
									<tr>
										<th>Distribution</th>
										<th>Package name</th>
									</tr>
									<xsl:for-each select="//zi:package-implementation">
										<tr>
											<td>
												<xsl:value-of select="(ancestor-or-self::*[@distributions])[last()]/@distributions"/>
											</td>
											<td>
												<xsl:value-of select="(ancestor-or-self::*[@package])[last()]/@package"/>
											</td>
										</tr>
									</xsl:for-each>
								</table>
							</xsl:if>
						</xsl:when>
						<xsl:otherwise>
							<p>
								No versions are available for downlad.
							</p>
						</xsl:otherwise>
					</xsl:choose>
				</div>
			</body>
		</html>
	</xsl:template>
	<!--xsl:template mode="dl" match="/zi:interface/@uri">
		<dt>Full URL</dt>
		<dd>
			<p>
				<a href="{.}">
					<xsl:value-of select="."/>
				</a>
			</p>
		</dd>
	</xsl:template-->
	<!--xsl:template mode="dl" match="zi:homepage">
		<dt>Homepage</dt>
		<dd>
			<p>
				<a href="{.}">
					<xsl:value-of select="."/>
				</a>
			</p>
		</dd>
	</xsl:template-->
	<xsl:template mode="dl" match="zi:description">
		<h2>Description</h2>
		<div class="description">
			<xsl:call-template name="description">
				<xsl:with-param name="text"><xsl:value-of select="."/></xsl:with-param>
			</xsl:call-template>
		</div>
	</xsl:template>
	<xsl:template name="description">
		<xsl:param name="text"/>
		<xsl:if test="normalize-space($text)">
			<xsl:variable name="first" select="substring-before($text, '&#xa;&#xa;')"/>
			<xsl:choose>
				<xsl:when test="normalize-space($first)">
					<p><xsl:value-of select="$first"/></p>
					<xsl:call-template name="description">
						<xsl:with-param name="text"><xsl:value-of select="substring-after($text, '&#xa;&#xa;')"/></xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<p><xsl:value-of select="$text"/></p>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:if>
	</xsl:template>
	<!--xsl:template mode="dl" match="zi:icon">
		<dt>Icon</dt>
		<dd>
			<p>
				<img src="{@href}" class="alpha"/>
			</p>
		</dd>
	</xsl:template-->
	<xsl:template mode="dl" match="*|@*"/>
	<xsl:template match="zi:group">
		<dl class="group">
			<xsl:apply-templates mode="attribs"
								 select="@stability|@version|@id|@arch|@released"/>
			<xsl:apply-templates select="zi:group|zi:requires|zi:runner|zi:implementation"/>
		</dl>
	</xsl:template>
	<xsl:template match="zi:requires | zi:runner">
		<dt>Requires</dt>
		<dd>
			<a href="{@interface}">
				<xsl:value-of select="@interface"/>
			</a>
		</dd>
	</xsl:template>
	<xsl:template match="zi:implementation">
		<dl class="impl">
			<xsl:apply-templates mode="attribs"
								 select="@stability|@version|@id|@arch|@released"/>
			<xsl:apply-templates/>
		</dl>
	</xsl:template>
	<xsl:template mode="attribs" match="@*">
		<dt>
			<xsl:value-of select="name(.)"/>
		</dt>
		<dd>
			<xsl:value-of select="."/>
		</dd>
	</xsl:template>
	<xsl:template match="zi:archive | zi:file">
		<xsl:variable name="stability"
					  select="(ancestor-or-self::*[@stability])[last()]/@stability"/>
		<span>
			<xsl:if test="$stability = 'buggy' or $stability = 'insecure'">
				<xsl:attribute name="style">
					visibility: hidden
				</xsl:attribute>
			</xsl:if>
			<a href="{@href}">Download</a>
			(<xsl:value-of select="format-number(@size div 1024 div 1024, '####0.00')"/> MiB)
		</span>
	</xsl:template>
</xsl:stylesheet>
