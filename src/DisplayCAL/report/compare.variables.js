// !!!DO NOT CHANGE NEUTRAL ENTRIES!!!
var CRITERIA_RULES_NEUTRAL = [
		// description, [[R, G, B],...], DELTA_[E|L|C|H]_[MAX|MED|MAD|AVG|STDDEV], max, recommended, [CIE[76|94|00]|CMC11|CMC21], always display [true|false]
		["Measured vs. assumed target whitepoint ΔE*76", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE76],
		["Measured vs. assumed target whitepoint ΔE*94", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE94],
		["Measured vs. assumed target whitepoint ΔE*00", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, CIE00],
		["Measured vs. display profile whitepoint ΔE*76", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE76],
		["Measured vs. display profile whitepoint ΔE*94", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE94],
		["Measured vs. display profile whitepoint ΔE*00", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, CIE00],
		["Average ΔE*76", [], DELTA_E_AVG, null, null, CIE76],
		["Average ΔE*94", [], DELTA_E_AVG, null, null, CIE94],
		["Average ΔE*00", [], DELTA_E_AVG, null, null, CIE00],
		["Maximum ΔE*76", [], DELTA_E_MAX, null, null, CIE76],
		["Maximum ΔE*94", [], DELTA_E_MAX, null, null, CIE94],
		["Maximum ΔE*00", [], DELTA_E_MAX, null, null, CIE00],
		["Median ΔE*76", [], DELTA_E_MED, null, null, CIE76],
		["Median ΔE*94", [], DELTA_E_MED, null, null, CIE94],
		["Median ΔE*00", [], DELTA_E_MED, null, null, CIE00],
		["Median absolute deviation ΔE*76", [], DELTA_E_MAD, null, null, CIE76],
		["Median absolute deviation ΔE*94", [], DELTA_E_MAD, null, null, CIE94],
		["Median absolute deviation ΔE*00", [], DELTA_E_MAD, null, null, CIE00],
		["Standard deviation ΔE*76", [], DELTA_E_STDDEV, null, null, CIE76],
		["Standard deviation ΔE*94", [], DELTA_E_STDDEV, null, null, CIE94],
		["Standard deviation ΔE*00", [], DELTA_E_STDDEV, null, null, CIE00],
		["Calibration red tone values", ['CAL_REDLEVELS'], '', null, 95],
		["Calibration green tone values", ['CAL_GREENLEVELS'], '', null, 95],
		["Calibration blue tone values", ['CAL_BLUELEVELS'], '', null, 95],
		["Calibration grayscale tone values", ['CAL_GRAYLEVELS'], '', null, 95],
		["Measured vs. assumed target whitepoint ΔICtCp", ['WHITEPOINT_MvsA'], DELTA_E_MAX, null, null, ICTCP],
		["Measured vs. display profile whitepoint ΔICtCp", ['WHITEPOINT_MvsP'], DELTA_E_MAX, null, null, ICTCP],
		["Average ΔICtCp", [], DELTA_E_AVG, null, null, ICTCP],
		["Maximum ΔICtCp", [], DELTA_E_MAX, null, null, ICTCP],
		["Median ΔICtCp", [], DELTA_E_MED, null, null, ICTCP],
		["Median absolute deviation ΔICtCp", [], DELTA_E_MAD, null, null, ICTCP],
		["Standard deviation ΔICtCp", [], DELTA_E_STDDEV, null, null, ICTCP]
	],
	CRITERIA_RULES_DEFAULT = CRITERIA_RULES_NEUTRAL.clone();

CRITERIA_RULES_DEFAULT[0][3] = 2; // Measured vs. assumed whitepoint ΔE*76 nominal
CRITERIA_RULES_DEFAULT[0][4] = 1; // Measured vs. assumed whitepoint ΔE*76 recommended

CRITERIA_RULES_DEFAULT[1][3] = 2; // Measured vs. assumed whitepoint ΔE*94 nominal
CRITERIA_RULES_DEFAULT[1][4] = 1; // Measured vs. assumed whitepoint ΔE*94 recommended

CRITERIA_RULES_DEFAULT[2][3] = 2; // Measured vs. assumed whitepoint ΔE*00 nominal
CRITERIA_RULES_DEFAULT[2][4] = 1; // Measured vs. assumed whitepoint ΔE*00 recommended

