// Color Look Up Table Shader ==================================================

// Configuration ---------------------------------------------------------------

#define CLUT_ENABLED	1

// Key to toggle CLUT on or off. See MSDN, "Virtual-Key Codes",
// msdn.microsoft.com/library/windows/desktop/dd375731%28v=vs.85%29.aspx
// for a list of key codes.
#define CLUT_TOGGLEKEY	0x24	// 0x24 = HOME key

// NOTE that only textures with a height of 2 ^ n and a width of <height> ^ 2
// will work correctly! E.g. <width>x<height>: 256x16, 1024x32, 4096x64
#define CLUT_TEXTURE	"ColorLookupTable.png"
#define CLUT_TEXTURE_WIDTH	${WIDTH}
#define CLUT_SIZE	${HEIGHT}

// END Configuration -----------------------------------------------------------

#pragma message "\nColor Look Up Table Shader ${VERSION}\n"
#pragma reshade showtogglemessage

texture2D ColorLookupTable_texColor : COLOR;

texture ColorLookupTable_texCLUT < string source = CLUT_TEXTURE; >
{
	Width = CLUT_TEXTURE_WIDTH;
	Height = CLUT_SIZE;
	Format = ${FORMAT};
};

sampler2D ColorLookupTable_samplerColor
{
	Texture = ColorLookupTable_texColor;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

sampler2D ColorLookupTable_samplerCLUT
{
	Texture = ColorLookupTable_texCLUT;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

void ColorLookupTable_VS(in uint id : SV_VertexID,
						 out float4 position : SV_Position,
						 out float2 texcoord : TEXCOORD0)
{
	texcoord.x = (id == 2) ? 2.0 : 0.0;
	texcoord.y = (id == 1) ? 2.0 : 0.0;
	position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

#define CLUTscale float2(1.0 / CLUT_TEXTURE_WIDTH, 1.0 / CLUT_SIZE)

float4 ColorLookupTable_PS(in float4 position : SV_Position,
						   in float2 texcoord : TEXCOORD) : SV_Target
{
	float4 color = tex2D(ColorLookupTable_samplerColor, texcoord.xy);

	float3 CLUTcoord = float3((color.rg * (CLUT_SIZE - 1) + 0.5) * CLUTscale,
							  color.b * (CLUT_SIZE - 1));
	float shift = floor(CLUTcoord.z);
	CLUTcoord.x += shift * CLUTscale.y;
	color.rgb = lerp(tex2D(ColorLookupTable_samplerCLUT, CLUTcoord.xy).rgb,
					 tex2D(ColorLookupTable_samplerCLUT,
						   float2(CLUTcoord.x + CLUTscale.y, CLUTcoord.y)).rgb,
					 CLUTcoord.z - shift);

	return color;
}

technique ColorLookupTable < bool enabled = CLUT_ENABLED; toggle = CLUT_TOGGLEKEY; >
{
	pass
	{
		VertexShader = ColorLookupTable_VS;
		PixelShader = ColorLookupTable_PS;
	}
}
