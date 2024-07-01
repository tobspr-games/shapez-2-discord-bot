import shapeCodeGenerator
import shapeViewer
import globalInfos
import utils
import pygamePIL
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

    def getValidValue(self,inputValue:tuple[str]|tuple[str,str]) -> bool|int|None:
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
        shapeViewer.EXTERNAL_COLOR_SKINS[0],
        strAllowedValues=shapeViewer.EXTERNAL_COLOR_SKINS,
        strCaseMatters=False
    )
}

def handleResponse(message:str) -> None|tuple[None|tuple[tuple[io.BytesIO,int],bool,None|list[str],None|list[str]],bool,list[str]]:

    potentialShapeCodes = shapeCodeGenerator.getPotentialShapeCodesFromMessage(message)

    if potentialShapeCodes == []:
        return

    shapeCodes:list[str] = []
    hasAtLeastOneInvalidShapeCode = False
    errorMsgs = []

    for i,code in enumerate(potentialShapeCodes):
        shapeCodesOrError, isShapeCodeValid = shapeCodeGenerator.generateShapeCodes(code)
        if isShapeCodeValid:
            shapeCodes.extend(shapeCodesOrError)
        else:
            errorMsgs.append(f"Invalid shape code for shape {i+1} : {shapeCodesOrError}")
            hasAtLeastOneInvalidShapeCode = True

    if shapeCodes == []:
        if hasAtLeastOneInvalidShapeCode:
            return None,hasAtLeastOneInvalidShapeCode,errorMsgs
        return None,True,["No non-empty shapes generated"]

    potentialDisplayParams = shapeCodeGenerator.getPotentialDisplayParamsFromMessage(message)
    curDisplayParams = {k:v.default for k,v in DISPLAY_PARAMS.items()}

    for param in potentialDisplayParams:
        if DISPLAY_PARAMS.get(param[0]) is not None:
            tempValue = DISPLAY_PARAMS[param[0]].getValidValue(param)
            if tempValue is not None:
                curDisplayParams[param[0]] = tempValue

    curDisplayParams["colors"] = curDisplayParams["colors"].upper()
    if curDisplayParams["colors"].endswith("-CB"):
        curDisplayParams["colors"] = curDisplayParams["colors"].removesuffix("-CB") + "-cb"

    numShapes = len(shapeCodes)
    size = curDisplayParams["size"]
    finalImage = pygamePIL.Surface(
        (size*min(globalInfos.SHAPES_PER_ROW,numShapes),size*(((numShapes-1)//globalInfos.SHAPES_PER_ROW)+1)),
        pygamePIL.SRCALPHA)

    renderedShapesCache = {}
    for i,code in enumerate(shapeCodes):
        if renderedShapesCache.get(code) is None:
            renderedShapesCache[code] = shapeViewer.renderShape(code,size,curDisplayParams["colors"])
        divMod = divmod(i,globalInfos.SHAPES_PER_ROW)
        finalImage.blit(renderedShapesCache[code],(size*divMod[1],size*divMod[0]))

    viewer3dLinks = None
    if curDisplayParams["3d"]:
        viewer3dLinks = []
        for code in shapeCodes:
            linkSafeCode = code
            for old,new in globalInfos.LINK_CHAR_REPLACEMENT.items():
                linkSafeCode = linkSafeCode.replace(old,new)
            link = f"[{code}](<{globalInfos.SHAPE_3D_VIEWER_LINK_START}{linkSafeCode}>)"
            viewer3dLinks.append(link)

    return (
        (
            utils.pygameSurfToBytes(finalImage),
            curDisplayParams["spoiler"],
            shapeCodes if curDisplayParams["result"] else None,
            viewer3dLinks
        ),
        hasAtLeastOneInvalidShapeCode,
        errorMsgs
    )