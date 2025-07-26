import shapeCodeGenerator
import globalInfos
import utils

import shapez2
from shapez2 import gameObjects
import io
import typing

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
    shapeCodes:list[str]|None
    viewer3dLinks:list[str]|None

def renderShapes(message:str) -> RenderOutput:

    output:RenderOutput = {
        "errorMsgs" : [],
        "hasPotentialShapeCodes" : False,
        "finalImage" : None,
        "spoiler" : False,
        "shapeCodes" : None,
        "viewer3dLinks" : None
    }

    potentialShapeCodes = shapeCodeGenerator.getPotentialShapeCodesFromMessage(message)

    if potentialShapeCodes == []:
        output["errorMsgs"].append("No potential shape codes detected")
        return output

    output["hasPotentialShapeCodes"] = True
    shapes:list[tuple[gameObjects.Shape,gameObjects.ShapesConfiguration]] = []

    for i,code in enumerate(potentialShapeCodes):
        errorMsg, result = shapeCodeGenerator.generateShapeCodes(code)
        if result is None:
            output["errorMsgs"].append(f"Invalid shape code for shape {i+1} : {errorMsg}")
        else:
            shapes.extend((shape,result[1]) for shape in result[0])

    if shapes == []:
        if output["errorMsgs"] == []:
            output["errorMsgs"].append("No non-empty shapes generated")
        return output

    potentialDisplayParams = shapeCodeGenerator.getPotentialDisplayParamsFromMessage(message)
    curDisplayParams = {k:v.default for k,v in DISPLAY_PARAMS.items()}

    for param in potentialDisplayParams:
        if DISPLAY_PARAMS.get(param[0]) is not None:
            tempValue = DISPLAY_PARAMS[param[0]].getValidValue(param)
            if tempValue is not None:
                curDisplayParams[param[0]] = tempValue

    output["spoiler"] = curDisplayParams["spoiler"]
    if curDisplayParams["result"]:
        output["shapeCodes"] = [s[0].toShapeCode() for s in shapes]

    curDisplayParams["colors"] = curDisplayParams["colors"].upper()
    if curDisplayParams["colors"].endswith("-CB"):
        curDisplayParams["colors"] = curDisplayParams["colors"].removesuffix("-CB") + "-cb"
    curColorMode = shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorModesById[curDisplayParams["colors"]]

    numShapes = len(shapes)
    size = curDisplayParams["size"]
    finalImage = shapez2.pygamePIL.Surface(
        (size*min(globalInfos.SHAPES_PER_ROW,numShapes),size*(((numShapes-1)//globalInfos.SHAPES_PER_ROW)+1)),
        shapez2.pygamePIL.SRCALPHA
    )

    renderedShapesCache = {}
    for i,shape in enumerate(shapes):
        if renderedShapesCache.get(shape) is None:
            renderedShapesCache[shape] = shapez2.shapeViewer.renderShape(shape[0],size,curColorMode,shape[1])
        divMod = divmod(i,globalInfos.SHAPES_PER_ROW)
        finalImage.blit(renderedShapesCache[shape],(size*divMod[1],size*divMod[0]))

    output["finalImage"] = utils.pygameSurfToBytes(finalImage)

    if curDisplayParams["3d"]:
        output["viewer3dLinks"] = []
        for shape,_ in shapes:
            shapeCode = shape.toShapeCode()
            linkSafeCode = shapeCode
            for old,new in globalInfos.LINK_CHAR_REPLACEMENT.items():
                linkSafeCode = linkSafeCode.replace(old,new)
            link = f"[{shapeCode}](<{globalInfos.SHAPE_3D_VIEWER_LINK_START}{linkSafeCode}>)"
            output["viewer3dLinks"].append(link)

    return output