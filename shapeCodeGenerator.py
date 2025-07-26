import globalInfos

import math
from shapez2 import gameObjects, ingameData, shapeCodes

STRUCT_EMPTY_CHAR = "0"
STRUCT_SHAPE_CHAR = "1"
STRUCT_COLORS = ["r","g","b","w"]
STRUCT_SHAPE = {
    ingameData.QUAD_SHAPES_CONFIG : "C",
    ingameData.HEX_SHAPES_CONFIG : "H"
}

PARAM_PREFIX = "+"
DISPLAY_PARAM_PREFIX = "/"
DISPLAY_PARAM_EXIT_CHAR = " "
DISPLAY_PARAM_KEY_VALUE_SEPARATOR = ":"
SHAPE_CODE_OPENING = "{"
SHAPE_CODE_CLOSING = "}"
INGNORE_CHARS_IN_SHAPE_CODE = ["`"]

def getPotentialShapeCodesFromMessage(message:str) -> list[str]:
    if (message == "") or (SHAPE_CODE_OPENING not in message):
        return []
    openingSplits = message.split(SHAPE_CODE_OPENING)[1:]
    potentialShapeCodes = []
    for split in openingSplits:
        if SHAPE_CODE_CLOSING in split:
            potentialShapeCode = split.split(SHAPE_CODE_CLOSING)[0]
            if potentialShapeCode != "":
                potentialShapeCodes.append(potentialShapeCode)
    return potentialShapeCodes

def getPotentialDisplayParamsFromMessage(message:str) -> list[tuple]:
    if (message == "") or (DISPLAY_PARAM_PREFIX not in message):
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