//CRITERIA_RULES_DEFAULT[3][3] = 2; // Measured vs. profile whitepoint ΔE*76 nominal
CRITERIA_RULES_DEFAULT[3][4] = 1; // Measured vs. profile whitepoint ΔE*76 recommended

//CRITERIA_RULES_DEFAULT[4][3] = 2; // Measured vs. profile whitepoint ΔE*94 nominal
CRITERIA_RULES_DEFAULT[4][4] = 1; // Measured vs. profile whitepoint ΔE*94 recommended

//CRITERIA_RULES_DEFAULT[5][3] = 2; // Measured vs. profile whitepoint ΔE*00 nominal
CRITERIA_RULES_DEFAULT[5][4] = 1; // Measured vs. profile whitepoint ΔE*00 recommended

CRITERIA_RULES_DEFAULT[6][3] = 3; // Average ΔE*76 nominal
CRITERIA_RULES_DEFAULT[6][4] = 1.5; // Average ΔE*76 recommended

CRITERIA_RULES_DEFAULT[7][3] = 1.5; // Average ΔE*94 nominal
CRITERIA_RULES_DEFAULT[7][4] = 1; // Average ΔE*94 recommended

CRITERIA_RULES_DEFAULT[8][3] = 1.5; // Average ΔE*00 nominal
CRITERIA_RULES_DEFAULT[8][4] = 1; // Average ΔE*00 recommended

CRITERIA_RULES_DEFAULT[9][3] = 6; // Maximum ΔE*76 nominal
CRITERIA_RULES_DEFAULT[9][4] = 4; // Maximum ΔE*76 recommended

CRITERIA_RULES_DEFAULT[10][3] = 4; // Maximum ΔE*94 nominal
CRITERIA_RULES_DEFAULT[10][4] = 3; // Maximum ΔE*94 recommended

CRITERIA_RULES_DEFAULT[11][3] = 4; // Maximum ΔE*00 nominal
CRITERIA_RULES_DEFAULT[11][4] = 3; // Maximum ΔE*00 recommended

CRITERIA_RULES_DEFAULT[25][3] = 2; // Measured vs. assumed whitepoint ΔICtCp nominal
CRITERIA_RULES_DEFAULT[25][4] = 1; // Measured vs. assumed whitepoint ΔICtCp recommended

CRITERIA_RULES_DEFAULT[26][4] = 1; // Measured vs. profile whitepoint ΔICtCp recommended

CRITERIA_RULES_DEFAULT[27][3] = 1.5; // Average ΔICtCp nominal
CRITERIA_RULES_DEFAULT[27][4] = 1; // Average ΔICtCp recommended

CRITERIA_RULES_DEFAULT[28][3] = 5; // Maximum ΔICtCp nominal
CRITERIA_RULES_DEFAULT[28][4] = 3; // Maximum ΔICtCp recommended


