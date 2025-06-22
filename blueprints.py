import utils
from utils import Rotation, Pos, Size
import gameInfos
import globalInfos
import shapeCodeGenerator
import gzip
import base64
import json
import typing
import math
import binascii
import enum

T = typing.TypeVar("T")
T1 = typing.TypeVar("T1")
T2 = typing.TypeVar("T2")

PREFIX = "SHAPEZ2"
SEPARATOR = "-"
SUFFIX = "$"

BUILDING_BP_TYPE = "Building"
ISLAND_BP_TYPE = "Island"

ISLAND_ROTATION_CENTER = utils.FloatPos(*([(gameInfos.islands.ISLAND_SIZE/2)-.5]*2))

NUM_BP_ICONS = 4

# use variables instead of string literals and make potential ID changes not go unnoticed at the same time
# note : when changing an ID, make sure the migration functions still work as intended
class BuildingIds(enum.StrEnum):
    label = gameInfos.buildings.allBuildings["LabelDefaultInternalVariant"].id
    constantSignal = gameInfos.buildings.allBuildings["ConstantSignalDefaultInternalVariant"].id
    itemProducer = gameInfos.buildings.allBuildings["SandboxItemProducerDefaultInternalVariant"].id
    fluidProducer = gameInfos.buildings.allBuildings["SandboxFluidProducerDefaultInternalVariant"].id
    button = gameInfos.buildings.allBuildings["ButtonDefaultInternalVariant"].id
    compareGate = gameInfos.buildings.allBuildings["LogicGateCompareInternalVariant"].id
    compareGateMirrored = gameInfos.buildings.allBuildings["LogicGateCompareInternalVariantMirrored"].id
    globalSignalSender = gameInfos.buildings.allBuildings["ControlledSignalTransmitterInternalVariant"].id
    globalSignalReceiver = gameInfos.buildings.allBuildings["ControlledSignalReceiverInternalVariant"].id
    globalSignalReceiverMirrored = gameInfos.buildings.allBuildings["ControlledSignalReceiverInternalVariantMirrored"].id
    operatorSignalRceiver = gameInfos.buildings.allBuildings["WireGlobalTransmitterReceiverInternalVariant"].id

ISLAND_PATH_TYPES = [
    "Forward",
    "LeftTurn",
    "RightTurn",
    "LeftFwdSplitter",
    "RightFwdSplitter",
    "YSplitter",
    "TripleSplitter",
    "RightFwdMerger",
    "LeftFwdMerger",
    "YMerger",
    "TripleMerger"
]

ISLAND_IDS = {
    "rails" : [
        gameInfos.islands.allIslands[f"Rail_{path}"].id
        for path in ISLAND_PATH_TYPES
    ],
    "hasDisabledTrainUnloadingLanes" : [
        gameInfos.islands.allIslands[f"Layout_Train{pt}_{ct}{s}{f}"].id
        for ct in ("Shape","Fluid")
        for pt,s in (("Unloader","s"),("Transfer",""))
        for f in ("","_Flipped")
    ]
}

NUM_CONNECTIONS_PER_RAIL = {
    "Forward" : 1,
    "LeftTurn" : 1,
    "RightTurn" : 1,
    "LeftFwdSplitter" : 2,
    "RightFwdSplitter" : 2,
    "YSplitter" : 2,
    "TripleSplitter" : 3,
    "RightFwdMerger" : 2,
    "LeftFwdMerger" : 2,
    "YMerger" : 2,
    "TripleMerger" : 3
}

SPACE_BELT_ID_V1095 = "Layout_SpaceBeltNode"
SPACE_PIPE_ID_V1095 = "Layout_SpacePipeNode"
RAIL_ID_V1095 = "Layout_RailNode"
GLOBAL_WIRE_SENDER_ID_V1095_1118 = "WireGlobalTransmitterSenderInternalVariant"
GLOBAL_WIRE_RECEIVER_ID_V1095_1118 = "WireGlobalTransmitterReceiverInternalVariant"
FOUNDATIONS_ID_V1105_TO_1118 = {
    "Layout_Normal_1"       : "Foundation_1x1",
    "Layout_Normal_2"       : "Foundation_1x2",
    "Layout_Normal_3x1"     : "Foundation_1x3",
    "Layout_Normal_3_L"     : "Foundation_L3",
    "Layout_Normal_4_2x2"   : "Foundation_2x2",
    "Layout_Normal_4_T"     : "Foundation_T4",
    "Layout_Normal_3x2"     : "Foundation_2x3",
    "Layout_Normal_5_Cross" : "Foundation_C5",
    "Layout_Normal_9_3x3"   : "Foundation_3x3"
}

class BlueprintError(Exception): ...

class BlueprintIcon:

    def __init__(self,raw:str|None) -> None:
        self.type:typing.Literal["empty","icon","shape"]
        if raw is None:
            self.type = "empty"
        elif raw.startswith("icon:"):
            self.type = "icon"
            self.value = raw.removeprefix("icon:")
        else:
            self.type = "shape"
            self.value = raw.removeprefix("shape:")

    def _encode(self) -> str|None:
        if self.type == "empty":
            return None
        if self.type == "icon":
            return f"icon:{self.value}"
        return f"shape:{self.value}"

class TileEntry:
    def __init__(self,referTo) -> None:
        self.referTo:BuildingEntry|IslandEntry = referTo

class BuildingEntry:

    def __init__(self,pos:Pos,rotation:Rotation,type:gameInfos.buildings.Building,extra:typing.Any) -> None:
        self.pos = pos
        self.rotation = rotation
        self.type = type
        self.extra:typing.Any
        if extra is None:
            self.extra = _getDefaultEntryExtraData(type.id)
        else:
            self.extra = extra

    def _encode(self) -> dict:
        toReturn = {
            "T" : self.type.id
        }
        _omitKeyIfDefault(toReturn,"X",self.pos.x)
        _omitKeyIfDefault(toReturn,"Y",self.pos.y)
        _omitKeyIfDefault(toReturn,"L",self.pos.z)
        _omitKeyIfDefault(toReturn,"R",self.rotation.value)
        _omitKeyIfDefault(toReturn,"C",_encodeEntryExtraData(self.extra,self.type.id))
        return toReturn

