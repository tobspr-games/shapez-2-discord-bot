import shapeCodeGenerator
import globalInfos
import utils
from utils import OutputString

import shapez2
from shapez2 import pygamePIL, shapeOperations, gameObjects
import io
from collections.abc import Callable

class Operation:

    def __init__(
        self,
        numInputs:int,
        numOutputs:int,
        fullName:str,
        func:Callable[...,list[gameObjects.Shape]],
        colorInputIndexes:list[int]|None=None
    ) -> None:
        self.numInputs = numInputs
        self.numOutputs = numOutputs
        self.fullName = fullName
        self.func = func
        self.colorInputindexes = [] if colorInputIndexes is None else colorInputIndexes
        self.image:pygamePIL.Surface|None = None

class Instruction:

    DEF = "def"
    OP = "op"

    def __init__(
        self,
        type:str,
        *,
        shapeVars:list[int]|None=None,
        shapes:list[gameObjects.Shape]|None=None,
        shapesConfig:gameObjects.ShapesConfiguration|None=None,
        inputShapeVars:list[int]|None=None,
        inputColorVars:list[gameObjects.Color]|None=None,
        operation:Operation|None=None,
        outputShapeVars:list[int]|None=None
    ) -> None:
        self.type = type
        if type == Instruction.DEF:
            self.vars = shapeVars
            self.shapes = shapes
            self.shapesConfig = shapesConfig
        else:
            self.inputs = inputShapeVars
            self.colorInputs = inputColorVars
            self.op = operation
            self.outputs = outputShapeVars

class GraphNode:

    SHAPE = "shape"
    OP = "op"

    def __init__(
        self,
        type:str,
        inputs:list[int]|None,
        outputs:list[int]|None,
        image:pygamePIL.Surface,
        *,
        shapeVar:int|None=None,
        shape:gameObjects.Shape|None=None,
        shapesConfig:gameObjects.ShapesConfiguration|None=None,
        colorInputs:list[gameObjects.Color]|None=None
    ) -> None:
        self.type = type
        self.inputs = inputs
        self.outputs = outputs
        self.image = image
        self.shapeVar = shapeVar
        self.shape = shape
        self.shapesConfig = shapesConfig
        self.colorInputs = colorInputs
        self.layer = None
        self.pos = None

class _GraphNodeLoopError(Exception): ...

INSTRUCTION_SEPARATOR = ";"
DEFINITION_SEPARATOR = "="
VALUE_SEPARATOR = ","
OPERATION_SEPARATOR = ":"

IMAGES_START_PATH = "./operationGraphImages/"

GRAPH_NODE_SIZE = 100
NODE_COLOR_INPUT_WIDTH = 10
GRAPH_H_MARGIN = 100
GRAPH_V_MARGIN = 200
LINE_COLOR = (127,127,127)
LINE_WIDTH = 5

OPERATIONS:dict[str,Operation] = {
    "cut" : Operation(1,2,"Cut",shapeOperations.cut),
    "hcut" : Operation(1,1,"Half cut",shapeOperations.halfCut),
    "r90cw" : Operation(1,1,"Rotate 90° clockwise",shapeOperations.rotate90CW),
    "r90ccw" : Operation(1,1,"Rotate 90° counterclockwise",shapeOperations.rotate90CCW),
    "r180" : Operation(1,1,"Rotate 180°",shapeOperations.rotate180),
    "swap" : Operation(2,2,"Swap halves",shapeOperations.swapHalves),
    "stack" : Operation(2,1,"Stack",shapeOperations.stack),
    "paint" : Operation(2,1,"Top paint",shapeOperations.topPaint,[1]),
    "pin" : Operation(1,1,"Push pin",shapeOperations.pushPin),
    "crystal" : Operation(2,1,"Generate crystals",shapeOperations.genCrystal,[1]),
    "split" : Operation(1,2,"Split",lambda shape,config: [shape,shape])
}

for k,v in OPERATIONS.items():
    v.image = pygamePIL.image.load(f"{IMAGES_START_PATH}{k}.png")