var CRITERIA_RULES_RGB = CRITERIA_RULES_DEFAULT.clone().concat(
		[
			["Gamma maximum", [], GAMMA_MAX],
			["Gamma minimum", [], GAMMA_MIN],
			["Gamma range", [], GAMMA_RANGE],
			["Gamma average", [], GAMMA_AVG],
			["Gamma median", [], GAMMA_MED],
			["Gamma median absolute deviation", [], GAMMA_MAD],
			["Gamma standard deviation", [], GAMMA_STDDEV]
		]
	),
	CRITERIA_RULES_VERIFY = CRITERIA_RULES_RGB.clone().concat(
		[
			["RGB gray balance (>= 1% luminance) average absolute ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE76],
			["RGB gray balance (>= 1% luminance) combined Δa*76 and Δb*76 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE76],
			["RGB gray balance (>= 1% luminance) maximum ΔC*76", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE76],
			["RGB gray balance (>= 1% luminance) average absolute weighted ΔC*94", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE94],
			["RGB gray balance (>= 1% luminance) combined Δa*94 and Δb*94 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE94],
			["RGB gray balance (>= 1% luminance) maximum weighted ΔC*94", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE94],
			["RGB gray balance (>= 1% luminance) average absolute weighted ΔC'00", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, CIE00],
			["RGB gray balance (>= 1% luminance) combined Δa*00 and Δb*00 range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, CIE00],
			["RGB gray balance (>= 1% luminance) maximum weighted ΔC'00", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, CIE00],
			["RGB gray balance (>= 1% luminance) average absolute ΔC CtCp", window.CRITERIA_GRAYSCALE, DELTA_C_AVG, 1.0, 0.5, ICTCP],
			["RGB gray balance (>= 1% luminance) combined ΔCt and ΔCp range", window.CRITERIA_GRAYSCALE, DELTA_A_B_RANGE, 2.0, 1.5, ICTCP],
			["RGB gray balance (>= 1% luminance) maximum ΔC CtCp", window.CRITERIA_GRAYSCALE, DELTA_C_MAX, null, null, ICTCP]
		]
	),
	CRITERIA_RULES_CMYK = CRITERIA_RULES_DEFAULT.clone(),
	CRITERIA_DEFAULT = {
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		name: "Default",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: false,
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_DEFAULT
	},
	CRITERIA_RGB = CRITERIA_DEFAULT.clone(),
	CRITERIA_CMYK = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "CMYK",
		name: "CMYK",
		strip_name: "CMYK",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: false,
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK
	},
	CMYK_SOLID_PRIMARIES = [
		[100, 0, 0, 0],
		[0, 100, 0, 0],
		[0, 0, 100, 0],
		[0, 0, 0, 100]
	],
	CMY_SOLID_SECONDARIES = [
		[100, 100, 0, 0],  // C+M = Blue
		[0, 100, 100, 0],  // M+Y = Red
		[100, 0, 100, 0]   // C+Y = Green
	],
	CMYK_SOLIDS = CMYK_SOLID_PRIMARIES.concat(CMY_SOLID_SECONDARIES),
	IDEALLIANCE_2009_CMY_GRAY = [
		[3.1, 2.2, 2.2, 0],
		[10.2, 7.4, 7.4, 0],
		[25, 19, 19, 0],
		[50, 40, 40, 0],
		[75, 66, 66, 0]
	],
	CRITERIA_IDEALLIANCE_2009 = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "IDEALLIANCE_2009",
		name: "IDEAlliance Control Strip 2009",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: true,
		warn_deviation: 3,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_CMYK.clone().concat([
			// description, [[C, M, Y, K],...], DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Paper white ΔL*00", [[0, 0, 0, 0]], DELTA_L_MAX, 2, 1, CIE00],
			["Paper white Δa*00", [[0, 0, 0, 0]], DELTA_A_MAX, 1, .5, CIE00],
			["Paper white Δb*00", [[0, 0, 0, 0]], DELTA_B_MAX, 2, 1, CIE00],
			/* ["Average ΔE*00", [], DELTA_E_AVG, 2, 1, CIE00],
			["Maximum ΔE*00", [], DELTA_E_MAX, 6, 3, CIE00], */
			["CMYK solids maximum ΔE*00", CMYK_SOLIDS, DELTA_E_MAX, 7, 3, CIE00],
			["CMY 50% grey ΔE*00", [[50, 40, 40, 0]], DELTA_E_MAX, 1.5, 0.75, CIE00], 
			["CMY grey maximum ΔL*00", IDEALLIANCE_2009_CMY_GRAY, DELTA_L_MAX, 2, 1, CIE00], 
			["CMY grey maximum Δa*00", IDEALLIANCE_2009_CMY_GRAY, DELTA_A_MAX, 1, .5, CIE00], 
			["CMY grey maximum Δb*00", IDEALLIANCE_2009_CMY_GRAY, DELTA_B_MAX, 1, .5, CIE00], 
			["CMY grey maximum ΔE*00", IDEALLIANCE_2009_CMY_GRAY, DELTA_E_MAX, 2, 1, CIE00]
		])
	},
	ISO12647_7_CMY_GRAY = [
		[100, 85, 85, 0],
		[80, 65, 65, 0],
		[60, 45, 45, 0],
		[40, 27, 27, 0],
		[20, 12, 12, 0],
		[10, 6, 6, 0]
	],
	CRITERIA_ISO12647_7 = {  // ISO 12647-7:2016 switched to DE00 and delta Ch
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: true,
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_NEUTRAL.concat([
			// description, [[C, M, Y, K],...], DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			["Paper white ΔE*00", [[0, 0, 0, 0]], DELTA_E_MAX, 3, 1, CIE00],
			/* ["Average ΔE*", [], DELTA_E_AVG, 2.5, 1, CIE00],
			["Maximum ΔE*", [], DELTA_E_MAX, 5, 3, CIE00], */
			["CMYK solids maximum ΔE*00", CMYK_SOLIDS, DELTA_E_MAX, 3, 2, CIE00],
			["CMY maximum ΔH*ab", [
				[100, 0, 0, 0],
				[0, 100, 0, 0],
				[0, 0, 100, 0]
			], DELTA_H_MAX, 2.5, 2.0, CIE76, true],
			["CMY grey average ΔCh", ISO12647_7_CMY_GRAY, DELTA_CH_AVG, 2, 1.5, CIE00],
			["CMY grey maximum ΔCh", ISO12647_7_CMY_GRAY, DELTA_CH_MAX, 3.5, 2.5, CIE00]
		])
	},
	CRITERIA_FOGRA_MEDIAWEDGE_3 = CRITERIA_ISO12647_7.clone(),
	CRITERIA_IDEALLIANCE_2013 = {
		fields_match: ['CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "IDEALLIANCE_2013",
		name: "IDEAlliance ISO 12647-7 Control Wedge 2013",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: null,
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: true,
		warn_deviation: 5,
			// values with greater Delta E will be marked in the overview (informational, not a pass criteria)
		rules: CRITERIA_RULES_NEUTRAL.clone().concat([
			// description, [[C, M, Y, K],...], DELTA_[E|L|C|H]_[MAX|AVG], max, recommended, [CIE[76|94|00]|CMC11|CMC21]
			/* ["Average ΔE*00", [], DELTA_E_AVG, 2, 1, CIE00],
			["Maximum ΔE*00", [], DELTA_E_MAX, 6, 3, CIE00], */
			["CMYK primaries maximum ΔE*00", CMYK_SOLID_PRIMARIES.concat([
				[75, 0, 0, 0],
				[50, 0, 0, 0],
				[25, 0, 0, 0],
				[10, 0, 0, 0],
				[0, 75, 0, 0],
				[0, 50, 0, 0],
				[0, 25, 0, 0],
				[0, 10, 0, 0],
				[0, 0, 75, 0],
				[0, 0, 50, 0],
				[0, 0, 25, 0],
				[0, 0, 10, 0],
				[0, 0, 0, 90],
				[0, 0, 0, 75],
				[0, 0, 0, 50],
				[0, 0, 0, 25],
				[0, 0, 0, 10],
				[0, 0, 0, 3]
			]), DELTA_E_MAX, 5, null, CIE00],
			["CMY grey maximum ΔE*00", [
				[3, 2.24, 2.24, 0],
				[10, 7.46, 7.46, 0],
				[25, 18.88, 18.88, 0],
				[50, 40, 40, 0],
				[75, 66.12, 66.12, 0],
				[90, 85.34, 85.34, 0]
			], DELTA_E_MAX, 3, null, CIE00]
		])
	},
	CRITERIA_ISO14861_OUTER_GAMUT = CRITERIA_CMYK.clone(),
	comparison_criteria = { // values MUST pass these criteria
		RGB: CRITERIA_RGB
	};

CRITERIA_RGB.id = 'RGB';
CRITERIA_RGB.fields_match = ['RGB_R', 'RGB_G', 'RGB_B'];
CRITERIA_RGB.name = "RGB";
CRITERIA_RGB.strip_name = "RGB";
CRITERIA_RGB.rules = CRITERIA_RULES_RGB;

if (window.CRITERIA_GRAYSCALE) {
	comparison_criteria.RGB_GRAY = CRITERIA_RGB.clone();
	comparison_criteria.RGB_GRAY.delta_calc_method = CIE00;
	comparison_criteria.RGB_GRAY.id = 'RGB_GRAY';
	comparison_criteria.RGB_GRAY.name = "RGB + gray balance";
	comparison_criteria.RGB_GRAY.rules = CRITERIA_RULES_VERIFY;
};

var CRITERIA_ISO14861_COLOR_ACCURACY = CRITERIA_RGB.clone();
CRITERIA_ISO14861_COLOR_ACCURACY.id = 'ISO_14861_COLOR_ACCURACY_RGB318';
CRITERIA_ISO14861_COLOR_ACCURACY.name = "ISO 14861:2015 color accuracy";
CRITERIA_ISO14861_COLOR_ACCURACY.passrecommendedtext = null;
CRITERIA_ISO14861_COLOR_ACCURACY.lock_delta_calc_method = true;
for (var i = 0; i < CRITERIA_RULES_RGB.length; i ++) {
	// Reset tolerances
	CRITERIA_ISO14861_COLOR_ACCURACY.rules[i][3] = null; // nominal
	CRITERIA_ISO14861_COLOR_ACCURACY.rules[i][4] = null; // recommended
}
CRITERIA_ISO14861_COLOR_ACCURACY.rules[8][3] = 2.5; // Average ΔE*00 nominal
CRITERIA_ISO14861_COLOR_ACCURACY.rules.push(["99% percentile ΔE*00", [], DELTA_E_PERCENTILE_99, 4.5, null, CIE00]);

comparison_criteria['ISO_14861_COLOR_ACCURACY_RGB318'] = CRITERIA_ISO14861_COLOR_ACCURACY;

comparison_criteria['CMYK'] = CRITERIA_CMYK;
comparison_criteria['FOGRA_MW3'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
comparison_criteria['IDEALLIANCE_2009'] = CRITERIA_IDEALLIANCE_2009;
comparison_criteria['IDEALLIANCE_2013'] = CRITERIA_IDEALLIANCE_2013;
comparison_criteria['ISO14861_OUTER_GAMUT'] = CRITERIA_ISO14861_OUTER_GAMUT;

comparison_criteria['CMYK_FOGRA_MEDIAWEDGE_V3'] = CRITERIA_FOGRA_MEDIAWEDGE_3;

for (var i=27; i<=47; i++) {
	comparison_criteria['1x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['2x_MW2_FOGRA' + i + 'L_SB'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW2_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
	comparison_criteria['FOGRA' + i + '_MW3_SUBSET'] = CRITERIA_FOGRA_MEDIAWEDGE_3;
};

comparison_criteria['FOGRASTRIP3'] = CRITERIA_FOGRA_MEDIAWEDGE_3;

comparison_criteria['CMYK_IDEALLIANCE_CONTROLSTRIP_2009'] = CRITERIA_IDEALLIANCE_2009;
comparison_criteria['GRACOLCOATED1_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE_2009;
comparison_criteria['SWOPCOATED3_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE_2009;
comparison_criteria['SWOPCOATED5_ISO12647-7_CONTROLSTRIP2009_REF'] = CRITERIA_IDEALLIANCE_2009;

comparison_criteria['CMYK_IDEALLIANCE_ISO_12647-7_CONTROL_WEDGE_2013'] = CRITERIA_IDEALLIANCE_2013;

comparison_criteria['CMYK_ISO_12647-7_OUTER_GAMUT'] = CRITERIA_ISO14861_OUTER_GAMUT;

CRITERIA_ISO14861_OUTER_GAMUT.id = 'ISO14861_OUTER_GAMUT';
CRITERIA_ISO14861_OUTER_GAMUT.name = "ISO 14861:2015 outer gamut";
CRITERIA_ISO14861_OUTER_GAMUT.passrecommendedtext = null;
CRITERIA_ISO14861_OUTER_GAMUT.lock_delta_calc_method = true;
CRITERIA_ISO14861_OUTER_GAMUT.warn_deviation = 2.5;
for (var i = 0; i < CRITERIA_RULES_CMYK.length; i ++) {
	// Reset tolerances
	CRITERIA_ISO14861_OUTER_GAMUT.rules[i][3] = null; // nominal
	CRITERIA_ISO14861_OUTER_GAMUT.rules[i][4] = null; // recommended
}
CRITERIA_ISO14861_OUTER_GAMUT.rules[11][3] = 2.5; // Maximum ΔE*00 nominal
	
CRITERIA_FOGRA_MEDIAWEDGE_3.id = 'FOGRA_MW3';
CRITERIA_FOGRA_MEDIAWEDGE_3.name = "Fogra Media Wedge V3 (ISO 12647-7:2016)";
CRITERIA_FOGRA_MEDIAWEDGE_3.strip_name = "Ugra/Fogra Media Wedge CMYK V3.0";
CRITERIA_FOGRA_MEDIAWEDGE_3.rules[8][3] = 2.5; // Average ΔE*00 nominal
CRITERIA_FOGRA_MEDIAWEDGE_3.rules[11][3] = 5; // Maximum ΔE*00 nominal

CRITERIA_IDEALLIANCE_2009.rules[8][3] = 2; // Average ΔE*00 nominal
CRITERIA_IDEALLIANCE_2009.rules[11][3] = 6; // Maximum ΔE*00 nominal

CRITERIA_IDEALLIANCE_2013.rules[8][3] = 4; // Average ΔE*00 nominal
CRITERIA_IDEALLIANCE_2013.rules[11][3] = 6.5; // Maximum ΔE*00 nominal

comparison_criteria['RGB_HUE_CHROMA_ONLY'] = {
		fields_match: ['RGB_R', 'RGB_G', 'RGB_B'],
		fields_compare: ['LAB_L', 'LAB_A', 'LAB_B'],
		id: "RGB_HUE_CHROMA_ONLY",
		name: "Hue & chroma only",
		passtext: "Nominal tolerance passed",
		failtext: "Nominal tolerance exceeded",
		passrecommendedtext: "Recommended tolerance passed",
		failrecommendedtext: null,
		delta_calc_method: CIE00, // delta calculation method for overview
		lock_delta_calc_method: false,
		warn_deviation: null,
		rules: [
			["Measured vs. assumed target whitepoint ΔC*76", ['WHITEPOINT_MvsA'], DELTA_C_MAX, 2, 1, CIE76],
			["Measured vs. assumed target whitepoint weighted ΔC*94", ['WHITEPOINT_MvsA'], DELTA_C_MAX, 2, 1, CIE94],
			["Measured vs. assumed target whitepoint weighted ΔC'00", ['WHITEPOINT_MvsA'], DELTA_C_MAX, 2, 1, CIE00],
			["Measured vs. assumed target whitepoint ΔC CtCp", ['WHITEPOINT_MvsA'], DELTA_C_MAX, 2, 1, ICTCP],
			["Measured vs. assumed target whitepoint ΔH*76", ['WHITEPOINT_MvsA'], DELTA_H_MAX, 2, 1, CIE76],
			["Measured vs. assumed target whitepoint weighted ΔH*94", ['WHITEPOINT_MvsA'], DELTA_H_MAX, 2, 1, CIE94],
			["Measured vs. assumed target whitepoint weighted ΔH'00", ['WHITEPOINT_MvsA'], DELTA_H_MAX, 2, 1, CIE00],
			["Measured vs. assumed target whitepoint ΔH CtCp", ['WHITEPOINT_MvsA'], DELTA_H_MAX, 2, 1, ICTCP],
			["Measured vs. display profile whitepoint ΔC*76", ['WHITEPOINT_MvsP'], DELTA_C_MAX, null, 1, CIE76],
			["Measured vs. display profile whitepoint weighted ΔC*94", ['WHITEPOINT_MvsP'], DELTA_C_MAX, null, 1, CIE94],
			["Measured vs. display profile whitepoint weighted ΔC'00", ['WHITEPOINT_MvsP'], DELTA_C_MAX, null, 1, CIE00],
			["Measured vs. display profile whitepoint ΔC CtCp", ['WHITEPOINT_MvsP'], DELTA_C_MAX, null, 1, ICTCP],
			["Measured vs. display profile whitepoint ΔH*76", ['WHITEPOINT_MvsP'], DELTA_H_MAX, null, 1, CIE76],
			["Measured vs. display profile whitepoint weighted ΔH*94", ['WHITEPOINT_MvsP'], DELTA_H_MAX, null, 1, CIE94],
			["Measured vs. display profile whitepoint weighted ΔH'00", ['WHITEPOINT_MvsP'], DELTA_H_MAX, null, 1, CIE00],
			["Measured vs. display profile whitepoint ΔH CtCp", ['WHITEPOINT_MvsP'], DELTA_H_MAX, null, 1, ICTCP],
			["Average ΔC*76", [], DELTA_C_AVG, 3, 1.5, CIE76],
			["Average weighted ΔC*94", [], DELTA_C_AVG, 1.5, 1, CIE94],
			["Average weighted ΔC'00", [], DELTA_C_AVG, 1.5, 1, CIE00],
			["Average ΔC CtCp", [], DELTA_C_AVG, 1.5, 1, ICTCP],
			["Average ΔH*76", [], DELTA_H_AVG, 3, 1.5, CIE76],
			["Average weighted ΔH*94", [], DELTA_H_AVG, 1.5, 1, CIE94],
			["Average weighted ΔH'00", [], DELTA_H_AVG, 1.5, 1, CIE00],
			["Average ΔH CtCp", [], DELTA_H_AVG, 1.5, 1, ICTCP],
			["Maximum ΔC*76", [], DELTA_C_MAX, 6, 4, CIE76],
			["Maximum weighted ΔC*94", [], DELTA_C_MAX, 4, 3, CIE94],
			["Maximum weighted ΔC'00", [], DELTA_C_MAX, 4, 3, CIE00],
			["Maximum ΔC CtCp", [], DELTA_C_MAX, 5, 3, ICTCP],
			["Maximum ΔH*76", [], DELTA_H_MAX, 6, 4, CIE76],
			["Maximum weighted ΔH*94", [], DELTA_H_MAX, 4, 3, CIE94],
			["Maximum weighted ΔH'00", [], DELTA_H_MAX, 4, 3, CIE00],
			["Maximum ΔH CtCp", [], DELTA_H_MAX, 5, 3, ICTCP],
			["Median ΔC*76", [], DELTA_C_MED, null, null, CIE76],
			["Median weighted ΔC*94", [], DELTA_C_MED, null, null, CIE94],
			["Median weighted ΔC'00", [], DELTA_C_MED, null, null, CIE00],
			["Median ΔC CtCp", [], DELTA_C_MED, null, null, ICTCP],
			["Median ΔH*76", [], DELTA_H_MED, null, null, CIE76],
			["Median weighted ΔH*94", [], DELTA_H_MED, null, null, CIE94],
			["Median weighted ΔH'00", [], DELTA_H_MED, null, null, CIE00],
			["Median ΔH CtCp", [], DELTA_H_MED, null, null, ICTCP],
			["Median absolute deviation ΔC*76", [], DELTA_C_MAD, null, null, CIE76],
			["Median absolute deviation weighted ΔC*94", [], DELTA_C_MAD, null, null, CIE94],
			["Median absolute deviation weighted ΔC'00", [], DELTA_C_MAD, null, null, CIE00],
			["Median absolute deviation ΔC CtCp", [], DELTA_C_MAD, null, null, ICTCP],
			["Median absolute deviation ΔH*76", [], DELTA_H_MAD, null, null, CIE76],
			["Median absolute deviation weighted ΔH*94", [], DELTA_H_MAD, null, null, CIE94],
			["Median absolute deviation weighted ΔH'00", [], DELTA_H_MAD, null, null, CIE00],
			["Median absolute deviation ΔH CtCp", [], DELTA_H_MAD, null, null, ICTCP],
			["Standard deviation ΔC*76", [], DELTA_C_STDDEV, null, null, CIE76],
			["Standard deviation weighted ΔC*94", [], DELTA_C_STDDEV, null, null, CIE94],
			["Standard deviation weighted ΔC'00", [], DELTA_C_STDDEV, null, null, CIE00],
			["Standard deviation ΔC CtCp", [], DELTA_C_STDDEV, null, null, ICTCP],
			["Standard deviation ΔH*76", [], DELTA_H_STDDEV, null, null, CIE76],
			["Standard deviation weighted ΔH*94", [], DELTA_H_STDDEV, null, null, CIE94],
			["Standard deviation weighted ΔH'00", [], DELTA_H_STDDEV, null, null, CIE00],
			["Standard deviation ΔH CtCp", [], DELTA_H_STDDEV, null, null, ICTCP]
		]
	};
