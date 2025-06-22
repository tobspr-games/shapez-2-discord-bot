import pygamePIL
import math
import typing

# hack for ease of copying this file into other projects
try:
    import globalInfos
    INITIAL_SHAPE_SIZE = globalInfos.INITIAL_SHAPE_SIZE
    SHAPE_NOTHING_CHAR = globalInfos.SHAPE_NOTHING_CHAR
    SHAPE_LAYER_SEPARATOR = globalInfos.SHAPE_LAYER_SEPARATOR
    SHAPE_CONFIG_QUAD = globalInfos.SHAPE_CONFIG_QUAD
    SHAPE_CONFIG_HEX = globalInfos.SHAPE_CONFIG_HEX
except ModuleNotFoundError:
    INITIAL_SHAPE_SIZE = 500
    SHAPE_NOTHING_CHAR = "-"
    SHAPE_LAYER_SEPARATOR = ":"
    SHAPE_CONFIG_QUAD = "quad"
    SHAPE_CONFIG_HEX = "hex"

SHAPE_BORDER_COLOR = (35,25,35)
BG_CIRCLE_COLOR = (31,41,61,25)
SHADOW_COLOR = (50,50,50,127)
EMPTY_COLOR = (0,0,0,0)
PIN_COLOR = (71,69,75)
COLORBLIND_PATTERN_COLOR = (0,0,0)

BASE_COLORS:dict[str,tuple[int,int,int]] = {
    "u" : (164,158,165),
    "r" : (255,0,0),
    "g" : (0,255,0),
    "b" : (0,0,255),
    "c" : (0,255,255),
    "m" : (255,0,255),
    "y" : (255,255,0),
    "w" : (255,255,255),
    "k" : (86,77,78),
    "p" : (167,41,207),
    "o" : (213,133,13)
}

INTERNAL_COLOR_SKINS = ["RGB","RYB","CMYK"]
INTERNAL_COLOR_SKINS_ANNOTATION = typing.Literal["RGB","RYB","CMYK"]
EXTERNAL_COLOR_SKINS = ["RGB","RYB","CMYK","RGB-cb"]
EXTERNAL_COLOR_SKINS_ANNOTATION = typing.Literal["RGB","RYB","CMYK","RGB-cb"]

INTERNAL_COLOR_SKINS_COLORS:dict[INTERNAL_COLOR_SKINS_ANNOTATION,dict[str,tuple[int,int,int]]] = {
    "RGB" : {
        "u" : BASE_COLORS["u"],
        "r" : BASE_COLORS["r"],
        "g" : BASE_COLORS["g"],
        "b" : BASE_COLORS["b"],
        "c" : BASE_COLORS["c"],
        "m" : BASE_COLORS["m"],
        "y" : BASE_COLORS["y"],
        "w" : BASE_COLORS["w"]
    },
    "RYB" : {
        "u" : BASE_COLORS["u"],
        "r" : BASE_COLORS["r"],
        "g" : BASE_COLORS["y"],
        "b" : BASE_COLORS["b"],
        "c" : BASE_COLORS["g"],
        "m" : BASE_COLORS["p"],
        "y" : BASE_COLORS["o"],
        "w" : BASE_COLORS["k"]
    },
    "CMYK" : {
        "u" : BASE_COLORS["u"],
        "r" : BASE_COLORS["c"],
        "g" : BASE_COLORS["m"],
        "b" : BASE_COLORS["y"],
        "c" : BASE_COLORS["r"],
        "m" : BASE_COLORS["g"],
        "y" : BASE_COLORS["b"],
        "w" : BASE_COLORS["k"]
    }
}

# according to 'dnSpy > ShapeMeshGenerator > GenerateShapeMesh()', this value should be 0.85
# according to ingame screenshots, it should be 0.77
# according to me, the closest to ingame is 0.8
# but, to me, the best for this context is 0.75
LAYER_SIZE_REDUCTION = 0.75

