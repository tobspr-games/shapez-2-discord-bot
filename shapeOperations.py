import globalInfos
import math
import typing

NOTHING_CHAR = globalInfos.SHAPE_NOTHING_CHAR
PIN_CHAR = "P"
CRYSTAL_CHAR = "c"
UNPAINTABLE_SHAPES = [CRYSTAL_CHAR,PIN_CHAR,NOTHING_CHAR]
REPLACED_BY_CRYSTAL = [PIN_CHAR,NOTHING_CHAR]
MAX_LAYERS = 4

class Quadrant:

    def __init__(self,shape:str,color:str) -> None:
        self.shape = shape
        self.color = color

class Shape:

    def __init__(self,layers:list[list[Quadrant]]) -> None:
        self.layers = layers
        self.numLayers = len(layers)
        self.numQuads = len(layers[0])

    def fromListOfLayers(layers:list[str]):
        newLayers:list[list[Quadrant]] = []
        numQuads = int(len(layers[0])/2)
        for layer in layers:
            newLayers.append([])
            for quadIndex in range(numQuads):
                newLayers[-1].append(Quadrant(layer[quadIndex*2],layer[(quadIndex*2)+1]))
        return Shape(newLayers)

    def fromShapeCode(shapeCode:str):
        return Shape.fromListOfLayers(shapeCode.split(globalInfos.SHAPE_LAYER_SEPARATOR))

    def toListOfLayers(self) -> list[str]:
        return ["".join(q.shape+q.color for q in l) for l in self.layers]

    def toShapeCode(self) -> str:
        return globalInfos.SHAPE_LAYER_SEPARATOR.join(self.toListOfLayers())
    
    def isEmpty(self) -> bool:
        return all(c == NOTHING_CHAR for c in "".join(self.toListOfLayers()))

class InvalidOperationInputs(ValueError): ...

def _gravityConnected(quad1:Quadrant,quad2:Quadrant) -> bool:
    if (quad1.shape in (NOTHING_CHAR,PIN_CHAR)) or (quad2.shape in (NOTHING_CHAR,PIN_CHAR)):
        return False
    return True

def _crystalsFused(quad1:Quadrant,quad2:Quadrant) -> bool:
    if (quad1.shape == CRYSTAL_CHAR) and (quad2.shape == CRYSTAL_CHAR):
        return True
    return False

def _getCorrectedIndex(list:list,index:int) -> int:
    if index > len(list)-1:
        return index - len(list)
    if index < 0:
        return len(list) + index
    return index

def _getConnectedSingleLayer(layer:list[Quadrant],index:int,connectedFunc:typing.Callable[[Quadrant,Quadrant],bool]) -> list[int]:

    if layer[index].shape == NOTHING_CHAR:
        return []

    connected = [index]
    previousIndex = index

    for i in range(index+1,len(layer)+index):
        curIndex = _getCorrectedIndex(layer,i)
        if not connectedFunc(layer[previousIndex],layer[curIndex]):
            break
        connected.append(curIndex)
        previousIndex = curIndex

    previousIndex = index
    for i in range(index-1,-len(layer)+index,-1):
        curIndex = _getCorrectedIndex(layer,i)
        if curIndex in connected:
            break
        if not connectedFunc(layer[previousIndex],layer[curIndex]):
            break
        connected.append(curIndex)
        previousIndex = curIndex

    return connected

def _getConnectedMultiLayer(layers:list[list[Quadrant]],layerIndex:int,quadIndex:int,
    connectedFunc:typing.Callable[[Quadrant,Quadrant],bool]) -> list[tuple[int,int]]:

    if layers[layerIndex][quadIndex].shape == NOTHING_CHAR:
        return []

    connected = [(layerIndex,quadIndex)]
    for curLayer,curQuad in connected:

        # same layer
        for quadIndex in _getConnectedSingleLayer(layers[curLayer],curQuad,connectedFunc):
            if (curLayer,quadIndex) not in connected:
                connected.append((curLayer,quadIndex))

        # layer below
        toCheckLayer, toCheckQuad = curLayer-1, curQuad
        if (curLayer > 0) and ((toCheckLayer,toCheckQuad) not in connected):
            if connectedFunc(layers[curLayer][curQuad],layers[toCheckLayer][toCheckQuad]):
                connected.append((toCheckLayer,toCheckQuad))

        # layer above
        toCheckLayer, toCheckQuad = curLayer+1, curQuad
        if (curLayer < (len(layers)-1)) and ((toCheckLayer,toCheckQuad) not in connected):
            if connectedFunc(layers[curLayer][curQuad],layers[toCheckLayer][toCheckQuad]):
                connected.append((toCheckLayer,toCheckQuad))

    return connected

