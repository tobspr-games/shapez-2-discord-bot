import shapeOperations
import shapeCodeGenerator
import globalInfos
import shapeViewer
import utils
from utils import OutputString
import pygamePIL
import io
import typing

class Operation:

    def __init__(self,numInputs:int,numOutputs:int,fullName:str,
        func:typing.Callable[...,list[shapeOperations.Shape]],colorInputIndexes:list[int]|None=None) -> None:
        self.numInputs = numInputs
        self.numOutputs = numOutputs
        self.fullName = fullName
        self.func = func
        self.colorInputindexes = [] if colorInputIndexes is None else colorInputIndexes
        self.image:pygamePIL.Surface|None = None

class Instruction:

    DEF = "def"
    OP = "op"

    def __init__(self,type:str,*,shapeVars:list[int]|None=None,shapeCodes:list[str]|None=None,
            inputShapeVars:list[int]|None=None,inputColorVars:list[str]|None=None,operation:Operation|None=None,outputShapeVars:list[int]|None=None) -> None:
        self.type = type
        if type == Instruction.DEF:
            self.vars = shapeVars
            self.shapeCodes = shapeCodes
        else:
            self.inputs = inputShapeVars
            self.colorInputs = inputColorVars
            self.op = operation
            self.outputs = outputShapeVars

class GraphNode:

    SHAPE = "shape"
    OP = "op"

    def __init__(self,type:str,inputs:list[int]|None,outputs:list[int]|None,image:pygamePIL.Surface,
        shapeVar:int|None=None,shapeCode:str|None=None) -> None:
        self.type = type
        self.inputs = inputs
        self.outputs = outputs
        self.image = image
        self.shapeVar = shapeVar
        self.shapeCode = shapeCode
        self.layer = None
        self.pos = None

class _GraphNodeLoopError(Exception): ...

INSTRUCTION_SEPARATOR = ";"
DEFINITION_SEPARATOR = "="
VALUE_SEPARATOR = ","
OPERATION_SEPARATOR = ":"

IMAGES_START_PATH = "./operationGraphImages/"

GRAPH_NODE_SIZE = 100
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
    "sh" : Operation(2,2,"Swap halves",shapeOperations.swapHalves),
    "stack" : Operation(2,1,"Stack",shapeOperations.stack),
    "paint" : Operation(2,1,"Top paint",shapeOperations.topPaint,[1]),
    "pin" : Operation(1,1,"Push pin",shapeOperations.pushPin),
    "crystal" : Operation(2,1,"Generate crystals",shapeOperations.genCrystal,[1])
}

for k,v in OPERATIONS.items():
    v.image = pygamePIL.image_load(f"{IMAGES_START_PATH}{k}.png")