# below are sizes in pixels taken from a screenshot of the ingame shape viewer
DEFAULT_IMAGE_SIZE = 602
DEFAULT_BG_CIRCLE_DIAMETER = 520
DEFAULT_SHAPE_DIAMETER = 407
DEFAULT_BORDER_SIZE = 15

FAKE_SURFACE_SIZE = INITIAL_SHAPE_SIZE
SIZE_CHANGE_RATIO = FAKE_SURFACE_SIZE / DEFAULT_IMAGE_SIZE
SHAPE_SIZE = DEFAULT_SHAPE_DIAMETER * SIZE_CHANGE_RATIO
SHAPE_BORDER_SIZE = round(DEFAULT_BORDER_SIZE*SIZE_CHANGE_RATIO)
BG_CIRCLE_DIAMETER = DEFAULT_BG_CIRCLE_DIAMETER * SIZE_CHANGE_RATIO

COLORBLIND_NUM_PATTERNS = 13
COLORBLIND_PATTERN_SPACING = (FAKE_SURFACE_SIZE) / (COLORBLIND_NUM_PATTERNS-1)
COLORBLIND_PATTERN_WIDTH = COLORBLIND_PATTERN_SPACING * 0.25

SQRT_2 = math.sqrt(2)
SQRT_3 = math.sqrt(3)
SQRT_6 = math.sqrt(6)

def _preRenderColorblindPatterns() -> None:

    global _colorblindPatterns
    surfaceSize = FAKE_SURFACE_SIZE
    redSurface = pygamePIL.Surface((surfaceSize,surfaceSize),pygamePIL.SRCALPHA)
    greenSurface = redSurface.copy()
    blueSurface = redSurface.copy()

    for i in range(COLORBLIND_NUM_PATTERNS):
        pygamePIL.draw_line(
            redSurface,
            COLORBLIND_PATTERN_COLOR,
            (i*COLORBLIND_PATTERN_SPACING,0),
            (i*COLORBLIND_PATTERN_SPACING,surfaceSize),
            round(COLORBLIND_PATTERN_WIDTH)
        )

    for x in range(COLORBLIND_NUM_PATTERNS-1):
        for y in range(COLORBLIND_NUM_PATTERNS):
            pygamePIL.draw_rect(
                greenSurface,
                COLORBLIND_PATTERN_COLOR,
                pygamePIL.Rect(
                    (x*COLORBLIND_PATTERN_SPACING) + (COLORBLIND_PATTERN_SPACING/2) - (COLORBLIND_PATTERN_WIDTH/2),
                    (y*COLORBLIND_PATTERN_SPACING) - (COLORBLIND_PATTERN_WIDTH/2),
                    COLORBLIND_PATTERN_WIDTH,
                    COLORBLIND_PATTERN_WIDTH
                )
            )

    for i in range((COLORBLIND_NUM_PATTERNS*2)-1):
        pygamePIL.draw_line(
            blueSurface,
            COLORBLIND_PATTERN_COLOR,
            ((i-COLORBLIND_NUM_PATTERNS+1)*COLORBLIND_PATTERN_SPACING,0),
            (i*COLORBLIND_PATTERN_SPACING,surfaceSize),
            round(COLORBLIND_PATTERN_WIDTH)
        )

    _colorblindPatterns = {
        "r" : redSurface,
        "g" : greenSurface,
        "b" : blueSurface
    }


_colorblindPatterns:dict[str,pygamePIL.Surface]
_preRenderColorblindPatterns()

def _getScaledShapeSize(shapeSize:float,layerIndex:int) -> float:
    return shapeSize * (LAYER_SIZE_REDUCTION**layerIndex)