def _breakCrystals(layers:list[list[Quadrant]],layerIndex:int,quadIndex:int) -> None:
    for curLayer,curQuad in _getConnectedMultiLayer(layers,layerIndex,quadIndex,_crystalsFused):
        layers[curLayer][curQuad] = Quadrant(NOTHING_CHAR,NOTHING_CHAR)

# to do (in the future) : decide what to do in case of two crystals connected vertically above an empty quadrant : do they stick or both break
def _makeLayersFall(layers:list[list[Quadrant]]) -> list[list[Quadrant]]:

    def sepInGroups(layer:list[Quadrant]) -> list[list[int]]:
        handledIndexes = []
        groups = []
        for quadIndex,_ in enumerate(layer):
            if quadIndex in handledIndexes:
                continue
            group = _getConnectedSingleLayer(layer,quadIndex,_gravityConnected)
            if group != []:
                groups.append(group)
                handledIndexes.extend(group)
        return groups

    for layerIndex,layer in enumerate(layers):
        if layerIndex == 0:
            continue

        for group in sepInGroups(layer): # first pass : break crystals
            fall = True
            for quadIndex in group:
                if layers[layerIndex-1][quadIndex].shape != NOTHING_CHAR:
                    fall = False
                    break
            if fall:
                for quadIndex in group:
                    if layer[quadIndex].shape == CRYSTAL_CHAR:
                        layer[quadIndex] = Quadrant(NOTHING_CHAR,NOTHING_CHAR)

        for group in sepInGroups(layer): # second pass : make layers fall with removed crystals
            for layerIndex2 in range(layerIndex,0,-1):
                fall = True
                for quadIndex in group:
                    if layers[layerIndex2-1][quadIndex].shape != NOTHING_CHAR:
                        fall = False
                        break
                if not fall:
                    break
                for quadIndex in group:
                    layers[layerIndex2-1][quadIndex] = layers[layerIndex2][quadIndex]
                    layers[layerIndex2][quadIndex] = Quadrant(NOTHING_CHAR,NOTHING_CHAR)

    return layers

def _cleanUpEmptyUpperLayers(layers:list[list[Quadrant]]) -> list[list[Quadrant]]:
    if len(layers) == 1:
        return layers
    for i in range(len(layers)-1,-1,-1):
        if any((q.shape != NOTHING_CHAR) for q in layers[i]):
            break
    return layers[:i+1]

def _differentNumQuadsUnsupported(func):
    def wrapper(*args,**kwargs) -> None:
        shapes:list[Shape] = []
        for arg in args:
            if type(arg) == Shape:
                shapes.append(arg)
        if shapes != []:
            expected = shapes[0].numQuads
            for shape in shapes[1:]:
                if shape.numQuads != expected:
                    raise InvalidOperationInputs(
                        f"Shapes with differing number of quadrants per layer are not supported for operation '{func.__name__}'")
        return func(*args,**kwargs)
    return wrapper

def cut(shape:Shape) -> list[Shape]:
    takeQuads = math.ceil(shape.numQuads/2)
    cutPoints = [(0,shape.numQuads-1),(shape.numQuads-takeQuads,shape.numQuads-takeQuads-1)]
    layers = shape.layers
    for layerIndex,layer in enumerate(layers):
        for cutPoint in cutPoints:
            if _crystalsFused(layer[cutPoint[0]],layer[cutPoint[1]]):
                _breakCrystals(layers,layerIndex,cutPoint[0])
    shapeA = []
    shapeB = []
    for layer in layers:
        shapeA.append([*([Quadrant(NOTHING_CHAR,NOTHING_CHAR)]*(shape.numQuads-takeQuads)),*(layer[-takeQuads:])])
        shapeB.append([*(layer[:-takeQuads]),*([Quadrant(NOTHING_CHAR,NOTHING_CHAR)]*(takeQuads))])
    shapeA, shapeB = [_cleanUpEmptyUpperLayers(_makeLayersFall(s)) for s in (shapeA,shapeB)]
    return [Shape(shapeA),Shape(shapeB)]

