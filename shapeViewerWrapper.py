import shapeCodeGenerator
import globalInfos
import utils

import shapez2
from shapez2 import gameObjects
import io
import typing
import math

SHAPE_CODE_OPENING = "{"
SHAPE_CODE_CLOSING = "}"
SHAPE_ROW_SEP = "[sep]"
DISPLAY_PARAM_PREFIX = "/"
DISPLAY_PARAM_EXIT_CHAR = " "
DISPLAY_PARAM_KEY_VALUE_SEPARATOR = ":"

def getPotentialDisplayParamsFromMessage(message:str) -> list[tuple]:

    if DISPLAY_PARAM_PREFIX not in message:
        return []

    prefixSplits = message.split(DISPLAY_PARAM_PREFIX)[1:]
    potentialDisplayParams = []

    for split in prefixSplits:

        if DISPLAY_PARAM_EXIT_CHAR in split:
            potentialDisplayParam = split.split(DISPLAY_PARAM_EXIT_CHAR)[0]
        else:
            potentialDisplayParam = split

        if DISPLAY_PARAM_KEY_VALUE_SEPARATOR in potentialDisplayParam:
            potentialDisplayParams.append(tuple(potentialDisplayParam.split(DISPLAY_PARAM_KEY_VALUE_SEPARATOR)[:2]))
        else:
            potentialDisplayParams.append((potentialDisplayParam,))

    return potentialDisplayParams

class DisplayParam:

    def __init__(
        self,
        type:typing.Literal["bool","int","str"],
        default,
        *,
        intRangeStart:int|None=None,
        intRangeStop:int|None=None,
        strAllowedValues:list[str]|None=None,
        strCaseMatters:bool|None=None
    ) -> None:
        self.type = type
        self.default = default
        if type == "int":
            self.intRangeStart:int = intRangeStart
            self.intRangeStop:int = intRangeStop
        elif type == "str":
            self.strAllowedValues:list[str] = strAllowedValues
            self.strCaseMatters:bool = strCaseMatters

    def getValidValue(self,inputValue:tuple[str]|tuple[str,str]) -> bool|int|str|None:
        if self.type == "bool":
            return True
        if len(inputValue) < 2:
            return None
        if self.type == "int":
            if len(inputValue[1]) > len(str(self.intRangeStop)):
                return None
            try:
                inputValueInt = int(inputValue[1])
            except ValueError:
                return None
            return min(self.intRangeStop,max(self.intRangeStart,inputValueInt))
        inputValueStr = inputValue[1]
        strAllowedValues = self.strAllowedValues
        if not self.strCaseMatters:
            inputValueStr = inputValueStr.lower()
            strAllowedValues = [v.lower() for v in strAllowedValues]
        if inputValueStr not in strAllowedValues:
            return None
        return inputValueStr

DISPLAY_PARAMS:dict[str,DisplayParam] = {
    "spoiler" : DisplayParam("bool",False),
    "size" : DisplayParam(
        "int",
        globalInfos.DEFAULT_SHAPE_SIZE,
        intRangeStart=globalInfos.MIN_SHAPE_SIZE,
        intRangeStop=globalInfos.MAX_SHAPE_SIZE
    ),
    "result" : DisplayParam("bool",False),
    "3d" : DisplayParam("bool",False),
    "colors" : DisplayParam(
        "str",
        shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorModes[0].id,
        strAllowedValues=[cm.id for cm in shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorModes],
        strCaseMatters=False
    )
}

class RenderOutput(typing.TypedDict):
    errorMsgs:list[str]
    hasPotentialShapeCodes:bool
    finalImage:tuple[io.BytesIO,int]|None
    spoiler:bool
    shapeCodes:list[list[str]]|None
    viewer3dLinks:list[list[str]]|None