def _drawShapePart(
    partShape:str,
    partColor:str,
    shapeSize:float,
    partIndex:int,
    layerIndex:int,
    layers:list[list[str]],
    colorSkin:INTERNAL_COLOR_SKINS_ANNOTATION,
    shapeConfig:str
    ) -> tuple[pygamePIL.Surface|None,pygamePIL.Surface|None]:
    # returns part with shadow, border

    borderSize = SHAPE_BORDER_SIZE
    halfBorderSize = borderSize / 2
    curShapeSize = _getScaledShapeSize(shapeSize,layerIndex)
    curPartSize = curShapeSize / 2

    withBorderPartSize = round(curPartSize+borderSize)
    partSurface = pygamePIL.Surface(
        (withBorderPartSize,withBorderPartSize),
        pygamePIL.SRCALPHA
    )
    partSurfaceForBorder = partSurface.copy()

    drawShadow = layerIndex != 0
    color = INTERNAL_COLOR_SKINS_COLORS[colorSkin].get(partColor)
    borderColor = SHAPE_BORDER_COLOR

    if partShape == SHAPE_NOTHING_CHAR:
        return None, None

    if partShape == "C":

        pygamePIL.draw_circle(partSurface,color, # main circle
            (halfBorderSize,withBorderPartSize-halfBorderSize),
            curPartSize,
            draw_top_right=True
        )

        pygamePIL.draw_circle(partSurfaceForBorder,borderColor, # circle border
            (halfBorderSize,withBorderPartSize-halfBorderSize),
            curPartSize+halfBorderSize,
            borderSize,
            draw_top_right=True
        )
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # left border
            (halfBorderSize,0),
            (halfBorderSize,withBorderPartSize),
            borderSize
        )
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # down border
            (0,withBorderPartSize-halfBorderSize),
            (withBorderPartSize,withBorderPartSize-halfBorderSize),
            borderSize
        )

        return partSurface, partSurfaceForBorder

    if partShape == "R":

        pygamePIL.draw_rect(partSurface,color, # main rect
            pygamePIL.Rect(halfBorderSize,halfBorderSize,curPartSize,curPartSize)
        )

        pygamePIL.draw_rect(partSurfaceForBorder,borderColor, # rect border
            pygamePIL.Rect(0,0,withBorderPartSize,withBorderPartSize),
            borderSize
        )

        return partSurface, partSurfaceForBorder

    if partShape == "S":

        points = [(curPartSize,0),(curPartSize/2,curPartSize),(0,curPartSize),(0,curPartSize/2)]
        points = [(halfBorderSize+x,halfBorderSize+y) for x,y in points]

        pygamePIL.draw_polygon(partSurface,color,points) # main polygon

        pygamePIL.draw_polygon(partSurfaceForBorder,borderColor,points,borderSize) # border polygon
        for point in points:
            pygamePIL.draw_circle(partSurfaceForBorder,borderColor,point,halfBorderSize-1) # fill in the missing vertices

        return partSurface, partSurfaceForBorder

    if partShape == "W":

        arcCenter = (halfBorderSize+(curPartSize*1.4),halfBorderSize+(curPartSize*-0.4))
        arcRadius = curPartSize * 1.18
        sideLength = curPartSize / 3.75

        pygamePIL.draw_rect(partSurface,color, # first fill in the whole part
            pygamePIL.Rect(halfBorderSize,halfBorderSize,curPartSize,curPartSize)
        )
        pygamePIL.draw_circle(partSurface,EMPTY_COLOR,arcCenter,arcRadius) # then carve out a circle

        pygamePIL.draw_circle(partSurfaceForBorder,borderColor,arcCenter,arcRadius+halfBorderSize,borderSize) # arc border
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # left border
            (halfBorderSize,0),
            (halfBorderSize,withBorderPartSize),
            borderSize
        )
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # down border
            (0,withBorderPartSize-halfBorderSize),
            (withBorderPartSize,withBorderPartSize-halfBorderSize),
            borderSize
        )
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # top edge border
            (halfBorderSize,halfBorderSize),
            (halfBorderSize+sideLength,halfBorderSize),
            borderSize
        )
        pygamePIL.draw_line(partSurfaceForBorder,borderColor, # right edge border
            (withBorderPartSize-halfBorderSize,withBorderPartSize-halfBorderSize-sideLength),
            (withBorderPartSize-halfBorderSize,withBorderPartSize-halfBorderSize),
            borderSize
        )

        return partSurface, partSurfaceForBorder

    if partShape == "H":

        points = [(0,0),((SQRT_3/2)*curPartSize,curPartSize/2),(0,curPartSize)]
        points = [(halfBorderSize+x,halfBorderSize+y) for x,y in points]

        pygamePIL.draw_polygon(partSurface,color,points) # main polygon

        pygamePIL.draw_polygon(partSurfaceForBorder,borderColor,points,borderSize) # border polygon
        for point in points:
            pygamePIL.draw_circle(partSurfaceForBorder,borderColor,point,halfBorderSize-1) # fill in the missing vertices

        return partSurface, partSurfaceForBorder

    if partShape == "F":

        semicircleRadius = ((3-SQRT_3)/4) * curPartSize
        triangleSideLength = 2 * semicircleRadius
        semicircleCenterX = (triangleSideLength*(SQRT_3/2)) / 2
        semicircleCenterY = (
            curPartSize
            - triangleSideLength
            + math.sqrt((semicircleRadius*semicircleRadius)-(semicircleCenterX*semicircleCenterX))
        )
        trianglePoints = [
            (0,curPartSize-triangleSideLength),
            ((SQRT_3/2)*triangleSideLength,curPartSize-semicircleRadius),
            (0,curPartSize)
        ]
        semicircleStartAngle = math.radians(360-30)
        semicircleStopAngle = math.radians(360-30-180)

        semicircleCenterX += halfBorderSize
        semicircleCenterY += halfBorderSize
        trianglePoints = [(halfBorderSize+x,halfBorderSize+y) for x,y in trianglePoints]

        pygamePIL.draw_polygon(partSurface,color,trianglePoints) # triangle part

        pygamePIL.draw_arc(partSurface,color,pygamePIL.Rect( # semicircle part
            semicircleCenterX-semicircleRadius,semicircleCenterY-semicircleRadius,triangleSideLength,triangleSideLength
        ),semicircleStartAngle,semicircleStopAngle,math.ceil(semicircleRadius))

        pygamePIL.draw_line(partSurfaceForBorder,borderColor,trianglePoints[0],trianglePoints[2],borderSize) # left border

        pygamePIL.draw_line(partSurfaceForBorder,borderColor,trianglePoints[1],trianglePoints[2],borderSize) # bottom border

        pygamePIL.draw_arc(partSurfaceForBorder,borderColor,pygamePIL.Rect( # semicircle border
            semicircleCenterX - semicircleRadius - halfBorderSize,
            semicircleCenterY - semicircleRadius - halfBorderSize,
            triangleSideLength + borderSize,
            triangleSideLength + borderSize
        ),semicircleStartAngle,semicircleStopAngle,borderSize)

        for point in trianglePoints:
            pygamePIL.draw_circle(partSurfaceForBorder,borderColor,point,halfBorderSize-1) # fill in the missing vertices

        return partSurface, partSurfaceForBorder

    if partShape == "G":

        points = [(0,0),((SQRT_3/6)*curPartSize,curPartSize/2),((SQRT_3/2)*curPartSize,curPartSize/2),(0,curPartSize)]
        points = [(halfBorderSize+x,halfBorderSize+y) for x,y in points]

        pygamePIL.draw_polygon(partSurface,color,points) # main polygon

        pygamePIL.draw_polygon(partSurfaceForBorder,borderColor,points,borderSize) # border polygon
        for point in points:
            pygamePIL.draw_circle(partSurfaceForBorder,borderColor,point,halfBorderSize-1) # fill in the missing vertices

        return partSurface, partSurfaceForBorder

    if partShape == "P":

        if shapeConfig == SHAPE_CONFIG_QUAD:
            pinCenter = (halfBorderSize+(curPartSize/3),halfBorderSize+(2*(curPartSize/3)))
        elif shapeConfig == SHAPE_CONFIG_HEX:
            pinCenter = (halfBorderSize+((SQRT_2/6)*curPartSize),halfBorderSize+((1-(SQRT_6/6))*curPartSize))
        pinRadius = curPartSize/6

        if drawShadow:
            pygamePIL.draw_circle(partSurface,SHADOW_COLOR,pinCenter,pinRadius+halfBorderSize) # shadow

        pygamePIL.draw_circle(partSurface,PIN_COLOR,pinCenter,pinRadius) # main circle

        return partSurface, None

    if partShape == "c":

        darkenedColor = tuple(round(c/2) for c in color)

        if shapeConfig == SHAPE_CONFIG_QUAD:

            darkenedAreasOffset = 0 if layerIndex%2 == 0 else 22.5
            startAngle1 = math.radians(67.5-darkenedAreasOffset)
            stopAngle1 = math.radians(90-darkenedAreasOffset)
            startAngle2 = math.radians(22.5-darkenedAreasOffset)
            stopAngle2 = math.radians(45-darkenedAreasOffset)
            darkenedAreasRect = pygamePIL.Rect(
                halfBorderSize - curPartSize,
                halfBorderSize,
                2 * curPartSize,
                2 * curPartSize
            )

            if drawShadow:
                pygamePIL.draw_circle(partSurface,SHADOW_COLOR, # shadow
                    (halfBorderSize,withBorderPartSize-halfBorderSize),
                    curPartSize+halfBorderSize,
                    borderSize,
                    draw_top_right=True
                )

            pygamePIL.draw_circle(partSurface,color, # main circle
                (halfBorderSize,withBorderPartSize-halfBorderSize),
                curPartSize,
                draw_top_right=True
            )
            pygamePIL.draw_arc(partSurface,darkenedColor, # 1st darkened area
                darkenedAreasRect,
                startAngle1,
                stopAngle1,
                math.ceil(curPartSize)
            )
            pygamePIL.draw_arc(partSurface,darkenedColor, # 2nd darkened area
                darkenedAreasRect,
                startAngle2,
                stopAngle2,
                math.ceil(curPartSize)
            )

            return partSurface, None

        elif shapeConfig == SHAPE_CONFIG_HEX:

            points = [(0,0),((SQRT_3/2)*curPartSize,curPartSize/2),(0,curPartSize)]
            points = [(halfBorderSize+x,halfBorderSize+y) for x,y in points]

            shadowPoints = [
                (points[0][0],points[0][1]-halfBorderSize),
                (points[1][0]+((SQRT_3/2)*halfBorderSize),points[1][1]-(halfBorderSize/2)),
                (points[2][0],points[2][1])
            ]

            sideMiddlePoint = ((points[0][0]+points[1][0])/2,(points[0][1]+points[1][1])/2)
            if layerIndex%2 == 0:
                darkenedArea = [points[0],sideMiddlePoint,points[2]]
            else:
                darkenedArea = [sideMiddlePoint,points[1],points[2]]

            if drawShadow:
                pygamePIL.draw_polygon(partSurface,SHADOW_COLOR,shadowPoints) # shadow

            pygamePIL.draw_polygon(partSurface,color,points) # main polygon

            pygamePIL.draw_polygon(partSurface,darkenedColor,darkenedArea) # darkened area

            return partSurface, None

    raise ValueError(f"Unknown shape type : {partShape}")