class BuildingBlueprint:

    def __init__(self,asEntryList:list[BuildingEntry],icons:list[BlueprintIcon]) -> None:
        self.asEntryList = asEntryList
        self.asTileDict = _getTileDictFromEntryList(asEntryList)
        self.icons = icons

    def getSize(self) -> Size:
        return _genericGetSize(self)

    def getBuildingCount(self) -> int:
        return len(self.asEntryList)

    def getBuildingCounts(self) -> dict[str,int]:
        return _genericGetCounts(self)

    def getTileCount(self) -> int:
        return len(self.asTileDict)

    def getValidIcons(self) -> list[BlueprintIcon]:
        return _genericGetValidIcons(self)

    def _encode(self) -> dict:
        return {
            "$type" : BUILDING_BP_TYPE,
            "Icon" : {
                "Data" : [i._encode() for i in self.icons]
            },
            "Entries" : [e._encode() for e in self.asEntryList],
            "BinaryVersion" : gameInfos.versions.LATEST_GAME_VERSION # encoding always uses the latest format
        }

class IslandEntry:

    def __init__(self,pos:Pos,rotation:Rotation,type:gameInfos.islands.Island,buildingBP:BuildingBlueprint|None,extra:typing.Any) -> None:
        self.pos = pos
        self.rotation = rotation
        self.type = type
        self.buildingBP = buildingBP
        if extra is None:
            self.extra = _getDefaultEntryExtraData(type.id)
        else:
            self.extra = extra

    def _encode(self) -> dict:
        toReturn = {
            "T" : self.type.id
        }
        _omitKeyIfDefault(toReturn,"X",self.pos.x)
        _omitKeyIfDefault(toReturn,"Y",self.pos.y)
        _omitKeyIfDefault(toReturn,"Z",self.pos.z)
        _omitKeyIfDefault(toReturn,"R",self.rotation.value)
        _omitKeyIfDefault(toReturn,"S",_encodeEntryExtraData(self.extra,self.type.id))
        if self.buildingBP is not None:
            toReturn["B"] = self.buildingBP._encode()
        return toReturn

class IslandBlueprint:

    def __init__(self,asEntryList:list[IslandEntry],icons:list[BlueprintIcon]) -> None:
        self.asEntryList = asEntryList
        self.asTileDict = _getTileDictFromEntryList(asEntryList)
        self.icons = icons

    def getSize(self) -> Size:
        return _genericGetSize(self)

    def getIslandCount(self) -> int:
        return len(self.asEntryList)

    def getIslandCounts(self) -> dict[str,int]:
        return _genericGetCounts(self)

    def getTileCount(self) -> int:
        return len(self.asTileDict)

    def getValidIcons(self) -> list[BlueprintIcon]:
        return _genericGetValidIcons(self)

    def _encode(self) -> dict:
        return {
            "$type" : ISLAND_BP_TYPE,
            "Icons" : {
                "Data" : [i._encode() for i in self.icons]
            },
            "Entries" : [e._encode() for e in self.asEntryList]
        }

class Blueprint:

    def __init__(self,majorVersion:int,version:int,type_:str,blueprint:BuildingBlueprint|IslandBlueprint) -> None:
        self.majorVersion = majorVersion
        self.version = version
        self.type = type_
        self.islandBP:IslandBlueprint|None
        self.buildingBP:BuildingBlueprint|None
        if type(blueprint) == BuildingBlueprint:
            self.buildingBP = blueprint
            self.islandBP = None
        else:
            self.islandBP = blueprint
            tempBuildingList = []
            for island in blueprint.asEntryList:
                if island.buildingBP is None:
                    continue
                for building in island.buildingBP.asEntryList:
                    tempBuildingList.append(BuildingEntry(
                        Pos(
                            (island.pos.x*gameInfos.islands.ISLAND_SIZE) + building.pos.x,
                            (island.pos.y*gameInfos.islands.ISLAND_SIZE) + building.pos.y,
                            (island.pos.z*gameInfos.islands.ISLAND_SIZE) + building.pos.z
                        ),
                        building.rotation,
                        building.type,
                        building.extra
                    ))
            if tempBuildingList == []:
                self.buildingBP = None
            else:
                self.buildingBP = BuildingBlueprint(tempBuildingList,blueprint.icons)

    def getCost(self) -> int:
        # bp cost formula : last updated : alpha 15.2
        # note to self : dnSpy > BuildingBlueprint > ComputeCost() / ComputeTotalCost()
        if self.buildingBP is None:
            return 0
        buildingCount = self.buildingBP.getBuildingCount()
        if buildingCount <= 1:
            return 0
        try:
            return math.ceil((buildingCount-1) ** 1.3)
        except OverflowError:
            raise BlueprintError("Failed to compute blueprint cost")

    def getIslandUnitCost(self) -> int|float:
        if self.islandBP is None:
            return 0
        return sum(island.type.islandUnitCost for island in self.islandBP.asEntryList)

    def _encode(self) -> dict:
        return {
            "V" : gameInfos.versions.LATEST_GAME_VERSION, # encoding always uses the latest format
            "BP" : (self.buildingBP if self.islandBP is None else self.islandBP)._encode()
        }

def _genericGetSize(bp:BuildingBlueprint|IslandBlueprint) -> Size:
    (minX,minY,minZ), (maxX,maxY,maxZ) = [[func(e.__dict__[k] for e in bp.asTileDict.keys()) for k in ("x","y","z")] for func in (min,max)]
    return Size(
        maxX - minX + 1,
        maxY - minY + 1,
        maxZ - minZ + 1
    )

def _genericGetCounts(bp:BuildingBlueprint|IslandBlueprint) -> dict[str,int]:
    output = {}
    for entry in bp.asEntryList:
        entryType = entry.type.id
        if output.get(entryType) is None:
            output[entryType] = 1
        else:
            output[entryType] += 1
    return output