def generateShapeCodes(potentialShapeCode:str) -> tuple[
    str,
    tuple[list[gameObjects.Shape],gameObjects.ShapesConfiguration]|None
]:
    """Returns ``errorMsg``, (``[shape0,shape1,...]``, ``shapesConfig``) """

    def getStructColor(layer:int) -> str:
        return STRUCT_COLORS[min(layer,len(STRUCT_COLORS)-1)]

    errorMsg = ""
    result = None

    def inner() -> bool:
        nonlocal potentialShapeCode, errorMsg, result

        for char in INGNORE_CHARS_IN_SHAPE_CODE:
            potentialShapeCode = potentialShapeCode.replace(char,"")

        if PARAM_PREFIX in potentialShapeCode:
            params = potentialShapeCode.split(PARAM_PREFIX)
            potentialShapeCode = params[0]
            params = params[1:]
        else:
            params = []

        cutInParams = "cut" in params
        qcutInParams = "qcut" in params
        if cutInParams and qcutInParams:
            errorMsg = "Mutualy exclusive 'cut' and 'qcut' parameters present"
            return False

        curColorScheme = ingameData.DEFAULT_COLOR_SCHEME
        curColors = [c.code for c in curColorScheme.colors]

        structInParams = "struct" in params

        # separate in layers
        if shapeCodes.LAYER_SEPARATOR in potentialShapeCode:
            layers = potentialShapeCode.split(shapeCodes.LAYER_SEPARATOR)
            for i,layer in enumerate(layers):
                if layer == "":
                    errorMsg = f"Layer {i+1} empty"
                    return False
        else:
            if potentialShapeCode == "":
                errorMsg = "Empty shape code"
                return False
            layers = [potentialShapeCode]

        # handle lfill
        if "lfill" in params:
            layersLen = len(layers)
            if layersLen == 1:
                layers = [layers[0]] * 4
            elif layersLen == 2:
                layers = [layers[0],layers[1]] * 2

        # replace some characters
        for old,new in globalInfos.SHAPE_CHAR_REPLACEMENT.items():
            for layerIndex,layer in enumerate(layers):
                layers[layerIndex] = layer.replace(old,new)

        # verify if only valid chars and determine shapes config
        if "hex" in params:
            toTestShapesConfigs = [ingameData.HEX_SHAPES_CONFIG]
        else:
            toTestShapesConfigs = [ingameData.QUAD_SHAPES_CONFIG,ingameData.HEX_SHAPES_CONFIG]
        def verifyOnlyValidChars(shapesConfig:gameObjects.ShapesConfiguration) -> bool:
            nonlocal errorMsg
            for layerIndex,layer in enumerate(layers):
                for charIndex,char in enumerate(layer):
                    if char not in (
                        [p.code for p in shapesConfig.parts]
                        + curColors
                        + [shapeCodes.EMPTY_CHAR,STRUCT_SHAPE_CHAR,STRUCT_EMPTY_CHAR]
                    ):
                        errorMsg = f"Invalid character in layer {layerIndex+1} ({layer}), at character {charIndex+1} : '{char}'"
                        return False
            return True
        curShapesConfig = None
        for testShapesConfig in toTestShapesConfigs:
            if verifyOnlyValidChars(testShapesConfig):
                curShapesConfig = testShapesConfig
                break
        if curShapesConfig is None:
            # errorMsg already set
            return False
        curShapeParts = [p.code for p in curShapesConfig.parts]
        curColorableShapes = [p.code for p in curShapesConfig.parts if p.hasColor]
        curNonColorableShapes = [p.code for p in curShapesConfig.parts if not p.hasColor]

        # handle struct
        if structInParams:
            for i,layer in enumerate(layers):
                newLayer = ""
                color = getStructColor(i)
                for char in layer:
                    if char == STRUCT_SHAPE_CHAR:
                        newLayer += STRUCT_SHAPE[curShapesConfig] + color
                    elif char == STRUCT_EMPTY_CHAR:
                        newLayer += shapeCodes.EMPTY_CHAR * 2
                    else:
                        newLayer += char
                layers[i] = newLayer

        # handle {C} -> {Cu} transformation
        for layerIndex,layer in enumerate(layers):
            newLayer = ""
            lastChar = len(layer)-1
            skipNext = False
            for charIndex,char in enumerate(layer):
                newLayer += char
                if skipNext:
                    skipNext = False
                    continue
                expand = False
                isLastChar = charIndex == lastChar
                if (
                    (char in curColorableShapes)
                    and (isLastChar or (layer[charIndex+1] not in curColors))
                ):
                    expand = True
                elif (
                    (char in (curNonColorableShapes+[shapeCodes.EMPTY_CHAR]))
                    and (isLastChar or (layer[charIndex+1] != shapeCodes.EMPTY_CHAR))
                ):
                    expand = True
                if expand:
                    if char in curColorableShapes:
                        newLayer += (
                            getStructColor(layerIndex)
                            if structInParams else
                            curColorScheme.defaultColor.code
                        )
                    else:
                        newLayer += shapeCodes.EMPTY_CHAR
                else:
                    skipNext = True
            layers[layerIndex] = newLayer

        # verify if shapes and colors are in the right positions
        for layerIndex,layer in enumerate(layers):
            shapeMode = True
            lastChar = len(layer)-1
            for charIndex,char in enumerate(layer):
                errorMsg = f"Character in layer {layerIndex+1} ({layer}) at character {charIndex+1} ({char}) "
                if shapeMode:
                    if char not in (curShapeParts+[shapeCodes.EMPTY_CHAR]):
                        errorMsg += "must be a shape or empty"
                        return False
                    if charIndex == lastChar:
                        errorMsg += "should have a color but is end of layer"
                        return False
                    nextMustBeColor = char in curColorableShapes
                    shapeMode = False
                else:
                    if char not in (curColors+[shapeCodes.EMPTY_CHAR]):
                        errorMsg += "must be a color or empty"
                        return False
                    if nextMustBeColor and (char not in curColors):
                        errorMsg += "must be a color"
                        return False
                    if (not nextMustBeColor) and (char != shapeCodes.EMPTY_CHAR):
                        errorMsg += "must be empty"
                        return False
                    shapeMode = True

        # handle fill
        if "fill" in params:
            for layerIndex,layer in enumerate(layers):
                newLayer = ""
                layerLen = len(layer)
                if curShapesConfig.numPartsPerLayer == 6:
                    if layerLen == 2:
                        newLayer = layer * 6
                    elif layerLen == 4:
                        newLayer = layer * 3
                    elif layerLen == 6:
                        newLayer = layer * 2
                    else:
                        newLayer = layer
                else:
                    if layerLen == 2:
                        newLayer = layer * 4
                    elif layerLen == 4:
                        newLayer = layer * 2
                    else:
                        newLayer = layer
                layers[layerIndex] = newLayer

        # verify all layers have the same length
        expectedLayerLen = len(layers[0])
        for layerIndex,layer in enumerate(layers[1:]):
            if len(layer) != expectedLayerLen:
                errorMsg = (
                    f"Layer {layerIndex+2} ({layer})"
                    + (f" (or 1 ({layers[0]}))" if layerIndex == 0 else "")
                    + " doesn't have the expected number of parts"
                )
                return False

        # handle lsep
        if "lsep" in params:
            curShapeCodes = [[layer] for layer in layers]
        else:
            curShapeCodes = [layers]

        # handle cut
        if cutInParams:
            newShapeCodes = []
            for shape in curShapeCodes:
                numParts = round(len(shape[0])/2)
                takeParts = math.ceil(numParts/2)
                shape1 = []
                shape2 = []
                for layer in shape:
                    shape1.append(f"{shapeCodes.EMPTY_CHAR*((numParts-takeParts)*2)}{layer[-(takeParts*2):]}")
                    shape2.append(f"{layer[:-(takeParts*2)]}{shapeCodes.EMPTY_CHAR*(takeParts*2)}")
                newShapeCodes.extend([shape1,shape2])

        # handle qcut
        elif qcutInParams:
            newShapeCodes = []
            for shape in curShapeCodes:
                numParts = round(len(shape[0])/2)
                takeParts = math.ceil(numParts/2)
                takeParts1 = math.ceil(takeParts/2)
                takeParts2 = takeParts - takeParts1
                takeParts3 = math.ceil((numParts-takeParts)/2)
                takeParts4 = numParts - takeParts - takeParts3
                shape1 = []
                shape2 = []
                shape3 = []
                shape4 = []
                for layer in shape:
                    shape1.append(f"{layer[:takeParts1*2]}{shapeCodes.EMPTY_CHAR*((takeParts2+takeParts3+takeParts4)*2)}")
                    shape2.append(f"{shapeCodes.EMPTY_CHAR*(takeParts1*2)}{layer[takeParts1*2:(takeParts1+takeParts2)*2]}{shapeCodes.EMPTY_CHAR*((takeParts3+takeParts4)*2)}")
                    shape3.append(f"{shapeCodes.EMPTY_CHAR*((takeParts1+takeParts2)*2)}{layer[(takeParts1+takeParts2)*2:(takeParts1+takeParts2+takeParts3)*2]}{shapeCodes.EMPTY_CHAR*(takeParts4*2)}")
                    shape4.append(f"{shapeCodes.EMPTY_CHAR*((takeParts1+takeParts2+takeParts3)*2)}{layer[(takeParts1+takeParts2+takeParts3)*2:]}")
                newShapeCodes.extend([shape1,shape2,shape3,shape4])
        else:
            newShapeCodes = curShapeCodes

        shapeCodesNoEmpty = []
        for shape in newShapeCodes:
            if any(any(c != shapeCodes.EMPTY_CHAR for c in l) for l in layers):
                shapeCodesNoEmpty.append(shapeCodes.LAYER_SEPARATOR.join(shape))

        resultingShapes = [gameObjects.Shape.fromShapeCode(s,curShapesConfig,curColorScheme) for s in shapeCodesNoEmpty]

        result = (resultingShapes,curShapesConfig)
        return True

    inner()
    return errorMsg, result