pygamePIL.font_init()
SHAPE_VAR_FONT = pygamePIL.font_Font(globalInfos.FONT_PATH,30)
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

            shapeCodesOrError, isShapeCodeValid = shapeCodeGenerator.generateShapeCodes(shapeCode)
            if not isShapeCodeValid:
                return False,OutputString("Error while decoding shape code : ",OutputString.UnsafeString(shapeCodesOrError))

            if len(shapeCodesOrError) != len(shapeVarsInt):
                return False,f"Number of shape codes outputed isn't the same as number of shape variables given ({len(shapeCodesOrError)} vs {len(shapeVarsInt)})"

            return True,Instruction(Instruction.DEF,shapeVars=shapeVarsInt,shapeCodes=shapeCodesOrError)

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
                if input not in globalInfos.SHAPE_COLORS:
                    return False,OutputString("Input ",OutputString.Number(i,True)," must be a color")
                colorInputs.append(input)
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

        return True,Instruction(Instruction.OP,inputShapeVars=inputsInt,inputColorVars=colorInputs,
            operation=curOperation,outputShapeVars=outputsInt)

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
    colorSkin:shapeViewer.EXTERNAL_COLOR_SKINS_ANNOTATION=shapeViewer.EXTERNAL_COLOR_SKINS[0]
) -> tuple[bool,str|OutputString|tuple[tuple[io.BytesIO,int],dict[int,str]]]:

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
        for var,code in zip(instruction.vars,instruction.shapeCodes):
            newInstructions.append(Instruction(Instruction.DEF,shapeVars=[var],shapeCodes=[code]))

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
    wasProcessingInstructionIndex = None

    def renderShape(shapeCode) -> pygamePIL.Surface:
        return shapeViewer.renderShape(shapeCode,GRAPH_NODE_SIZE,colorSkin)

    def newId() -> int:
        nonlocal curId
        curId += 1
        return curId - 1

    def genGraphNode(instruction:Instruction,instructionIndex:int) -> int:
        nonlocal wasProcessingInstructionIndex

        def createFinalOutputShape(inputs:list[int],shapeCode:str,shapeVar:int) -> int:
            curId = newId()
            graphNodes[curId] = GraphNode(GraphNode.SHAPE,inputs,None,renderShape(shapeCode),shapeVar,shapeCode)
            return curId

        if instructionIndex in handledInstructions:
            return handledInstructions[instructionIndex]

        if instruction.type == Instruction.DEF:

            curShapeVar = instruction.vars[0]
            curShapeCode = instruction.shapeCodes[0]

            curId = newId()
            graphNodes[curId] = GraphNode(GraphNode.SHAPE,None,None,
                renderShape(curShapeCode),curShapeVar,curShapeCode)
            handledInstructions[instructionIndex] = curId

            connectedInstructionLocation = inputLocations.get(curShapeVar)
            if connectedInstructionLocation is None:
                connectedNodeId = createFinalOutputShape([],curShapeCode,curShapeVar)
            else:
                connectedNodeId = genGraphNode(instructions[connectedInstructionLocation],connectedInstructionLocation)

            graphNodes[connectedNodeId].inputs.append(curId)
            graphNodes[curId].outputs = [connectedNodeId]
            return curId

        connectedInputs = []
        inputShapeCodes = []

        curCurId = newId()
        graphNodes[curCurId] = GraphNode(GraphNode.OP,[],[],instruction.op.image)
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
            inputShapeCodes.append(graphNodes[connectedInput].shapeCode)

        graphNodes[curCurId].inputs.extend(connectedInputs)

        wasProcessingInstructionIndex = instructionIndex
        outputShapeCodes = instruction.op.func(*[shapeOperations.Shape.fromShapeCode(s) for s in inputShapeCodes],*instruction.colorInputs)
        outputShapeCodes = [s.toShapeCode() for s in outputShapeCodes]

        toGenOutputs = []

        for output,outputShapeCode in zip(instruction.outputs,outputShapeCodes):
            outputLocation = inputLocations.get(output)
            if outputLocation is None:
                graphNodes[curCurId].outputs.append(createFinalOutputShape([curCurId],outputShapeCode,output))
            else:
                curId = newId()
                graphNodes[curId] = GraphNode(GraphNode.SHAPE,[curCurId],None,
                    renderShape(outputShapeCode),output,outputShapeCode)
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
            node.pos = (((graphWidth-layerWidth)/2)+(nodeIndex*(GRAPH_NODE_SIZE+GRAPH_H_MARGIN)),
                layerIndex*(GRAPH_NODE_SIZE+GRAPH_V_MARGIN))

    graphSurface = pygamePIL.Surface((graphWidth,graphHeight),pygamePIL.SRCALPHA)

    for node in graphNodes.values():
        if node.outputs is not None:
            for output in node.outputs:
                outputPos = graphNodes[output].pos
                pygamePIL.draw_line(graphSurface,LINE_COLOR,
                    (node.pos[0]+(GRAPH_NODE_SIZE/2),node.pos[1]+GRAPH_NODE_SIZE),
                    (outputPos[0]+(GRAPH_NODE_SIZE/2),outputPos[1]),LINE_WIDTH)

    shapeVarValues = {}

    for node in graphNodes.values():
        graphSurface.blit(node.image,node.pos)
        if node.type == GraphNode.SHAPE:
            shapeVarValues[node.shapeVar] = node.shapeCode
            if showShapeVars:
                varText = SHAPE_VAR_FONT.render(str(node.shapeVar),1,SHAPE_VAR_COLOR)
                graphSurface.blit(varText,(node.pos[0]+GRAPH_NODE_SIZE-varText.get_width(),
                    node.pos[1]+GRAPH_NODE_SIZE-varText.get_height()))

    return True,(utils.pygameSurfToBytes(graphSurface),shapeVarValues)