def halfCut(shape:Shape) -> list[Shape]:
    return [cut(shape)[1]]

def rotate90CW(shape:Shape) -> list[Shape]:
    newLayers = []
    for layer in shape.layers:
        newLayers.append([layer[-1],*(layer[:-1])])
    return [Shape(newLayers)]

def rotate90CCW(shape:Shape) -> list[Shape]:
    newLayers = []
    for layer in shape.layers:
        newLayers.append([*(layer[1:]),layer[0]])
    return [Shape(newLayers)]

def rotate180(shape:Shape) -> list[Shape]:
    takeQuads = math.ceil(shape.numQuads/2)
    newLayers = []
    for layer in shape.layers:
        newLayers.append([*(layer[takeQuads:]),*(layer[:takeQuads])])
    return [Shape(newLayers)]

@_differentNumQuadsUnsupported
def swapHalves(shapeA:Shape,shapeB:Shape) -> list[Shape]:
    numLayers = max(shapeA.numLayers,shapeB.numLayers)
    takeQuads = math.ceil(shapeA.numQuads/2)
    shapeACut, shapeBCut = cut(shapeA), cut(shapeB)
    shapeACut = [[*s.layers,*([[Quadrant(NOTHING_CHAR,NOTHING_CHAR)]*shapeA.numQuads]*(numLayers-len(s.layers)))] for s in shapeACut]
    shapeBCut = [[*s.layers,*([[Quadrant(NOTHING_CHAR,NOTHING_CHAR)]*shapeB.numQuads]*(numLayers-len(s.layers)))] for s in shapeBCut]
    returnShapeA = []
    returnShapeB = []
    for layerA0,layerA1,layerB0,layerB1 in zip(*shapeACut,*shapeBCut):
        returnShapeA.append([*(layerA1[:-takeQuads]),*(layerB0[-takeQuads:])])
        returnShapeB.append([*(layerB1[:-takeQuads]),*(layerA0[-takeQuads:])])
    returnShapeA, returnShapeB = _cleanUpEmptyUpperLayers(returnShapeA),_cleanUpEmptyUpperLayers(returnShapeB)
    return [Shape(returnShapeA),Shape(returnShapeB)]

@_differentNumQuadsUnsupported
def stack(bottomShape:Shape,topShape:Shape) -> list[Shape]:
    newTopShape = [[Quadrant(NOTHING_CHAR,NOTHING_CHAR) if q.shape == CRYSTAL_CHAR else q for q in l] for l in topShape.layers]
    newLayers = [*bottomShape.layers,*newTopShape]
    newLayers = _cleanUpEmptyUpperLayers(_makeLayersFall(newLayers))
    newLayers = newLayers[:MAX_LAYERS]
    return [Shape(newLayers)]

def topPaint(shape:Shape,color:str) -> list[Shape]:
    newLayers = shape.layers[:-1]
    newLayers.append([Quadrant(q.shape,q.color if q.shape in UNPAINTABLE_SHAPES else color) for q in shape.layers[-1]])
    return [Shape(newLayers)]

def pushPin(shape:Shape) -> list[Shape]:

    layers = shape.layers
    addedPins = []

    for quad in layers[0]:
        if quad.shape == NOTHING_CHAR:
            addedPins.append(Quadrant(NOTHING_CHAR,NOTHING_CHAR))
        else:
            addedPins.append(Quadrant(PIN_CHAR,NOTHING_CHAR))

    if len(layers) < MAX_LAYERS:
        newLayers = [addedPins,*layers]
    else:
        newLayers = [addedPins,*(layers[:MAX_LAYERS-1])]
        removedLayer = layers[MAX_LAYERS-1]
        for quadIndex,quad in enumerate(newLayers[MAX_LAYERS-1]):
            if _crystalsFused(quad,removedLayer[quadIndex]):
                _breakCrystals(newLayers,MAX_LAYERS-1,quadIndex)
        newLayers = _cleanUpEmptyUpperLayers(_makeLayersFall(newLayers))

    return [Shape(newLayers)]

def genCrystal(shape:Shape,color:str) -> list[Shape]:
    return [Shape([[Quadrant(CRYSTAL_CHAR,color) if q.shape in REPLACED_BY_CRYSTAL else q for q in l] for l in shape.layers])]