def _drawColorblindPatterns(layerSurface:pygamePIL.Surface,color:str) -> None:

    curMask = pygamePIL.mask_from_surface(layerSurface,200)

    for colors,pattern in zip(
        (["r","m","y","w"],["g","y","c","w"],["b","c","m","w"]),
        _colorblindPatterns.values()
    ):
        if color not in colors:
            continue

        curPattern = pygamePIL.Surface(layerSurface.get_size(),pygamePIL.SRCALPHA)
        _blitCentered(pattern,curPattern)

        curPatternMasked = pygamePIL.Surface(curPattern.get_size(),pygamePIL.SRCALPHA)
        curMask.to_surface(curPatternMasked,curPattern,unsetcolor=None)

        layerSurface.blit(curPatternMasked,(0,0))

def _blitCentered(blitFrom:pygamePIL.Surface,blitTo:pygamePIL.Surface) -> None:
    blitTo.blit(
        blitFrom,
        (
            (blitTo.get_width()/2) - (blitFrom.get_width()/2),
            (blitTo.get_height()/2) - (blitFrom.get_height()/2)
        )
    )

def _rotateSurf(toRotate:pygamePIL.Surface,numParts:int,partIndex:int,layerIndex:int,shapeSize:float) -> pygamePIL.Surface:
    curShapeSize = _getScaledShapeSize(shapeSize,layerIndex)
    tempSurf = pygamePIL.Surface(
        (curShapeSize+SHAPE_BORDER_SIZE,)*2,
        pygamePIL.SRCALPHA
    )
    tempSurf.blit(toRotate,(curShapeSize/2,0))
    tempSurf = pygamePIL.transform_rotate(tempSurf,-((360/numParts)*partIndex))
    return tempSurf