pygamePIL.font.init()
SHAPE_VAR_FONT = pygamePIL.font.Font(globalInfos.FONT_PATH,30)
SHAPE_VAR_COLOR = (255,255,255)

def getInstructionsFromText(text:str) -> tuple[bool,list[Instruction]|str|OutputString]:

    def decodeInstruction(instruction:str) -> tuple[bool,str|OutputString|Instruction]:

        if DEFINITION_SEPARATOR in instruction:

            if instruction.count(DEFINITION_SEPARATOR) > 1:
                return False,f"Max 1 '{DEFINITION_SEPARATOR}' per instruction"

            shapeVars, shapeCode = instruction.split(DEFINITION_SEPARATOR)
            if shapeVars == "":
                return False,"Empty variables section"
            if shapeCode == "":
                return False,"Empty shape code section"

            shapeVars = shapeVars.split(VALUE_SEPARATOR)
            shapeVarsInt = []
            for i,sv in enumerate(shapeVars):
                try:
                    curVar = int(sv)
                except ValueError:
                    return False,OutputString("Shape variable ",OutputString.Number(i,True)," not an integer")
                if curVar < 0:
                    return False,OutputString("Shape variable ",OutputString.Number(i,True)," can't be negative")
                shapeVarsInt.append(curVar)

            errorMsg, result = shapeCodeGenerator.generateShapeCodes(shapeCode)
            if result is None:
                return False,OutputString("Error while decoding shape code : ",OutputString.UnsafeString(errorMsg))
            shapes, shapesConfig = result

            if len(shapes) != len(shapeVarsInt):
                return False,f"Number of shapes outputed isn't the same as number of shape variables given ({len(shapes)} vs {len(shapeVarsInt)})"

            return True,Instruction(Instruction.DEF,shapeVars=shapeVarsInt,shapes=shapes,shapesConfig=shapesConfig)

        if instruction.count(OPERATION_SEPARATOR) != 2:
            return False,f"Operation instruction must contain 2 '{OPERATION_SEPARATOR}'"

        inputs, op, outputs = instruction.split(OPERATION_SEPARATOR)
        for k,v in {"inputs":inputs,"operation":op,"outputs":outputs}.items():
            if v == "":
                return False,f"Empty {k} section"

        if OPERATIONS.get(op) is None:
            return False,OutputString("Unknown operation '",OutputString.UnsafeString(op),"'")

        inputs = inputs.split(VALUE_SEPARATOR)
        for old,new in globalInfos.SHAPE_CHAR_REPLACEMENT.items():
            inputs = [i.replace(old,new) for i in inputs]
        outputs = outputs.split(VALUE_SEPARATOR)
        inputsInt = []
        colorInputs = []
        outputsInt = []
        curOperation = OPERATIONS[op]

        for i,input in enumerate(inputs):
            if i in curOperation.colorInputindexes:
                if input not in [c.code for c in shapez2.ingameData.DEFAULT_COLOR_SCHEME.colors]:
                    return False,OutputString("Input ",OutputString.Number(i,True)," must be a color")
                colorInputs.append(shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorsByCode[input])
            else:
                try:
                    curVar = int(input)
                except ValueError:
                    return False,OutputString("Input ",OutputString.Number(i,True)," not an integer")
                if curVar < 0:
                    return False,OutputString("Input ",OutputString.Number(i,True)," can't be negative")
                inputsInt.append(curVar)

        for i,output in enumerate(outputs):
            try:
                curVar = int(output)
            except ValueError:
                return False,OutputString("Output ",OutputString.Number(i,True)," not an integer")
            if curVar < 0:
                return False,OutputString("Output ",OutputString.Number(i,True)," can't be negative")
            outputsInt.append(curVar)

        for e,g,t in zip((curOperation.numInputs,curOperation.numOutputs),(len(inputsInt)+len(colorInputs),len(outputsInt)),("inputs","outputs")):
            if e != g:
                return False,f"Number of operation {t} isn't the same as number of {t} given ({e} vs {g})"

        return True,Instruction(
            Instruction.OP,
            inputShapeVars=inputsInt,
            inputColorVars=colorInputs,
            operation=curOperation,
            outputShapeVars=outputsInt
        )

    if text == "":
        return False,"Empty text"

    instructions = text.split(INSTRUCTION_SEPARATOR)
    decodedInstructions = []

    for i,instruction in enumerate(instructions):
        valid, decodedInstructionOrError = decodeInstruction(instruction)
        if not valid:
            return False,OutputString("Error in instruction ",OutputString.Number(i,True)," : ",decodedInstructionOrError)
        decodedInstructions.append(decodedInstructionOrError)

    return True,decodedInstructions