def renderShapes(message:str) -> RenderOutput:

    output:RenderOutput = {
        "errorMsgs" : [],
        "hasPotentialShapeCodes" : False,
        "finalImage" : None,
        "spoiler" : False,
        "shapeCodes" : None,
        "viewer3dLinks" : None
    }

    potentialShapeCodes:list[list[str]] = []
    for row in message.split(SHAPE_ROW_SEP):
        potentialRowShapeCodes = []
        for split in row.split(SHAPE_CODE_OPENING)[1:]:
            if SHAPE_CODE_CLOSING in split:
                potentialShapeCode = split.split(SHAPE_CODE_CLOSING)[0]
                # avoid considering parts that can't be shape codes
                if (potentialShapeCode != "") and ("\n" not in potentialShapeCode):
                    potentialRowShapeCodes.append(potentialShapeCode)
        potentialShapeCodes.append(potentialRowShapeCodes)

    if all(r == [] for r in potentialShapeCodes):
        output["errorMsgs"].append("No potential shape codes detected")
        return output

    output["hasPotentialShapeCodes"] = True
    shapes:list[list[tuple[gameObjects.Shape,gameObjects.ShapesConfiguration]]] = []

    shapeIndex = 1
    for row in potentialShapeCodes:
        shapes.append([])
        for code in row:
            errorMsg, result = shapeCodeGenerator.generateShapeCodes(code)
            if result is None:
                output["errorMsgs"].append(f"Invalid shape code for shape {shapeIndex} : {errorMsg}")
            else:
                shapes[-1].extend((shape,result[1]) for shape in result[0])
            shapeIndex += 1

    # remove leading empty rows
    for row in list(shapes):
        if row != []:
            break
        shapes.pop(0)

    # remove trailing empty rows
    for row in reversed(shapes):
        if row != []:
            break
        shapes.pop(-1)

    # no need to check for the case where all inner rows
    # would be empty as they would be removed above
    if shapes == []:
        if output["errorMsgs"] == []:
            raise ValueError("somehow no shapes generated and no error messages")
        return output

    if SHAPE_ROW_SEP not in message:
        rawShapes = shapes[0]
        rawShapesLen = len(rawShapes)
        shapesPerRaw = globalInfos.DEFAULT_SHAPES_PER_ROW
        if rawShapesLen > shapesPerRaw+2:
            shapes = []
            for i in range(math.ceil(rawShapesLen/shapesPerRaw)):
                shapes.append(rawShapes[i*shapesPerRaw:(i+1)*shapesPerRaw])

    potentialDisplayParams = getPotentialDisplayParamsFromMessage(message)
    curDisplayParams = {k:v.default for k,v in DISPLAY_PARAMS.items()}

    for param in potentialDisplayParams:
        if DISPLAY_PARAMS.get(param[0]) is not None:
            tempValue = DISPLAY_PARAMS[param[0]].getValidValue(param)
            if tempValue is not None:
                curDisplayParams[param[0]] = tempValue

    output["spoiler"] = curDisplayParams["spoiler"]
    if curDisplayParams["result"]:
        output["shapeCodes"] = [[s[0].toShapeCode() for s in row] for row in shapes]

    curDisplayParams["colors"] = curDisplayParams["colors"].upper()
    if curDisplayParams["colors"].endswith("-CB"):
        curDisplayParams["colors"] = curDisplayParams["colors"].removesuffix("-CB") + "-cb"
    curColorMode = shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorModesById[curDisplayParams["colors"]]

    size = curDisplayParams["size"]
    finalImage = shapez2.pygamePIL.Surface(
        (size*max(len(r) for r in shapes),size*len(shapes)),
        shapez2.pygamePIL.SRCALPHA
    )

    renderedShapesCache = {}
    for rowIndex,row in enumerate(shapes):
        for shapeIndex,shape in enumerate(row):
            if renderedShapesCache.get(shape) is None:
                renderedShapesCache[shape] = shapez2.shapeViewer.renderShape(
                    shape[0],size,curColorMode,shape[1]
                )
            finalImage.blit(
                renderedShapesCache[shape],
                (size*shapeIndex,size*rowIndex)
            )

    output["finalImage"] = utils.pygameSurfToBytes(finalImage)

    if curDisplayParams["3d"]:
        output["viewer3dLinks"] = []
        for row in shapes:
            output["viewer3dLinks"].append([])
            for shape,_ in row:
                shapeCode = shape.toShapeCode()
                linkSafeCode = shapeCode
                for old,new in globalInfos.LINK_CHAR_REPLACEMENT.items():
                    linkSafeCode = linkSafeCode.replace(old,new)
                link = f"[{shapeCode}](<{globalInfos.SHAPE_3D_VIEWER_LINK_START}{linkSafeCode}>)"
                output["viewer3dLinks"][-1].append(link)

    return output