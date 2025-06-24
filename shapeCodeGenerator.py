import globalInfos
import math
import shapez2

COLORS = shapez2.gameData.SHAPE_COLORS
NOTHING_CHAR = shapez2.gameData.SHAPE_NOTHING_CHAR
SHAPE_CONFIG_QUAD = shapez2.gameData.SHAPE_CONFIG_QUAD
SHAPE_CONFIG_HEX = shapez2.gameData.SHAPE_CONFIG_HEX
COLOR_SHAPES = shapez2.shapeCodes.COLOR_SHAPES
NO_COLOR_SHAPES = shapez2.shapeCodes.NO_COLOR_SHAPES

COLOR_SHAPES_DEFAULT_COLOR = COLORS[0]
NO_COLOR_SHAPES_DEFAULT_COLOR = NOTHING_CHAR
STRUCT_COLORS = ["r","g","b","w"]
STRUCT_SHAPE = {
    SHAPE_CONFIG_QUAD : "C",
    SHAPE_CONFIG_HEX : "H"
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

def generateShapeCodes(potentialShapeCode:str) -> tuple[tuple[list[str],str]|str,bool]:
    """Returns (``([shapeCode0,shapeCode1,...], shapeConfig)`` or ``errorMsg``), ``isShapeCodeValid``"""

    def getStructColor(layer:int) -> str:
        return STRUCT_COLORS[min(layer,len(STRUCT_COLORS)-1)]

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
        return "Mutualy exclusive 'cut' and 'qcut' parameters present",False

    hexInParams = "hex" in params
    curShapeConfig = SHAPE_CONFIG_HEX if hexInParams else SHAPE_CONFIG_QUAD

    structInParams = "struct" in params

    # separate in layers
    layersResult = shapez2.shapeCodes._separateInLayers(potentialShapeCode)
    if not layersResult[1]:
        return layersResult[0],False
    layers:list[str] = layersResult[0]

    # handle lfill
    if "lfill" in params:
        layersLen = len(layers)
        if layersLen == 1:
            layers = [layers[0]] * 4
        elif layersLen == 2:
            layers = [layers[0],layers[1]] * 2

    # handle struct
    if structInParams:
        for i,layer in enumerate(layers):
            newLayer = ""
            color = getStructColor(i)
            for char in layer:
                if char == "1":
                    newLayer += STRUCT_SHAPE[curShapeConfig] + color
                elif char == "0":
                    newLayer += NOTHING_CHAR * 2
                else:
                    newLayer += char
            layers[i] = newLayer

    # replace some characters
    for old,new in globalInfos.SHAPE_CHAR_REPLACEMENT.items():
        for layerIndex,layer in enumerate(layers):
            layers[layerIndex] = layer.replace(old,new)

    # verify if only valid chars
    validCharsResult = shapez2.shapeCodes._verifyOnlyValidChars(layers,curShapeConfig)
    if not validCharsResult[1]:
        return validCharsResult[0],False

    # handle {C} -> {Cu} transformation
    for layerIndex,layer in enumerate(layers):
        newLayer = ""
        lastChar = len(layer)-1
        skipNext = False
        for charIndex,char in enumerate(layer):
            if skipNext:
                newLayer += char
                skipNext = False
                continue
            expand = False
            isLastChar = charIndex == lastChar
            if (char in COLOR_SHAPES[curShapeConfig]) and ((isLastChar) or (layer[charIndex+1] not in COLORS)):
                expand = True
            elif (char in [*NO_COLOR_SHAPES[curShapeConfig],NOTHING_CHAR]) and ((isLastChar) or (layer[charIndex+1] != NOTHING_CHAR)):
                expand = True
            if expand:
                if char in [*NO_COLOR_SHAPES[curShapeConfig],NOTHING_CHAR]:
                    newLayer += char + NO_COLOR_SHAPES_DEFAULT_COLOR
                else:
                    newLayer += char + (getStructColor(layerIndex) if structInParams else COLOR_SHAPES_DEFAULT_COLOR)
            else:
                skipNext = True
                newLayer += char
        layers[layerIndex] = newLayer

    # verify if shapes and colors are in the right positions
    shapesAndColorsInRightPosResult = shapez2.shapeCodes._verifyShapesAndColorsInRightPos(layers,curShapeConfig)
    if not shapesAndColorsInRightPosResult[1]:
        return shapesAndColorsInRightPosResult[0],False

    # handle fill
    if "fill" in params:
        for layerIndex,layer in enumerate(layers):
            newLayer = ""
            layerLen = len(layer)
            if hexInParams:
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
    allLayersHaveSameLenResult = shapez2.shapeCodes._verifyAllLayersHaveSameLen(layers)
    if not allLayersHaveSameLenResult[1]:
        return allLayersHaveSameLenResult[0],False

    # handle lsep
    if "lsep" in params:
        shapeCodes = [[layer] for layer in layers]
    else:
        shapeCodes = [layers]

    # handle cut
    if cutInParams:
        newShapeCodes = []
        for shape in shapeCodes:
            numParts = round(len(shape[0])/2)
            takeParts = math.ceil(numParts/2)
            shape1 = []
            shape2 = []
            for layer in shape:
                shape1.append(f"{NOTHING_CHAR*((numParts-takeParts)*2)}{layer[-(takeParts*2):]}")
                shape2.append(f"{layer[:-(takeParts*2)]}{NOTHING_CHAR*(takeParts*2)}")
            newShapeCodes.extend([shape1,shape2])

    # handle qcut
    elif qcutInParams:
        newShapeCodes = []
        for shape in shapeCodes:
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
                shape1.append(f"{layer[:takeParts1*2]}{NOTHING_CHAR*((takeParts2+takeParts3+takeParts4)*2)}")
                shape2.append(f"{NOTHING_CHAR*(takeParts1*2)}{layer[takeParts1*2:(takeParts1+takeParts2)*2]}{NOTHING_CHAR*((takeParts3+takeParts4)*2)}")
                shape3.append(f"{NOTHING_CHAR*((takeParts1+takeParts2)*2)}{layer[(takeParts1+takeParts2)*2:(takeParts1+takeParts2+takeParts3)*2]}{NOTHING_CHAR*(takeParts4*2)}")
                shape4.append(f"{NOTHING_CHAR*((takeParts1+takeParts2+takeParts3)*2)}{layer[(takeParts1+takeParts2+takeParts3)*2:]}")
            newShapeCodes.extend([shape1,shape2,shape3,shape4])
    else:
        newShapeCodes = shapeCodes

    noEmptyShapeCodes = []
    for shape in newShapeCodes:
        if not shapez2.shapeCodes._isShapeEmpty(shape):
            noEmptyShapeCodes.append(shapez2.gameData.SHAPE_LAYER_SEPARATOR.join(shape))

    return (noEmptyShapeCodes,curShapeConfig),True