def genOperationGraph(
    instructions:list[Instruction],
    showShapeVars:bool,
    colorMode:shapez2.gameObjects.ColorMode=shapez2.ingameData.DEFAULT_COLOR_SCHEME.colorModes[0],
    maxShapeLayers:int=4
) -> tuple[bool,str|OutputString|tuple[tuple[io.BytesIO,int],dict[int,gameObjects.Shape]]]:

    seenInputVars = []
    seenOutputVars = []

    for i,instruction in enumerate(instructions):

        errMsgStart = OutputString("Error in instruction ",OutputString.Number(i,True)," : ")

        if instruction.type == Instruction.DEF:

            for var in instruction.vars:
                if var in seenOutputVars:
                    return False,OutputString(errMsgStart,"Variable '",OutputString.UnsafeNumber(var),"' cannot be used as output/defined to multiple times")
                seenOutputVars.append(var)

        else:

            for var in instruction.inputs:
                if var in instruction.outputs:
                    return False,OutputString(errMsgStart,"Variable '",OutputString.UnsafeNumber(var),"' cannot be used as input and output in the same instruction")
                if var in seenInputVars:
                    return False,OutputString(errMsgStart,"Variable '",OutputString.UnsafeNumber(var),"' cannot be used as input multiple times")
                seenInputVars.append(var)

            for var in instruction.outputs:
                if var in seenOutputVars:
                    return False,OutputString(errMsgStart,"Variable '",OutputString.UnsafeNumber(var),"' cannot be used as output/defined to multiple times")
                seenOutputVars.append(var)

    for siv in seenInputVars:
        if siv not in seenOutputVars:
            return False,OutputString("Variable '",OutputString.UnsafeNumber(siv),"' is not used as output")

    newInstructions = []
    for instruction in instructions:
        if instruction.type == Instruction.OP:
            newInstructions.append(instruction)
            continue
        for var,shape in zip(instruction.vars,instruction.shapes):
            newInstructions.append(Instruction(
                Instruction.DEF,
                shapeVars=[var],
                shapes=[shape],
                shapesConfig=instruction.shapesConfig
            ))

    instructions = newInstructions.copy()

    inputLocations = {}
    outputLocations = {}

    for i,instruction in enumerate(instructions):
        if instruction.type == Instruction.DEF:
            outputLocations[instruction.vars[0]] = i
        else:
            for input in instruction.inputs:
                inputLocations[input] = i
            for output in instruction.outputs:
                outputLocations[output] = i

    graphNodes:dict[int,GraphNode] = {}
    curId = 0
    handledInstructions = {}
    wasProcessingInstructionIndex:int

    def renderShape(shape:gameObjects.Shape,shapesConfig:gameObjects.ShapesConfiguration) -> pygamePIL.Surface:
        return shapez2.shapeViewer.renderShape(shape,GRAPH_NODE_SIZE,colorMode,shapesConfig)

    def newId() -> int:
        nonlocal curId
        curId += 1
        return curId - 1

    def genGraphNode(instruction:Instruction,instructionIndex:int) -> int:
        nonlocal wasProcessingInstructionIndex

        def createFinalOutputShape(
            inputs:list[int],
            shape:gameObjects.Shape,
            shapeVar:int,
            shapesConfig:gameObjects.ShapesConfiguration
        ) -> int:
            curId = newId()
            graphNodes[curId] = GraphNode(
                GraphNode.SHAPE,
                inputs,
                None,
                renderShape(shape,shapesConfig),
                shapeVar=shapeVar,
                shape=shape,
                shapesConfig=shapesConfig
            )
            return curId

        if instructionIndex in handledInstructions:
            return handledInstructions[instructionIndex]

        if instruction.type == Instruction.DEF:

            curShapeVar = instruction.vars[0]
            curShape = instruction.shapes[0]
            curShapesConfig = instruction.shapesConfig

            curId = newId()
            graphNodes[curId] = GraphNode(
                GraphNode.SHAPE,
                None,
                None,
                renderShape(curShape,curShapesConfig),
                shapeVar=curShapeVar,
                shape=curShape,
                shapesConfig=curShapesConfig
            )
            handledInstructions[instructionIndex] = curId

            connectedInstructionLocation = inputLocations.get(curShapeVar)
            if connectedInstructionLocation is None:
                connectedNodeId = createFinalOutputShape([],curShape,curShapeVar,curShapesConfig)
            else:
                connectedNodeId = genGraphNode(instructions[connectedInstructionLocation],connectedInstructionLocation)

            graphNodes[connectedNodeId].inputs.append(curId)
            graphNodes[curId].outputs = [connectedNodeId]
            return curId

        connectedInputs = []
        inputShapes:list[gameObjects.Shape] = []
        inputShapesConfigs = []

        curCurId = newId()
        graphNodes[curCurId] = GraphNode(GraphNode.OP,[],[],instruction.op.image,colorInputs=instruction.colorInputs)
        handledInstructions[instructionIndex] = curCurId

        for input in instruction.inputs:
            inputLocation = outputLocations[input]
            inputNodeId = genGraphNode(instructions[inputLocation],inputLocation)
            if graphNodes[inputNodeId].type == GraphNode.SHAPE:
                connectedInput = inputNodeId
            else:
                if graphNodes[inputNodeId].outputs == []:
                    raise _GraphNodeLoopError
                for output in graphNodes[inputNodeId].outputs:
                    if graphNodes[output].shapeVar == input:
                        connectedInput = output
                        break

            connectedInputs.append(connectedInput)
            inputShapes.append(graphNodes[connectedInput].shape)
            inputShapesConfigs.append(graphNodes[connectedInput].shapesConfig)

        wasProcessingInstructionIndex = instructionIndex

        for inputShapesConfig in inputShapesConfigs[1:]:
            if inputShapesConfig != inputShapesConfigs[0]:
                raise shapeOperations.InvalidOperationInputs(
                    f"Differing input shapes configurations (quad/hex) aren't supported in '{instruction.op.fullName}' operation"
                )
        curShapesConfig = inputShapesConfigs[0]

        graphNodes[curCurId].inputs.extend(connectedInputs)

        inputShapes = [s.copy() for s in inputShapes]
        outputShapes = instruction.op.func(
            *inputShapes,
            *instruction.colorInputs,
            config=shapeOperations.ShapeOperationConfig(maxShapeLayers,curShapesConfig)
        )

        toGenOutputs = []

        for output,outputShape in zip(instruction.outputs,outputShapes):
            outputLocation = inputLocations.get(output)
            if outputLocation is None:
                graphNodes[curCurId].outputs.append(createFinalOutputShape([curCurId],outputShape,output,curShapesConfig))
            else:
                curId = newId()
                graphNodes[curId] = GraphNode(
                    GraphNode.SHAPE,
                    [curCurId],
                    None,
                    renderShape(outputShape,curShapesConfig),
                    shapeVar=output,
                    shape=outputShape,
                    shapesConfig=curShapesConfig
                )
                graphNodes[curCurId].outputs.append(curId)
                toGenOutputs.append((curId,outputLocation))
        for cid,ol in toGenOutputs:
            graphNodes[cid].outputs = [genGraphNode(instructions[ol],ol)]

        return curCurId

    try:
        for i,instruction in enumerate(instructions):
            genGraphNode(instruction,i)
    except shapeOperations.InvalidOperationInputs as e:
        return False,OutputString("Error happened in instruction ",OutputString.Number(wasProcessingInstructionIndex,True)," : ",str(e))
    except RecursionError:
        return False,f"Too many connected instructions"
    except _GraphNodeLoopError:
        return False,f"Error : loop in graph nodes"

    def getNodeLayer(node:GraphNode) -> int:
        if node.layer is None:
            if node.inputs is None:
                node.layer = 0
            else:
                node.layer = max(getNodeLayer(graphNodes[n]) for n in node.inputs)+1
        return node.layer

    for node in graphNodes.values():
        getNodeLayer(node)

    maxNodeLayer = max(n.layer for n in graphNodes.values())
    for node in graphNodes.values():
        if node.outputs is None:
            node.layer = maxNodeLayer

    graphNodesLayers:dict[int,dict[int,GraphNode]] = {}
    for nodeId,node in graphNodes.items():
        if graphNodesLayers.get(node.layer) is None:
            graphNodesLayers[node.layer] = {}
        graphNodesLayers[node.layer][nodeId] = node

    maxNodesPerLayer = max(len(l) for l in graphNodesLayers.values())
    graphWidth = round((maxNodesPerLayer*GRAPH_NODE_SIZE)+((maxNodesPerLayer-1)*GRAPH_H_MARGIN))
    graphHeight = round(((maxNodeLayer+1)*GRAPH_NODE_SIZE)+(maxNodeLayer*GRAPH_V_MARGIN))

    for layerIndex,layer in graphNodesLayers.items():
        layerLen = len(layer)
        layerWidth = (layerLen*GRAPH_NODE_SIZE)+((layerLen-1)*GRAPH_H_MARGIN)
        for nodeIndex,node in enumerate(layer.values()):
            node.pos = (
                ((graphWidth-layerWidth)/2)+(nodeIndex*(GRAPH_NODE_SIZE+GRAPH_H_MARGIN)),
                layerIndex*(GRAPH_NODE_SIZE+GRAPH_V_MARGIN)
            )

    graphSurface = pygamePIL.Surface((graphWidth,graphHeight),pygamePIL.SRCALPHA)

    for node in graphNodes.values():
        if node.outputs is not None:
            for output in node.outputs:
                outputPos = graphNodes[output].pos
                pygamePIL.draw.line(
                    graphSurface,
                    LINE_COLOR,
                    (node.pos[0]+(GRAPH_NODE_SIZE/2),node.pos[1]+GRAPH_NODE_SIZE),
                    (outputPos[0]+(GRAPH_NODE_SIZE/2),outputPos[1]),
                    LINE_WIDTH
                )

    shapeVarValues = {}

    for node in graphNodes.values():
        if (node.type == GraphNode.OP) and (len(node.colorInputs) != 0):
            curImage = pygamePIL.transform.smoothscale(node.image,(GRAPH_NODE_SIZE-NODE_COLOR_INPUT_WIDTH,)*2)
            curImagePos = (node.pos[0],node.pos[1]+(NODE_COLOR_INPUT_WIDTH/2))
        else:
            curImage = node.image
            curImagePos = node.pos
        graphSurface.blit(curImage,curImagePos)
        if node.type == GraphNode.SHAPE:
            shapeVarValues[node.shapeVar] = node.shape
            if showShapeVars:
                varText = SHAPE_VAR_FONT.render(str(node.shapeVar),1,SHAPE_VAR_COLOR)
                graphSurface.blit(varText,(
                    node.pos[0]+GRAPH_NODE_SIZE-varText.get_width(),
                    node.pos[1]+GRAPH_NODE_SIZE-varText.get_height()
                ))
        else:
            if len(node.colorInputs) != 0:
                curColorInputHeight = GRAPH_NODE_SIZE / len(node.colorInputs)
                for colorIndex,color in enumerate(node.colorInputs):
                    pygamePIL.draw.rect(
                        graphSurface,
                        colorMode.colorSkin.colors[color],
                        pygamePIL.Rect(
                            node.pos[0] + GRAPH_NODE_SIZE - NODE_COLOR_INPUT_WIDTH,
                            node.pos[1] + (curColorInputHeight*colorIndex),
                            NODE_COLOR_INPUT_WIDTH,
                            curColorInputHeight
                        )
                    )

    return True,(utils.pygameSurfToBytes(graphSurface),shapeVarValues)