def _externalToInternalColorSkin(external:EXTERNAL_COLOR_SKINS_ANNOTATION) -> tuple[INTERNAL_COLOR_SKINS_ANNOTATION,bool]:
    return external.removesuffix("-cb"), external.endswith("-cb")

def getShapeColor(colorCode:str,colorSkin:EXTERNAL_COLOR_SKINS_ANNOTATION) -> tuple[int,int,int]:
    return INTERNAL_COLOR_SKINS_COLORS[_externalToInternalColorSkin(colorSkin)[0]][colorCode]

def renderShape(
    shapeCode:str,
    surfaceSize:int,
    colorSkin:EXTERNAL_COLOR_SKINS_ANNOTATION=EXTERNAL_COLOR_SKINS[0],
    shapeConfig:str=SHAPE_CONFIG_QUAD
) -> pygamePIL.Surface:

    decomposedShapeCode = shapeCode.split(SHAPE_LAYER_SEPARATOR)
    numParts = int(len(decomposedShapeCode[0])/2)
    decomposedShapeCode = [[layer[i*2:(i*2)+2] for i in range(numParts)] for layer in decomposedShapeCode]

    curInternalColorSkin, colorblindPatterns = _externalToInternalColorSkin(colorSkin)

    returnSurface = pygamePIL.Surface((FAKE_SURFACE_SIZE,FAKE_SURFACE_SIZE),pygamePIL.SRCALPHA)
    pygamePIL.draw_circle(returnSurface,BG_CIRCLE_COLOR,(FAKE_SURFACE_SIZE/2,FAKE_SURFACE_SIZE/2),BG_CIRCLE_DIAMETER/2)

    for layerIndex, layer in enumerate(decomposedShapeCode):

        partBorders = []

        for partIndex, part in enumerate(layer):

            partSurface, partBorder = _drawShapePart(
                part[0],
                part[1],
                SHAPE_SIZE,
                partIndex,
                layerIndex,
                decomposedShapeCode,
                curInternalColorSkin,
                shapeConfig
            )
            partBorders.append(partBorder)

            if partSurface is None:
                continue

            rotatedLayer = _rotateSurf(partSurface,numParts,partIndex,layerIndex,SHAPE_SIZE)
            if colorblindPatterns:
                _drawColorblindPatterns(rotatedLayer,part[1])
            _blitCentered(rotatedLayer,returnSurface)

        for partIndex, border in enumerate(partBorders):

            if border is None:
                continue

            _blitCentered(_rotateSurf(border,numParts,partIndex,layerIndex,SHAPE_SIZE),returnSurface)

    # pygame doesn't work well at low resolution so render at size 500 then downscale to the desired size
    return pygamePIL.transform_smoothscale(returnSurface,(surfaceSize,surfaceSize))