def _genericGetValidIcons(bp:BuildingBlueprint|IslandBlueprint) -> list[BlueprintIcon]:
    validIcons = []
    for icon in bp.icons[:NUM_BP_ICONS]:
        if icon.type == "empty":
            validIcons.append(icon)
            continue
        if icon.type == "icon":
            if (icon.value in VALID_BP_ICONS) and (icon.value != "Empty"):
                validIcons.append(icon)
            else:
                validIcons.append(BlueprintIcon(None))
            continue
        if shapeCodeGenerator.isShapeCodeValid(icon.value,None,True)[1]:
            validIcons.append(icon)
        else:
            validIcons.append(BlueprintIcon(None))
    validIcons += [BlueprintIcon(None)] * (NUM_BP_ICONS-len(validIcons))
    return validIcons

def _omitKeyIfDefault(dict:dict,key:str,value:int|str,defaults:tuple[typing.Any,...]=(None,0,"")) -> None:
    if value not in defaults:
        dict[key] = value

def _decodeEntryExtraData(raw:str|None,entryType:str) -> typing.Any:

    def standardDecode(rawDecoded:bytes,emptyIsLengthNegative1:bool) -> str:
        try:
            decodedBytes = utils.decodeStringWithLen(rawDecoded,emptyIsLengthNegative1=emptyIsLengthNegative1)
        except ValueError as e:
            raise BlueprintError(f"Error while decoding string : {e}")
        try:
            return decodedBytes.decode()
        except UnicodeDecodeError:
            raise BlueprintError(f"Can't decode from bytes")

    def getValidShapeGenerator(rawString:bytes) -> dict[str,str]:

        if len(rawString) < 1:
            raise BlueprintError("String must be at least 1 byte long")

        if rawString[0] == 0:
            return {"type":"empty"}

        if len(rawString) < 2:
            raise BlueprintError("String must be at least 2 bytes long")

        if (rawString[0] != 1) or (rawString[1] != 1):
            raise BlueprintError("First two bytes of shape generation string aren't '\\x01'")

        shapeCode = standardDecode(rawString[2:],True)
        error, valid = shapeCodeGenerator.isShapeCodeValid(shapeCode,None,True)

        if not valid:
            raise BlueprintError(f"Invalid shape code : {error}")

        return {"type":"shape","value":shapeCode}

    def getValidFluidGenerator(rawString:bytes) -> dict[str,str]:

        if len(rawString) < 1:
            raise BlueprintError("String must be at least 1 byte long")

        if rawString[0] == 0:
            return {"type":"empty"}

        if len(rawString) < 2:
            raise BlueprintError("String must be at least 2 bytes long")

        if rawString[0] != 1:
            raise BlueprintError("First byte of fluid generation string isn't '\\x01'")

        try:
            color = rawString[1:2].decode()
        except UnicodeDecodeError:
            raise BlueprintError("Invalid color")

        if color not in globalInfos.SHAPE_COLORS:
            raise BlueprintError(f"Unknown color : '{color}'")

        return {"type":"paint","value":color}

    if raw is None:
        rawDecoded = b""
    else:
        try:
            rawDecoded = base64.b64decode(raw,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")

    if entryType == BuildingIds.label:
        return standardDecode(rawDecoded,False)

    if entryType == BuildingIds.constantSignal:

        if len(rawDecoded) < 1:
            raise BlueprintError("String must be at least 1 byte long")
        signalType = rawDecoded[0]

        if signalType > 7:
            raise BlueprintError(f"Unknown signal type : {signalType}")

        if signalType in (0,1,2): # empty, null, conflict
            return {
                "type" : {
                    0 : "empty",
                    1 : "null",
                    2 : "conflict"
                }[signalType]
            }

        if signalType in (4,5): # bool
            return {"type":"bool","value":signalType==5}

        signalValue = rawDecoded[1:]

        if signalType == 3: # integer
            if len(signalValue) != 4:
                raise BlueprintError("Signal value must be 4 bytes long for integer signal type")
            return {"type":"int","value":int.from_bytes(signalValue,"little",signed=True)}

        if signalType == 6: # shape
            try:
                return {"type":"shape","value":getValidShapeGenerator(signalValue)}
            except BlueprintError as e:
                raise BlueprintError(f"Error while decoding shape signal value : {e}")

        # fluid
        try:
            return {"type":"fluid","value":getValidFluidGenerator(signalValue)}
        except BlueprintError as e:
            raise BlueprintError(f"Error while decoding fluid signal value : {e}")

    if entryType == BuildingIds.itemProducer:
        try:
            return getValidShapeGenerator(rawDecoded)
        except BlueprintError as e:
            raise BlueprintError(f"Error while decoding shape generation string : {e}")

    if entryType == BuildingIds.fluidProducer:
        try:
            return getValidFluidGenerator(rawDecoded)
        except BlueprintError as e:
            raise BlueprintError(f"Error while decoding fluid generation string : {e}")

    if entryType == BuildingIds.button:

        if len(rawDecoded) < 1:
            raise BlueprintError("String must be at least 1 byte long")

        return rawDecoded[0] != 0

    if entryType in (BuildingIds.compareGate,BuildingIds.compareGateMirrored):

        if len(rawDecoded) < 1:
            raise BlueprintError("String must be at least 1 byte long")

        compareMode = rawDecoded[0]

        if (compareMode < 1) or (compareMode > 6):
            raise BlueprintError(f"Unknown compare mode : {compareMode}")

        return [
            "Equal",
            "GreaterEqual",
            "Greater",
            "Less",
            "LessEqual",
            "NotEqual"
        ][compareMode-1]

    if entryType in (BuildingIds.globalSignalReceiver,BuildingIds.globalSignalReceiverMirrored):

        if rawDecoded != bytes([0,0,0,2]):
            raise BlueprintError("Must be '\\x00\\x00\\x00\\x02'")

        return None

    if entryType == BuildingIds.operatorSignalRceiver:

        if rawDecoded not in (bytes([0,0,0,2]),bytes([1,0,0,2])):
            raise BlueprintError("Must be '\\x00\\x00\\x00\\x02' or '\\x01\\x00\\x00\\x02'")

        return rawDecoded[0]

    # islands

    if entryType in ISLAND_IDS["rails"]:

        numConnections = NUM_CONNECTIONS_PER_RAIL[entryType.removeprefix("Rail_")]

        if len(rawDecoded) < 1:
            raise BlueprintError("String must be at least 1 byte long")

        numConnectionsInData = rawDecoded[0]
        if numConnectionsInData < numConnections:
            raise BlueprintError(f"Must have at least {numConnections} color information")

        colorData = rawDecoded[1:]
        if len(colorData) != 4*numConnectionsInData:
            raise BlueprintError("Color data isn't the indicated length")

        colorInts = [int.from_bytes(colorData[i*4:(i+1)*4],"little") for i in range(numConnectionsInData)]
        return [
            {
                "y" : (c & 64) != 0,
                "m" : (c & 32) != 0,
                "c" : (c & 16) != 0,
                "w" : (c & 8) != 0,
                "r" : (c & 4) != 0,
                "g" : (c & 2) != 0,
                "b" : (c & 1) != 0
            }
            for c in colorInts
        ]

    if entryType in ISLAND_IDS["hasDisabledTrainUnloadingLanes"]:

        if len(rawDecoded) < 4:
            raise BlueprintError("String must be at least 4 bytes long")

        numDisabledLanes = int.from_bytes(rawDecoded[:4],"little",signed=True)

        if numDisabledLanes < 0:
            raise BlueprintError("Number of disabled lanes must be positive")

        rawDisabledLanes = rawDecoded[4:]

        if len(rawDisabledLanes) < (numDisabledLanes*4):
            raise BlueprintError(f"Disabled lanes data must be at least {numDisabledLanes*4} bytes long")

        return [int.from_bytes(rawDisabledLanes[i*4:(i+1)*4],"little",signed=True) for i in range(numDisabledLanes)]

    return None

def _encodeEntryExtraData(extra:typing.Any,entryType:str) -> str|None:

    def b64encode(string:bytes) -> str:
        return base64.b64encode(string).decode()

    def standardEncode(string:str,emptyIsLengthNegative1:bool) -> str:
        return b64encode(utils.encodeStringWithLen(string.encode(),emptyIsLengthNegative1=emptyIsLengthNegative1))

    def encodeShapeGen(shapeGen:dict[str,str]) -> bytes:
        if shapeGen["type"] == "empty":
            return bytes([0])
        return bytes([1,1]) + utils.encodeStringWithLen(shapeGen["value"].encode())

    def encodeFluidGen(fluidGen:dict[str,str]) -> bytes:
        if fluidGen["type"] == "empty":
            return bytes([0])
        return bytes([1]) + fluidGen["value"].encode()

    if entryType == BuildingIds.label:
        return standardEncode(extra,False)

    if entryType == BuildingIds.constantSignal:

        if extra["type"] in ("empty","null","conflict"):
            return b64encode(bytes([{"empty":0,"null":1,"conflict":2}[extra["type"]]]))

        if extra["type"] == "bool":
            return b64encode(bytes([5 if extra["value"] else 4]))

        if extra["type"] == "int":
            return b64encode(bytes([3])+extra["value"].to_bytes(4,"little",signed=True))

        if extra["type"] == "shape":
            return b64encode(bytes([6])+encodeShapeGen(extra["value"]))

        if extra["type"] == "fluid":
            return b64encode(bytes([7])+encodeFluidGen(extra["value"]))

    if entryType == BuildingIds.itemProducer:
        return b64encode(encodeShapeGen(extra))

    if entryType == BuildingIds.fluidProducer:
        return b64encode(encodeFluidGen(extra))

    if entryType == BuildingIds.button:
        return b64encode(bytes([int(extra)]))

    if entryType in (BuildingIds.compareGate,BuildingIds.compareGateMirrored):
        return b64encode(bytes([{
            "Equal" : 1,
            "GreaterEqual" : 2,
            "Greater" : 3,
            "Less" : 4,
            "LessEqual" : 5,
            "NotEqual" : 6
        }[extra]]))

    if entryType in (BuildingIds.globalSignalReceiver,BuildingIds.globalSignalReceiverMirrored):
        return b64encode(bytes([0,0,0,2]))

    if entryType == BuildingIds.operatorSignalRceiver:
        return b64encode(bytes([extra,0,0,2]))

    # islands

    if entryType in ISLAND_IDS["rails"]:
        colorInts:list[int] = []
        for color in extra:
            encodedColor = 0
            if color["y"]:
                encodedColor += 64
            if color["m"]:
                encodedColor += 32
            if color["c"]:
                encodedColor += 16
            if color["w"]:
                encodedColor += 8
            if color["r"]:
                encodedColor += 4
            if color["g"]:
                encodedColor += 2
            if color["b"]:
                encodedColor += 1
            colorInts.append(encodedColor)
        return b64encode(bytes([len(colorInts)])+b"".join(c.to_bytes(4,"little") for c in colorInts))

    if entryType in ISLAND_IDS["hasDisabledTrainUnloadingLanes"]:
        return b64encode(
            len(extra).to_bytes(4,"little",signed=True)
            + b"".join(l.to_bytes(4,"little",signed=True) for l in extra)
        )

    if extra is None:
        return None

    raise ValueError(f"Attempt to encode extra data of entry that shouldn't have any ({entryType})")

def _getDefaultEntryExtraData(entryType:str) -> typing.Any:

    if entryType == BuildingIds.label:
        return "Label"

    if entryType == BuildingIds.constantSignal:
        return {"type":"null"}

    if entryType == BuildingIds.itemProducer:
        return {"type":"shape","value":"CuCuCuCu"}

    if entryType == BuildingIds.fluidProducer:
        return {"type":"paint","value":"r"}

    if entryType == BuildingIds.button:
        return False

    if entryType in (BuildingIds.compareGate,BuildingIds.compareGateMirrored):
        return "Equal"

    if entryType == BuildingIds.operatorSignalRceiver:
        return 0

    # islands

    if entryType in ISLAND_IDS["rails"]:
        return [
            {k:False for k in ["r","g","b","c","m","y","w"]}
            for _ in range(NUM_CONNECTIONS_PER_RAIL[entryType.removeprefix("Rail_")])
        ]

    if entryType in ISLAND_IDS["hasDisabledTrainUnloadingLanes"]:
        return []

    return None

def _getTileDictFromEntryList(entryList:list[BuildingEntry]|list[IslandEntry]) -> dict[Pos,TileEntry]:
    tileDict:dict[Pos,TileEntry] = {}
    for entry in entryList:
        if type(entry) == BuildingEntry:
            curTiles = entry.type.tiles
        else:
            curTiles = [t.pos for t  in entry.type.tiles]
        curTiles = [t.rotateCW(entry.rotation) for t in curTiles]
        curTiles = [Pos(entry.pos.x+t.x,entry.pos.y+t.y,entry.pos.z+t.z) for t in curTiles]
        for curTile in curTiles:
            tileDict[curTile] = TileEntry(entry)
    return tileDict

def _getDefaultRawIcons(bpType:str) -> list[str|None]:
    return [
        "icon:" + ("Buildings" if bpType == BUILDING_BP_TYPE else "Platforms"),
        None,
        None,
        "shape:" + ("Cu"*4 if bpType == BUILDING_BP_TYPE else "Ru"*4)
    ]

def _loadIcons() -> list[str]:
    with open(globalInfos.GI_ICONS_PATH,encoding="utf-8") as f:
        return json.load(f)["Icons"]
VALID_BP_ICONS = _loadIcons()





_ERR_MSG_PATH_SEP = ">"
_ERR_MSG_PATH_START = "'"
_ERR_MSG_PATH_END = "' : "
_defaultObj = object()

def _getKeyValue(dict:dict,key:str,expectedValueType:type[T1],default:T2=_defaultObj) -> T1|T2:

    value = dict.get(key,_defaultObj)

    if value is _defaultObj:
        if default is _defaultObj:
            raise BlueprintError(f"{_ERR_MSG_PATH_END}Missing '{key}' key")
        return default

    valueType = type(value)
    if valueType != expectedValueType:
        raise BlueprintError(
            f"{_ERR_MSG_PATH_SEP}{key}{_ERR_MSG_PATH_END}Incorrect value type, expected '{expectedValueType.__name__}', got '{valueType.__name__}'")

    return value

def _decodeBlueprintFirstPart(rawBlueprint:str) -> tuple[dict,int]:

    try:

        sepCount = rawBlueprint.count(SEPARATOR)
        if sepCount != 2:
            raise BlueprintError(f"Expected 2 separators, got {sepCount}")

        prefix, majorVersion, codeAndSuffix = rawBlueprint.split(SEPARATOR)

        if prefix != PREFIX:
            raise BlueprintError("Incorrect prefix")

        if not utils.isNumber(majorVersion):
            raise BlueprintError("Version not a number")
        majorVersion = int(majorVersion)

        if not codeAndSuffix.endswith(SUFFIX):
            raise BlueprintError("Doesn't end with suffix")

        encodedBP = codeAndSuffix.removesuffix(SUFFIX)

        if encodedBP == "":
            raise BlueprintError("Empty encoded section")

        try:
            encodedBP = base64.b64decode(encodedBP,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")
        try:
            encodedBP = gzip.decompress(encodedBP)
        except Exception as e:
            raise BlueprintError(f"Can't gzip decompress ({e.__class__.__name__})")
        try:
            decodedBP = json.loads(encodedBP)
        except Exception as e:
            raise BlueprintError(f"Can't parse json ({e.__class__.__name__})")

        if type(decodedBP) != dict:
            raise BlueprintError("Decoded value isn't a json object")

        try:
            _getKeyValue(decodedBP,"V",int)
            _getKeyValue(decodedBP,"BP",dict)
        except BlueprintError as e:
            raise BlueprintError(f"Error in {_ERR_MSG_PATH_START}blueprint json object{e}")

    except BlueprintError as e:
        raise BlueprintError(f"Error while decoding blueprint string : {e}")

    return decodedBP, majorVersion

def _encodeBlueprintLastPart(blueprint:dict) -> str:
    blueprint = base64.b64encode(gzip.compress(json.dumps(blueprint,separators=(",",":")).encode())).decode()
    blueprint = (
        PREFIX
        + SEPARATOR
        + str(gameInfos.versions.LATEST_MAJOR_VERSION) # encoding always uses the latest format
        + SEPARATOR
        + blueprint
        + SUFFIX
    )
    return blueprint

def _spaceBeltPipeRailV1095Migration(entry:dict,entryType:str) -> None:

    errMsgBase = f"{_ERR_MSG_PATH_SEP}space belt/pipe/rail v1095 migration"

    def fs(*args:T) -> frozenset[T]:
        return frozenset(args)

    conversionTable:dict[frozenset[tuple[int,int]],str] = {
        fs((0,0)) : "Forward",
        fs((0,3)) : "LeftTurn",
        fs((0,1)) : "RightTurn",
        fs((0,0),(0,3)) : "LeftFwdSplitter",
        fs((0,0),(0,1)) : "RightFwdSplitter",
        fs((0,3),(0,1)) : "YSplitter",
        fs((0,0),(0,3),(0,1)) : "TripleSplitter",
        fs((0,0),(1,0)) : "RightFwdMerger",
        fs((0,0),(3,0)) : "LeftFwdMerger",
        fs((1,0),(3,0)) : "YMerger",
        fs((0,0),(1,0),(3,0)) : "TripleMerger"
    }

    railColorOrder = {
        "Forward" : [(0,0)],
        "LeftTurn" : [(0,3)],
        "RightTurn" : [(0,1)],
        "LeftFwdSplitter" : [(0,0),(0,3)],
        "RightFwdSplitter" : [(0,0),(0,1)],
        "YSplitter" : [(0,1),(0,3)],
        "TripleSplitter" : [(0,0),(0,1),(0,3)],
        # order for the mergers made up as not easily checkable ingame and doesn't matter in game-generated blueprints
        "RightFwdMerger" : [(0,0),(1,0)],
        "LeftFwdMerger" : [(0,0),(3,0)],
        "YMerger" : [(3,0),(1,0)],
        "TripleMerger" : [(0,0),(3,0),(1,0)]
    }

    isRail = entryType == RAIL_ID_V1095

    try:
        extraData = _getKeyValue(entry,"C",str)
    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{e}")

    try:

        try:
            rawDecoded = base64.b64decode(extraData,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")

        if len(rawDecoded) < 2:
            raise BlueprintError("String must be at least 2 bytes long")

        layoutHeader = rawDecoded[0]
        if (not isRail) and (layoutHeader != 20):
            raise BlueprintError("First byte of space belt/pipe layout isn't '\\x14'")
        if (isRail) and (layoutHeader != 10):
            raise BlueprintError("First byte of rail layout isn't '\\x0a'")

        layoutType = rawDecoded[1]
        if (layoutType < 1) or (layoutType > 3):
            raise BlueprintError(f"Invalid layout type : {layoutType}")

        layoutData = rawDecoded[2:]
        dataLen = (6*layoutType) if isRail else (2*layoutType)
        if len(layoutData) != dataLen:
            raise BlueprintError("Incorrect layout data length")

        if isRail:
            connections = [(layoutData[i*6],layoutData[(i*6)+1]) for i in range(layoutType)]
            colorData = [layoutData[(i*6)+2:(i+1)*6] for i in range(layoutType)]
        else:
            connections = [(layoutData[i*2],layoutData[(i*2)+1]) for i in range(layoutType)]

        newLayoutType = None
        for newRotation in range(4):
            connectionsRotated = [((i-newRotation)%4,(o-newRotation)%4) for i,o in connections]
            connectionsFS = frozenset(connectionsRotated)
            potentialLayout = conversionTable.get(connectionsFS)
            if potentialLayout is not None:
                newLayoutType = potentialLayout
                break
        if newLayoutType is None:
            raise BlueprintError("Invalid layout data")

        entry["T"] = (
            ("Rail" if isRail else ("SpaceBelt" if entryType == SPACE_BELT_ID_V1095 else "SpacePipe"))
            + "_"
            + newLayoutType
        )
        entry["R"] = newRotation

        if not isRail:
            # entry["S"] intentionally not set
            return

        colorDataOrdered:list[bytes] = []
        for connection in railColorOrder[newLayoutType]:
            colorDataOrdered.append(colorData[connectionsRotated.index(connection)])

        entry["S"] = base64.b64encode(bytes([layoutType])+b"".join(colorDataOrdered)).decode()

    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{_ERR_MSG_PATH_END}{e}")

def _globalWireTransmitterV1095Migration(entry:dict,entryType:str) -> None:

    errMsgBase = f"{_ERR_MSG_PATH_SEP}global wire transmitter v1095 migration"
    isReceiver = entryType == GLOBAL_WIRE_RECEIVER_ID_V1095_1118

    try:
        extraData = _getKeyValue(entry,"C",str)
    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{e}")

    try:

        try:
            rawDecoded = base64.b64decode(extraData,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")

        stringLen = 5 if isReceiver else 4
        if len(rawDecoded) < stringLen:
            raise BlueprintError(f"String must be at least {stringLen} bytes long")

        channel = int.from_bytes(rawDecoded[:4],"little",signed=True)

        if (channel < 0) or (channel > 7):
            raise BlueprintError("Channel out of range")

        encodedChannel = channel.to_bytes(3,"little")

        if isReceiver:
            isROS = rawDecoded[4] == 1
            entry["C"] = base64.b64encode(encodedChannel+bytes([2 if isROS else 1])).decode()
            return

        entry["C"] = base64.b64encode(encodedChannel).decode() + "AQQAAAABAQEBAAAAAAAAAIAAAAAAAAAAgAA="

    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{_ERR_MSG_PATH_END}{e}")

def _foundationV1105Migration(entry:dict,entryType:str) -> None:
    entry["T"] = FOUNDATIONS_ID_V1105_TO_1118[entryType]

def _globalWireReceiverV1118RegularMigration(entry:dict) -> None:

    errMsgBase = f"{_ERR_MSG_PATH_SEP}global wire receiver v1118 regular migration"

    try:
        extraData = _getKeyValue(entry,"C",str)
    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{e}")

    try:

        try:
            rawDecoded = base64.b64decode(extraData,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")

        if len(rawDecoded) < 4:
            raise BlueprintError(f"String must be at least 4 bytes long")

        channel = int.from_bytes(rawDecoded[:3],"little")

        # set to a ROS channel
        if (rawDecoded[3] == 2) and (channel in (0,1)):
            newData = rawDecoded[:4]
        # regular channel or invalid, reset
        else:
            newData = bytes([0,0,0,2])

        entry["C"] = base64.b64encode(newData).decode()

    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{_ERR_MSG_PATH_END}{e}")

def _globalWireTransmitterV1118AdvancedMigration(entry:dict,entryType:str) -> None:

    if entryType == GLOBAL_WIRE_SENDER_ID_V1095_1118:
        entry["T"] = BuildingIds.globalSignalSender.value
        entry.pop("C",None)
        return

    errMsgBase = f"{_ERR_MSG_PATH_SEP}global wire receiver v1118 advanced migration"

    try:
        extraData = _getKeyValue(entry,"C",str)
    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{e}")

    try:

        try:
            rawDecoded = base64.b64decode(extraData,validate=True)
        except binascii.Error:
            raise BlueprintError("Can't decode from base64")

        if len(rawDecoded) < 4:
            raise BlueprintError(f"String must be at least 4 bytes long")

        channel = int.from_bytes(rawDecoded[:3],"little")

        # set to a regular channel
        if rawDecoded[3] == 1:
            entry["T"] = BuildingIds.globalSignalReceiver.value
            entry["C"] = "AAAAAg=="
            return

        # set to a ROS channel
        if channel in (0,1): # valid channel
            newData = rawDecoded[:4]
        else: # invalid, reset
            newData = bytes([0,0,0,2])
        entry["C"] = base64.b64encode(newData).decode()

    except BlueprintError as e:
        raise BlueprintError(f"{errMsgBase}{_ERR_MSG_PATH_END}{e}")

def _getValidBlueprint(blueprint:dict,mustBeBuildingBP:bool=False,mainBPVersion:int|None=None,migrate:bool=False) -> dict:

    validBP = {}

    bpType = _getKeyValue(blueprint,"$type",str)

    if bpType not in (BUILDING_BP_TYPE,ISLAND_BP_TYPE):
        raise BlueprintError(f"{_ERR_MSG_PATH_SEP}$type{_ERR_MSG_PATH_END}Unknown blueprint type : '{bpType}'")

    isBuildingBP = bpType == BUILDING_BP_TYPE

    if mustBeBuildingBP and (not isBuildingBP):
        raise BlueprintError(f"{_ERR_MSG_PATH_SEP}$type{_ERR_MSG_PATH_END}Must be a building blueprint")

    validBP["$type"] = bpType

    bpIcons = _getKeyValue(blueprint,"Icon",dict,{"Data":_getDefaultRawIcons(bpType)})

    try:

        bpIconsData = _getKeyValue(bpIcons,"Data",list,[])

        validIcons = []

        for i,icon in enumerate(bpIconsData):
            try:

                iconType = type(icon)

                if iconType in (dict,list):
                    raise BlueprintError(f"{_ERR_MSG_PATH_END}Incorrect value type")

                if iconType in (bool,int,float):
                    continue

                if icon == "":
                    icon = None

                if icon is None:
                    validIcons.append(icon)
                    continue

                icon:str

                if not icon.startswith(("icon:","shape:")):
                    continue

                if icon.startswith("icon:") and (len(icon.removeprefix("icon:")) in (0,1)):
                    continue

                validIcons.append(icon)

            except BlueprintError as e:
                raise BlueprintError(f"{_ERR_MSG_PATH_SEP}Data{_ERR_MSG_PATH_SEP}{i}{e}")

    except BlueprintError as e:
        raise BlueprintError(f"{_ERR_MSG_PATH_SEP}Icon{e}")

    validBP["Icon"] = {
        "Data" : validIcons
    }

    bpEntries = _getKeyValue(blueprint,"Entries",list)

    if bpEntries == []:
        raise BlueprintError(f"{_ERR_MSG_PATH_SEP}Entries{_ERR_MSG_PATH_END}Empty list")

    if isBuildingBP:
        versionForMigration = _getKeyValue(blueprint,"BinaryVersion",int,gameInfos.versions.LATEST_GAME_VERSION)
    else:
        versionForMigration = mainBPVersion

    allowedEntryTypes = (
        gameInfos.buildings.allBuildings.keys()
        if isBuildingBP else
        gameInfos.islands.allIslands.keys()
    )
    layerKey = "L" if isBuildingBP else "Z"
    extraDataKey = "C" if isBuildingBP else "S"

    validBPEntries = []

    for i,entry in enumerate(bpEntries):
        try:

            entryType = type(entry)
            if entryType != dict:
                raise BlueprintError(f"{_ERR_MSG_PATH_END}Incorrect value type, expected 'dict', got '{entryType.__name__}'")

            x, y, z, r = (_getKeyValue(entry,k,int,0) for k in ("X","Y",layerKey,"R"))

            if (r < 0) or (r > 3):
                raise BlueprintError(f"{_ERR_MSG_PATH_SEP}R{_ERR_MSG_PATH_END}Rotation must be in range from 0 to 3")

            t = _getKeyValue(entry,"T",str)

            if versionForMigration < 1103 : # before 0.0.9
                if t in (SPACE_BELT_ID_V1095,SPACE_PIPE_ID_V1095,RAIL_ID_V1095):
                    _spaceBeltPipeRailV1095Migration(entry,t)
                elif t in (GLOBAL_WIRE_SENDER_ID_V1095_1118,GLOBAL_WIRE_RECEIVER_ID_V1095_1118):
                    _globalWireTransmitterV1095Migration(entry,t)
            if versionForMigration < 1118: # before 0.1.0-pre1
                if t in FOUNDATIONS_ID_V1105_TO_1118.keys():
                    _foundationV1105Migration(entry,t)
            if versionForMigration < 1119: # before 0.1.0-pre2
                if t in (GLOBAL_WIRE_SENDER_ID_V1095_1118,GLOBAL_WIRE_RECEIVER_ID_V1095_1118):
                    if migrate:
                        _globalWireTransmitterV1118AdvancedMigration(entry,t)
                    elif t == GLOBAL_WIRE_RECEIVER_ID_V1095_1118:
                        _globalWireReceiverV1118RegularMigration(entry)

            # if migration changed the values
            t = entry["T"]
            x, y, z, r = (entry.get(k,0) for k in ("X","Y",layerKey,"R"))

            if t not in allowedEntryTypes:
                if migrate:
                    continue
                raise BlueprintError(f"{_ERR_MSG_PATH_SEP}T{_ERR_MSG_PATH_END}Unknown entry type '{t}'")

            validEntry = {
                "X" : x,
                "Y" : y,
                layerKey : z,
                "R" : r,
                "T" : t
            }

            extra = _getKeyValue(entry,extraDataKey,str,None)
            try:
                extra = _decodeEntryExtraData(extra,t)
            except BlueprintError as e:
                raise BlueprintError(f"{_ERR_MSG_PATH_SEP}{extraDataKey}{_ERR_MSG_PATH_END}{e}")
            validEntry[extraDataKey] = extra

            if not isBuildingBP:
                b = entry.get("B",_defaultObj)
                if b is not _defaultObj:
                    b = _getKeyValue(entry,"B",dict)
                    try:
                        validB = _getValidBlueprint(b,True,migrate=migrate)
                    except BlueprintError as e:
                        raise BlueprintError(f"{_ERR_MSG_PATH_SEP}B{e}")
                    validEntry["B"] = validB

            validBPEntries.append(validEntry)

        except BlueprintError as e:
            raise BlueprintError(f"{_ERR_MSG_PATH_SEP}Entries{_ERR_MSG_PATH_SEP}{i}{e}")

    validBP["Entries"] = validBPEntries

    return validBP

def _decodeBuildingBP(buildings:list[dict[str,typing.Any]],icons:list[str|None]) -> BuildingBlueprint:

    entryList:list[BuildingEntry] = []
    occupiedTiles:set[Pos] = set()

    for building in buildings:

        curTiles = [t.rotateCW(building["R"]) for t in gameInfos.buildings.allBuildings[building["T"]].tiles]
        curTiles = [Pos(building["X"]+t.x,building["Y"]+t.y,building["L"]+t.z) for t in curTiles]

        for curTile in curTiles:

            if curTile in occupiedTiles:
                raise BlueprintError(f"Error while placing tile of '{building['T']}' at {curTile} : another tile is already placed there")

            occupiedTiles.add(curTile)

    for b in buildings:
        entryList.append(BuildingEntry(
            Pos(b["X"],b["Y"],b["L"]),
            Rotation(b["R"]),
            gameInfos.buildings.allBuildings[b["T"]],
            b["C"]
        ))

    return BuildingBlueprint(entryList,[BlueprintIcon(i) for i in icons])

def _decodeIslandBP(islands:list[dict[str,typing.Any]],icons:list[str|None]) -> IslandBlueprint:

    entryList:list[IslandEntry] = []
    occupiedTiles:set[Pos] = set()

    for island in islands:

        curTiles = [t.pos.rotateCW(island["R"]) for t in gameInfos.islands.allIslands[island["T"]].tiles]
        curTiles = [Pos(island["X"]+t.x,island["Y"]+t.y,island["Z"]+t.z) for t in curTiles]

        for curTile in curTiles:

            if curTile in occupiedTiles:
                raise BlueprintError(f"Error while placing tile of '{island['T']}' at {curTile} : another tile is already placed there")

            occupiedTiles.add(curTile)

    for island in islands:

        islandEntryInfos:dict[str,Pos|int|gameInfos.islands.Island|typing.Any] = {
            "pos" : Pos(island["X"],island["Y"],island["Z"]),
            "r" : island["R"],
            "t" : gameInfos.islands.allIslands[island["T"]],
            "s" : island["S"]
        }

        if island.get("B") is None:
            entryList.append(IslandEntry(
                islandEntryInfos["pos"],
                Rotation(islandEntryInfos["r"]),
                islandEntryInfos["t"],
                None,
                islandEntryInfos["s"]
            ))
            continue

        try:
            curBuildingBP = _decodeBuildingBP(island["B"]["Entries"],island["B"]["Icon"]["Data"])
        except BlueprintError as e:
            raise BlueprintError(
                f"Error while creating building blueprint representation of '{islandEntryInfos['t'].id}' at {islandEntryInfos['pos']} : {e}")

        curIslandBuildArea = [a.rotateCW(islandEntryInfos["r"],ISLAND_ROTATION_CENTER) for a in islandEntryInfos["t"].totalBuildArea]

        for pos,b in curBuildingBP.asTileDict.items():

            curBuilding:BuildingEntry = b.referTo

            inArea = False
            for area in curIslandBuildArea:
                if area.containsPos(pos) and (pos.z >= 0) and (pos.z < gameInfos.islands.ISLAND_SIZE):
                    inArea = True
                    break
            if not inArea:
                raise BlueprintError(
                    f"Error in '{islandEntryInfos['t'].id}' at {islandEntryInfos['pos']} : tile of building '{curBuilding.type.id}' at {pos} is not inside its platform build area")

        entryList.append(IslandEntry(
            islandEntryInfos["pos"],
            Rotation(islandEntryInfos["r"]),
            islandEntryInfos["t"],
            curBuildingBP,
            islandEntryInfos["s"]
        ))

    return IslandBlueprint(entryList,[BlueprintIcon(i) for i in icons])





def getBlueprintVersion(blueprint:str) -> int:
    return _decodeBlueprintFirstPart(blueprint)[0]["V"]

def decodeBlueprint(rawBlueprint:str,migrate:bool=False) -> Blueprint:
    decodedBP, majorVersion = _decodeBlueprintFirstPart(rawBlueprint)
    version = decodedBP["V"]

    try:
        validBP = _getValidBlueprint(decodedBP["BP"],mainBPVersion=version,migrate=migrate)
    except BlueprintError as e:
        raise BlueprintError(f"Error in {_ERR_MSG_PATH_START}blueprint json object{_ERR_MSG_PATH_SEP}BP{e}")

    bpType = validBP["$type"]

    if bpType == BUILDING_BP_TYPE:
        func = _decodeBuildingBP
        text = "building"
    else:
        func = _decodeIslandBP
        text = "platform"

    try:
        decodedDecodedBP = func(validBP["Entries"],validBP["Icon"]["Data"])
    except BlueprintError as e:
        raise BlueprintError(f"Error while creating {text} blueprint representation : {e}")
    return Blueprint(majorVersion,version,bpType,decodedDecodedBP)

def encodeBlueprint(blueprint:Blueprint) -> str:
    return _encodeBlueprintLastPart(blueprint._encode())

def getPotentialBPCodesInString(string:str) -> list[str]:

    if PREFIX not in string:
        return []

    bps = string.split(PREFIX)[1:]

    bpCodes = []

    for bp in bps:

        if SUFFIX not in bp:
            continue

        bp = bp.split(SUFFIX)[0]

        bpCodes.append(PREFIX+bp+SUFFIX)

    return bpCodes

def getDefaultBlueprintIcons(bpType:str) -> list[BlueprintIcon]:
    return [BlueprintIcon(i) for i in _getDefaultRawIcons(bpType)]